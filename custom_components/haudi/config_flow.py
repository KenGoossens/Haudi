"""Config flow for Haudi (myAudi Connect).

Uses a browser-based OAuth2 flow (no HTML scraping):

1. User picks a region and optionally enters their S-PIN.
2. We generate an authorize URL and show it to the user.
3. User opens the link in their browser, logs in via VW Group.
4. Browser redirects to  myaudi:///...?code=XYZ  – browser shows an error.
5. User copies the full redirect URL and pastes it back here.
6. We exchange the code for tokens.  Done.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import AudiAuth, AuthError, PKCEState, extract_code_from_url
from .const import CONF_REGION, CONF_SPIN, DOMAIN, REGIONS

_LOGGER = logging.getLogger(__name__)


class HaudiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Haudi."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        super().__init__()
        self._auth: AudiAuth | None = None
        self._pkce: PKCEState | None = None
        self._region: str = "emea"
        self._spin: str | None = None

    # ── Step 1: region + optional SPIN ───────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step – region selection."""
        if user_input is not None:
            self._region = user_input.get(CONF_REGION, "emea")
            self._spin = user_input.get(CONF_SPIN)
            return await self.async_step_browser()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SPIN): str,
                    vol.Optional(CONF_REGION, default="emea"): vol.In(REGIONS),
                }
            ),
        )

    # ── Step 2: show authorize URL ───────────────────────────────────

    async def async_step_browser(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the user an authorize URL to open in their browser."""
        session = async_get_clientsession(self.hass)
        self._auth = AudiAuth(session, self._region)

        try:
            authorize_url, self._pkce = await self._auth.generate_authorize_url()
        except AuthError as err:
            _LOGGER.error("Failed to generate authorize URL: %s", err)
            return self.async_abort(reason="cannot_connect")
        except aiohttp.ClientError:
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="callback",
            data_schema=vol.Schema(
                {vol.Required("redirect_url"): str}
            ),
            description_placeholders={"authorize_url": authorize_url},
        )

    # ── Step 3: user pastes the redirect URL ─────────────────────────

    async def async_step_callback(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pasted redirect URL containing the auth code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            redirect_url = user_input.get("redirect_url", "").strip()
            code = extract_code_from_url(redirect_url)

            if not code:
                errors["redirect_url"] = "no_code"
            elif self._auth is None or self._pkce is None:
                errors["base"] = "unknown"
            else:
                try:
                    tokens = await self._auth.exchange_code(code, self._pkce)
                except AuthError as err:
                    _LOGGER.error("Token exchange failed: %s", err)
                    errors["base"] = "invalid_auth"
                except aiohttp.ClientError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during token exchange")
                    errors["base"] = "unknown"
                else:
                    # Prevent duplicate entries – unique per refresh token
                    unique = tokens.get("refresh_token", "")
                    if unique:
                        await self.async_set_unique_id(str(hash(unique)))
                        self._abort_if_unique_id_configured()

                    data: dict[str, Any] = {
                        CONF_REGION: self._region,
                        "tokens": tokens,
                    }
                    if self._spin:
                        data[CONF_SPIN] = self._spin

                    return self.async_create_entry(
                        title="myAudi",
                        data=data,
                    )

        return self.async_show_form(
            step_id="callback",
            data_schema=vol.Schema(
                {vol.Required("redirect_url"): str}
            ),
            errors=errors,
        )

