"""Device tracker platform for Haudi."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HaudiConfigEntry
from .entity import HaudiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaudiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Haudi device tracker entities."""
    coordinator = entry.runtime_data
    entities = [
        HaudiDeviceTracker(coordinator, vin) for vin in coordinator.vins
    ]
    async_add_entities(entities)


class HaudiDeviceTracker(HaudiEntity, TrackerEntity):
    """Representation of the vehicle's parking position."""

    _attr_translation_key = "parking_position"
    _attr_icon = "mdi:car-connected"

    def __init__(self, coordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "parking_position")

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        data = self.vehicle_data
        return data.latitude if data else None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        data = self.vehicle_data
        return data.longitude if data else None

    @property
    def available(self) -> bool:
        """Return True if GPS position is available."""
        return super().available and self.latitude is not None
