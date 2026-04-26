"""Authentication module for Haudi - handles IDK OAuth2 PKCE + MBB token bridge.

Uses a browser-based OAuth2 flow so we NEVER parse HTML login pages.
This makes authentication completely resilient to VW/Audi login page changes.

Flow:
  1. generate_authorize_url() → URL + PKCE state for user to open in browser
  2. User authenticates in browser → redirected to myaudi:///...?code=XYZ
  3. exchange_code() → exchanges code for tokens
  4. refresh_tokens() → all subsequent re-authentication (no browser needed)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp

from .const import (
    BFF_BASE_URLS,
    HEADER_ACCEPT,
    HEADER_CONTENT_TYPE,
    HEADER_USER_AGENT,
    HEADER_X_APP_NAME,
    HEADER_X_APP_VERSION,
    IDK_CODE_CHALLENGE_METHOD,
    IDK_REDIRECT_URI,
    IDK_RESPONSE_TYPE_AUTH,
    IDK_RESPONSE_TYPE_TOKEN,
    IDK_SCOPES,
    MBB_OAUTH_BASE_URL,
    MBB_REGISTER_PATH,
    MBB_SCOPE,
    MBB_TOKEN_PATH,
    OIDC_CONFIG_PATH,
    TOKEN_ACCESS,
    TOKEN_EXPIRES_AT,
    TOKEN_EXPIRES_IN,
    TOKEN_ID,
    TOKEN_MBB_ACCESS,
    TOKEN_MBB_CLIENT_ID,
    TOKEN_MBB_REFRESH,
    TOKEN_REFRESH,
)

_LOGGER = logging.getLogger(__name__)

# Known client_id for myAudi EMEA – stable across app versions.
DEFAULT_CLIENT_ID = "09b6cbec-cd19-4589-82fd-363dfa8c24da@apps_vw-dilab_com"

# X-QMAuth HMAC secret (extracted from myAudi app, used by all known integrations)
_QMAUTH_SECRET = bytes([
    26, 256 - 74, 256 - 103, 37, 256 - 84, 23, 256 - 102,
    256 - 86, 78, 256 - 125, 256 - 85, 256 - 26, 113, 256 - 87,
    71, 109, 23, 100, 24, 256 - 72, 91, 256 - 41,
    6, 256 - 15, 67, 108, 256 - 95, 91, 256 - 26,
    71, 256 - 104, 256 - 100,
])


def _compute_x_qmauth() -> str:
    """Compute the X-QMAuth header value.

    Uses HMAC-SHA256 with a static secret and a timestamp-based message.
    The timestamp is divided by 100 (100-second windows).
    """
    timestamp = str(int(time.time() // 100))
    mac = hmac.new(_QMAUTH_SECRET, timestamp.encode("ascii"), hashlib.sha256)
    return f"v1:01da27b0:{mac.hexdigest()}"


class AuthError(Exception):
    """Authentication error."""


class PKCEState:
    """Holds PKCE challenge state for an in-progress authorization."""

    def __init__(self) -> None:
        self.code_verifier = _generate_code_verifier()
        self.code_challenge = _generate_code_challenge(self.code_verifier)
        self.state = _generate_nonce()
        self.nonce = _generate_nonce()


def _generate_code_verifier() -> str:
    """Generate a random PKCE code verifier (43-128 chars, URL-safe)."""
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")


def _generate_code_challenge(verifier: str) -> str:
    """Generate S256 code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _generate_nonce() -> str:
    return base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode("ascii")


def extract_code_from_url(url: str) -> str | None:
    """Extract authorization code from a redirect URL.

    After login the browser redirects to  myaudi:///...?code=XYZ&state=...
    The user copies this URL and we pull out the code.
    """
    parsed = urlparse(url)
    for source in (parsed.query, parsed.fragment):
        params = parse_qs(source)
        if "code" in params:
            return params["code"][0]
    return None


