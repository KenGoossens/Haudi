"""Lock platform for Haudi."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SPIN, DOMAIN
from .entity import HaudiEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Haudi lock entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    spin = entry.data.get(CONF_SPIN)
    entities = [
        HaudiLock(coordinator, vin, spin) for vin in coordinator.vins
    ]
    async_add_entities(entities)


class HaudiLock(HaudiEntity, LockEntity):
    """Representation of the vehicle lock."""

    _attr_translation_key = "vehicle_lock"
    _attr_icon = "mdi:car-key"

    def __init__(self, coordinator, vin: str, spin: str | None) -> None:
        super().__init__(coordinator, vin, "vehicle_lock")
        self._spin = spin

    @property
    def is_locked(self) -> bool | None:
        """Return True if the vehicle is locked."""
        data = self.vehicle_data
        return data.doors_locked if data else None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the vehicle."""
        result = await self.coordinator.api.lock_vehicle(self._vin, self._spin)
        if result:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to lock vehicle %s", self._vin)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the vehicle."""
        if not self._spin:
            _LOGGER.error(
                "SPIN required to unlock vehicle. Configure it in the integration settings"
            )
            return
        result = await self.coordinator.api.unlock_vehicle(self._vin, self._spin)
        if result:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to unlock vehicle %s", self._vin)

    @property
    def available(self) -> bool:
        """Return True if the lock state is known."""
        return super().available and self.is_locked is not None
