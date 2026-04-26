"""The Haudi (myAudi Connect) integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AudiAPI
from .auth import AudiAuth, AuthError
from .const import CONF_REGION, CONF_SPIN, CONF_VIN, DOMAIN, PLATFORMS
from .coordinator import HaudiCoordinator

_LOGGER = logging.getLogger(__name__)

type HaudiConfigEntry = ConfigEntry[HaudiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HaudiConfigEntry) -> bool:
    """Set up Haudi from a config entry."""
    session = async_get_clientsession(hass)
    region = entry.data.get(CONF_REGION, "emea")

    auth = AudiAuth(session, region)

    # Restore tokens from config entry (set during config flow)
    tokens = entry.data.get("tokens", {})
    if not tokens:
        _LOGGER.error("No tokens stored – please re-authenticate via config flow")
        return False
    auth.tokens = dict(tokens)

    # Refresh if expired (uses refresh_token, no browser needed)
    if auth.is_token_expired:
        try:
            tokens = await auth.refresh_tokens()
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, "tokens": tokens},
            )
        except AuthError:
            _LOGGER.exception(
                "Token refresh failed – please re-authenticate via config flow"
            )
            return False

    api = AudiAPI(session, auth, region)

    # Get VIN list
    vins = entry.data.get(CONF_VIN, [])
    if isinstance(vins, str):
        vins = [vins]

    if not vins:
        # Discover vehicles
        try:
            vehicles = await api.get_vehicles()
            vins = []
            for v in vehicles:
                vin = v.get("vin") or v.get("VIN") or v.get("vehicleIdentificationNumber", "")
                if vin:
                    vins.append(vin)
            if vins:
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_VIN: vins},
                )
        except Exception:
            _LOGGER.exception("Failed to discover vehicles")
            return False

    if not vins:
        _LOGGER.error("No vehicles found for this account")
        return False

    coordinator = HaudiCoordinator(hass, api, vins)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register token refresh listener
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: _persist_tokens(hass, entry, auth)
        )
    )

    return True


def _persist_tokens(
    hass: HomeAssistant, entry: ConfigEntry, auth: AudiAuth
) -> None:
    """Persist updated tokens to config entry."""
    if auth.tokens:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "tokens": auth.tokens},
        )


async def async_unload_entry(hass: HomeAssistant, entry: HaudiConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