class AudiAuth:
    """Handle myAudi / VW Group IDK OAuth2 authentication.

    This class does NOT scrape HTML.  Two entry points:

    * Browser flow (config_flow setup):
        1. generate_authorize_url()  →  give URL to user
        2. User logs in via browser  →  redirected to myaudi:///
        3. exchange_code(code, pkce)  →  tokens stored
        4. All later refreshes via refresh_tokens()

    * Token restore (HA restart):
        1. Set self.tokens from stored config entry
        2. ensure_valid_token()  →  auto-refreshes if expired
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        region: str = "emea",
    ) -> None:
        self._session = session
        self._region = region
        self._bff_base = BFF_BASE_URLS[region]
        self._oidc_config: dict | None = None
        self._tokens: dict[str, str | float] = {}

    @property
    def tokens(self) -> dict[str, str | float]:
        """Return current tokens."""
        return self._tokens

    @tokens.setter
    def tokens(self, value: dict[str, str | float]) -> None:
        """Set tokens (e.g. from stored config entry)."""
        self._tokens = value

    @property
    def access_token(self) -> str | None:
        """Return IDK access token."""
        return self._tokens.get(TOKEN_ACCESS)

    @property
    def id_token(self) -> str | None:
        """Return IDK id token."""
        return self._tokens.get(TOKEN_ID)

    @property
    def mbb_access_token(self) -> str | None:
        """Return MBB access token."""
        return self._tokens.get(TOKEN_MBB_ACCESS)

    @property
    def is_token_expired(self) -> bool:
        """Check if access token is expired."""
        expires_at = self._tokens.get(TOKEN_EXPIRES_AT, 0)
        return time.time() >= float(expires_at) - 60

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": HEADER_USER_AGENT,
            "Accept": HEADER_ACCEPT,
            "X-App-Version": HEADER_X_APP_VERSION,
            "X-App-Name": HEADER_X_APP_NAME,
        }

    def _token_headers(self) -> dict[str, str]:
        """Headers for token exchange/refresh requests (includes X-QMAuth)."""
        return {
            **self._headers(),
            "Content-Type": "application/x-www-form-urlencoded",
            "X-QMAuth": _compute_x_qmauth(),
        }

    async def _fetch_openid_config(self) -> dict:
        """Fetch OpenID Connect discovery document from BFF."""
        if self._oidc_config:
            return self._oidc_config

        url = self._bff_base + OIDC_CONFIG_PATH
        async with self._session.get(url, headers=self._headers()) as resp:
            if resp.status != 200:
                raise AuthError(
                    f"Failed to fetch OpenID config: HTTP {resp.status}"
                )
            self._oidc_config = await resp.json()
            return self._oidc_config

    # ── Step 1: Build authorize URL (for user's browser) ─────────────

    async def generate_authorize_url(self) -> tuple[str, PKCEState]:
        """Build the full authorize URL the user should open in a browser.

        Returns (url, pkce_state).  The caller must keep pkce_state
        to later call exchange_code().
        """
        oidc = await self._fetch_openid_config()
        authorize_endpoint = oidc.get("authorization_endpoint", "")
        if not authorize_endpoint:
            raise AuthError("OpenID config missing authorization_endpoint")

        pkce = PKCEState()

        params = {
            "response_type": IDK_RESPONSE_TYPE_AUTH,
            "client_id": DEFAULT_CLIENT_ID,
            "redirect_uri": IDK_REDIRECT_URI,
            "scope": IDK_SCOPES,
            "state": pkce.state,
            "nonce": pkce.nonce,
            "code_challenge": pkce.code_challenge,
            "code_challenge_method": IDK_CODE_CHALLENGE_METHOD,
            "prompt": "login",
            "ui_locales": "en-GB en",
        }

        url = f"{authorize_endpoint}?{urlencode(params)}"
        return url, pkce

    # ── Step 2: Exchange authorization code for tokens ────────────────

    async def exchange_code(
        self, code: str, pkce: PKCEState
    ) -> dict[str, str | float]:
        """Exchange an authorization code (from the browser redirect) for tokens."""
        oidc = await self._fetch_openid_config()
        token_endpoint = oidc.get("token_endpoint", "")
        if not token_endpoint:
            raise AuthError("OpenID config missing token_endpoint")

        data = {
            "client_id": DEFAULT_CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": IDK_REDIRECT_URI,
            "response_type": IDK_RESPONSE_TYPE_TOKEN,
            "code_verifier": pkce.code_verifier,
        }

        _LOGGER.debug("Exchanging authorization code for tokens")
        async with self._session.post(
            token_endpoint,
            data=data,
            headers=self._token_headers(),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise AuthError(
                    f"Token exchange failed: HTTP {resp.status} – {body}"
                )
            token_response = await resp.json()

        self._tokens = {
            TOKEN_ACCESS: token_response.get("access_token", ""),
            TOKEN_ID: token_response.get("id_token", ""),
            TOKEN_REFRESH: token_response.get("refresh_token", ""),
            TOKEN_EXPIRES_IN: token_response.get("expires_in", 3600),
            TOKEN_EXPIRES_AT: time.time()
            + float(token_response.get("expires_in", 3600)),
        }

        _LOGGER.debug("IDK tokens obtained successfully")

        # Bridge to MBB for vehicle API access
        await self._bridge_to_mbb()

        return self._tokens

    # ── MBB bridge ───────────────────────────────────────────────────

    async def _register_mbb_client(self) -> str | None:
        """Register a mobile client with MBB to get a dynamic client_id."""
        url = MBB_OAUTH_BASE_URL + MBB_REGISTER_PATH
        json_data = {
            "client_name": "HAudi-HA",
            "platform": "google",
            "client_brand": "Audi",
            "appName": "myAudi",
            "appVersion": HEADER_X_APP_VERSION,
            "appId": "de.myaudi.mobile.assistant",
        }

        try:
            async with self._session.post(
                url,
                json=json_data,
                headers=self._headers(),
            ) as resp:
                if resp.status != 200 and resp.status != 201:
                    _LOGGER.debug(
                        "MBB client registration returned %s, skipping",
                        resp.status,
                    )
                    return None
                result = await resp.json()
                client_id = result.get("client_id", "")
                _LOGGER.debug("MBB client registered: %s", client_id[:8] + "...")
                return client_id
        except Exception:
            _LOGGER.debug("MBB client registration failed, will try without")
            return None

    async def _bridge_to_mbb(self) -> None:
        """Bridge IDK id_token → MBB access token for vehicle APIs."""
        if not self._tokens.get(TOKEN_ID):
            _LOGGER.warning("No IDK id_token available for MBB bridge")
            return

        # Register MBB client first to get dynamic X-Client-ID
        mbb_client_id = await self._register_mbb_client()

        token_url = MBB_OAUTH_BASE_URL + MBB_TOKEN_PATH
        data = {
            "grant_type": "id_token",
            "token": self._tokens[TOKEN_ID],
            "scope": MBB_SCOPE,
        }

        headers = self._token_headers()
        if mbb_client_id:
            headers["X-Client-ID"] = mbb_client_id

        _LOGGER.debug("Bridging IDK token to MBB")
        async with self._session.post(
            token_url,
            data=data,
            headers=headers,
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning(
                    "MBB token bridge failed: HTTP %s (vehicle control may be limited)",
                    resp.status,
                )
                return
            mbb_response = await resp.json()

        self._tokens[TOKEN_MBB_ACCESS] = mbb_response.get("access_token", "")
        self._tokens[TOKEN_MBB_REFRESH] = mbb_response.get("refresh_token", "")
        self._tokens[TOKEN_MBB_CLIENT_ID] = mbb_response.get("client_id", "")

        _LOGGER.debug("MBB tokens obtained successfully")

    async def refresh_tokens(self) -> dict[str, str | float]:
        """Refresh IDK tokens using refresh token."""
        refresh_token = self._tokens.get(TOKEN_REFRESH)
        if not refresh_token:
            raise AuthError(
                "No refresh token available – re-authenticate via browser"
            )

        oidc_config = await self._fetch_openid_config()
        token_endpoint = oidc_config.get("token_endpoint", "")

        data = {
            "client_id": DEFAULT_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "response_type": IDK_RESPONSE_TYPE_TOKEN,
        }

        _LOGGER.debug("Refreshing IDK tokens")
        async with self._session.post(
            token_endpoint,
            data=data,
            headers=self._token_headers(),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise AuthError(
                    f"Token refresh failed: HTTP {resp.status} - {body}"
                )
            token_response = await resp.json()

        self._tokens[TOKEN_ACCESS] = token_response.get(
            "access_token", self._tokens.get(TOKEN_ACCESS, "")
        )
        self._tokens[TOKEN_ID] = token_response.get(
            "id_token", self._tokens.get(TOKEN_ID, "")
        )
        if token_response.get("refresh_token"):
            self._tokens[TOKEN_REFRESH] = token_response["refresh_token"]
        self._tokens[TOKEN_EXPIRES_IN] = token_response.get("expires_in", 3600)
        self._tokens[TOKEN_EXPIRES_AT] = time.time() + float(
            token_response.get("expires_in", 3600)
        )

        # Re-bridge to MBB with new id_token
        await self._bridge_to_mbb()

        _LOGGER.debug("Tokens refreshed successfully")
        return self._tokens

    async def ensure_valid_token(self) -> str:
        """Ensure we have a valid access token, refreshing if needed."""
        if self.is_token_expired:
            await self.refresh_tokens()
        return self._tokens.get(TOKEN_ACCESS, "")

    def auth_headers(self) -> dict[str, str]:
        """Return headers with Bearer token for BFF API calls."""
        return {
            "Authorization": f"Bearer {self._tokens.get(TOKEN_ACCESS, '')}",
            "User-Agent": HEADER_USER_AGENT,
            "Accept": HEADER_ACCEPT,
            "Content-Type": HEADER_CONTENT_TYPE,
        }

    def mbb_auth_headers(self) -> dict[str, str]:
        """Return headers with MBB Bearer token for legacy API calls."""
        headers = {
            "Authorization": f"Bearer {self._tokens.get(TOKEN_MBB_ACCESS, '')}",
            "User-Agent": HEADER_USER_AGENT,
            "Accept": HEADER_ACCEPT,
            "Content-Type": HEADER_CONTENT_TYPE,
        }
        client_id = self._tokens.get(TOKEN_MBB_CLIENT_ID)
        if client_id:
            headers["X-Client-ID"] = str(client_id)
        return headers
