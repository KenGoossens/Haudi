"""API client for Haudi - communicates with Audi/CARIAD vehicle APIs."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import aiohttp

from .auth import AudiAuth, AuthError
from .const import (
    BFF_BASE_URLS,
    MBB_MAL_BASE_URL,
    MBB_OAUTH_BASE_URL,
    SPIN_COMPLETE_PATH,
    SPIN_PREPARE_PATH,
    STATUS_JOBS,
    VEHICLE_CLIMATE_SETTINGS_PATH,
    VEHICLE_CLIMATE_START_PATH,
    VEHICLE_CLIMATE_STOP_PATH,
    VEHICLE_LOCK_PATH,
    VEHICLE_PARKING_PATH,
    VEHICLE_STATUS_PATH,
    VEHICLE_UNLOCK_PATH,
    VEHICLE_WAKEUP_PATH,
)

_LOGGER = logging.getLogger(__name__)


class AudiAPIError(Exception):
    """API call error."""


class AudiAPI:
    """Client for Audi/CARIAD vehicle APIs."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth: AudiAuth,
        region: str = "emea",
    ) -> None:
        self._session = session
        self._auth = auth
        self._region = region
        self._bff_base = BFF_BASE_URLS[region]

    async def _request(
        self,
        method: str,
        url: str,
        *,
        use_mbb: bool = False,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> dict | list | None:
        """Make an authenticated API request."""
        await self._auth.ensure_valid_token()

        headers = self._auth.mbb_auth_headers() if use_mbb else self._auth.auth_headers()

        kwargs: dict[str, Any] = {"headers": headers}
        if json_data is not None:
            kwargs["json"] = json_data
        if params is not None:
            kwargs["params"] = params

        async with self._session.request(method, url, **kwargs) as resp:
            if resp.status == 401:
                # Token expired mid-request, refresh and retry once
                _LOGGER.debug("Got 401, refreshing tokens and retrying")
                await self._auth.refresh_tokens()
                headers = (
                    self._auth.mbb_auth_headers()
                    if use_mbb
                    else self._auth.auth_headers()
                )
                kwargs["headers"] = headers
                async with self._session.request(method, url, **kwargs) as retry_resp:
                    if retry_resp.status == 204:
                        return None
                    if retry_resp.status >= 400:
                        body = await retry_resp.text()
                        raise AudiAPIError(
                            f"API request failed after retry: HTTP {retry_resp.status} - {body}"
                        )
                    return await retry_resp.json()
            if resp.status == 204:
                return None
            if resp.status >= 400:
                body = await resp.text()
                raise AudiAPIError(
                    f"API request failed: HTTP {resp.status} - {body}"
                )
            return await resp.json()

    # --- Vehicle discovery ---

    async def get_vehicles(self) -> list[dict]:
        """Get list of vehicles associated with the account.

        Tries the BFF user endpoint first, then falls back to MAL.
        """
        # Try BFF user endpoint for vehicle list
        url = f"{self._bff_base}/user/v1"
        try:
            result = await self._request("GET", url)
            if result and isinstance(result, dict):
                vehicles = result.get("vehicles", [])
                if vehicles:
                    return vehicles
                # Some responses nest vehicles differently
                user_data = result.get("data", result)
                if isinstance(user_data, dict):
                    vehicles = user_data.get("vehicles", [])
                    if vehicles:
                        return vehicles
        except AudiAPIError:
            _LOGGER.debug("BFF user endpoint failed, trying alternatives")

        # Try MAL vehicles endpoint
        try:
            url = f"{MBB_MAL_BASE_URL}/usermanagement/users/v1/vehicles"
            result = await self._request("GET", url, use_mbb=True)
            if result and isinstance(result, dict):
                vehicle_list = result.get("userVehicles", {}).get("vehicle", [])
                return vehicle_list
        except AudiAPIError:
            _LOGGER.debug("MAL vehicle list failed")

        return []

    # --- Vehicle status ---

    async def get_vehicle_status(self, vin: str) -> dict:
        """Get selective vehicle status (all available data)."""
        url = self._bff_base + VEHICLE_STATUS_PATH.format(vin=vin)
        params = {"jobs": ",".join(STATUS_JOBS)}

        try:
            result = await self._request("GET", url, params=params)
            return result if isinstance(result, dict) else {}
        except AudiAPIError as err:
            _LOGGER.error("Failed to get vehicle status for %s: %s", vin, err)
            return {}

    async def get_parking_position(self, vin: str) -> dict | None:
        """Get vehicle parking position (lat/lon)."""
        url = self._bff_base + VEHICLE_PARKING_PATH.format(vin=vin)
        try:
            result = await self._request("GET", url)
            return result if isinstance(result, dict) else None
        except AudiAPIError:
            _LOGGER.debug("No parking position available for %s", vin)
            return None

    # --- Climate control ---

    async def start_climatisation(
        self,
        vin: str,
        target_temp: float | None = None,
    ) -> bool:
        """Start vehicle climatisation/pre-conditioning."""
        url = self._bff_base + VEHICLE_CLIMATE_START_PATH.format(vin=vin)
        json_data = None
        if target_temp is not None:
            json_data = {
                "targetTemperature": target_temp,
                "targetTemperatureUnit": "celsius",
            }
        try:
            await self._request("POST", url, json_data=json_data)
            return True
        except AudiAPIError as err:
            _LOGGER.error("Failed to start climatisation: %s", err)
            return False

    async def stop_climatisation(self, vin: str) -> bool:
        """Stop vehicle climatisation."""
        url = self._bff_base + VEHICLE_CLIMATE_STOP_PATH.format(vin=vin)
        try:
            await self._request("POST", url)
            return True
        except AudiAPIError as err:
            _LOGGER.error("Failed to stop climatisation: %s", err)
            return False

    async def set_climatisation_settings(
        self, vin: str, settings: dict
    ) -> bool:
        """Update climatisation settings."""
        url = self._bff_base + VEHICLE_CLIMATE_SETTINGS_PATH.format(vin=vin)
        try:
            await self._request("PUT", url, json_data=settings)
            return True
        except AudiAPIError as err:
            _LOGGER.error("Failed to update climate settings: %s", err)
            return False

    # --- Lock/Unlock ---

    async def _prepare_spin(self, spin: str) -> tuple[str, str]:
        """Prepare SPIN challenge-response.

        Returns (security_token, hashed_pin).
        """
        url = MBB_MAL_BASE_URL + SPIN_PREPARE_PATH
        try:
            result = await self._request("POST", url, use_mbb=True)
        except AudiAPIError as err:
            raise AudiAPIError(f"SPIN prepare failed: {err}") from err

        if not isinstance(result, dict):
            raise AudiAPIError("Invalid SPIN prepare response")

        sec_pin_auth = result.get("securityPinAuthInfo", result)
        challenge = sec_pin_auth.get("securityPinTransmission", {}).get(
            "challenge", ""
        )
        security_token = sec_pin_auth.get("securityToken", "")

        if not challenge or not security_token:
            raise AudiAPIError("SPIN challenge or token missing from response")

        # Hash: SHA512(challenge + SHA512(pin))
        pin_hash = hashlib.sha512(spin.encode()).hexdigest().upper()
        combined_hash = (
            hashlib.sha512((challenge + pin_hash).encode()).hexdigest().upper()
        )

        return security_token, combined_hash

    async def _complete_spin(
        self, security_token: str, challenge: str, pin_hash: str
    ) -> str:
        """Complete SPIN authentication, return security token for action."""
        url = MBB_MAL_BASE_URL + SPIN_COMPLETE_PATH
        json_data = {
            "securityPinAuthentication": {
                "securityPin": {
                    "challenge": challenge,
                    "securityPinHash": pin_hash,
                },
                "securityToken": security_token,
            }
        }
        try:
            result = await self._request("POST", url, json_data=json_data, use_mbb=True)
            if isinstance(result, dict):
                return result.get("securityToken", security_token)
            return security_token
        except AudiAPIError as err:
            raise AudiAPIError(f"SPIN verification failed: {err}") from err

    async def lock_vehicle(self, vin: str, spin: str | None = None) -> bool:
        """Lock the vehicle. May require SPIN."""
        url = self._bff_base + VEHICLE_LOCK_PATH.format(vin=vin)
        json_data: dict[str, Any] = {}
        if spin:
            json_data["spin"] = spin
        try:
            await self._request("POST", url, json_data=json_data or None)
            return True
        except AudiAPIError as err:
            _LOGGER.error("Failed to lock vehicle: %s", err)
            return False

    async def unlock_vehicle(self, vin: str, spin: str | None = None) -> bool:
        """Unlock the vehicle. Requires SPIN."""
        url = self._bff_base + VEHICLE_UNLOCK_PATH.format(vin=vin)
        json_data: dict[str, Any] = {}
        if spin:
            json_data["spin"] = spin
        try:
            await self._request("POST", url, json_data=json_data or None)
            return True
        except AudiAPIError as err:
            _LOGGER.error("Failed to unlock vehicle: %s", err)
            return False

    # --- Other actions ---

    async def wakeup_vehicle(self, vin: str) -> bool:
        """Send vehicle wakeup command."""
        url = self._bff_base + VEHICLE_WAKEUP_PATH.format(vin=vin)
        try:
            await self._request("POST", url)
            return True
        except AudiAPIError as err:
            _LOGGER.error("Failed to wakeup vehicle: %s", err)
            return False
