"""Binary sensor platform for Haudi."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HaudiVehicleData
from .entity import HaudiEntity


@dataclass(frozen=True, kw_only=True)
class HaudiBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Haudi binary sensor."""

    value_fn: Callable[[HaudiVehicleData], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[HaudiBinarySensorDescription, ...] = (
    HaudiBinarySensorDescription(
        key="doors_locked",
        translation_key="doors_locked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda d: not d.doors_locked if d.doors_locked is not None else None,
    ),
    HaudiBinarySensorDescription(
        key="doors_closed",
        translation_key="doors_closed",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: not d.doors_closed if d.doors_closed is not None else None,
    ),
    HaudiBinarySensorDescription(
        key="trunk_open",
        translation_key="trunk_open",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:car-back",
        value_fn=lambda d: d.trunk_open,
    ),
    HaudiBinarySensorDescription(
        key="hood_open",
        translation_key="hood_open",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:car",
        value_fn=lambda d: d.hood_open,
    ),
    HaudiBinarySensorDescription(
        key="plug_connected",
        translation_key="plug_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda d: d.plug_connected,
    ),
    HaudiBinarySensorDescription(
        key="plug_locked",
        translation_key="plug_locked",
        device_class=BinarySensorDeviceClass.LOCK,
        icon="mdi:ev-plug-type2",
        value_fn=lambda d: (
            not d.plug_locked if d.plug_locked is not None else None
        ),
    ),
    HaudiBinarySensorDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d: (
            str(d.charging_state).lower() == "charging"
            if d.charging_state
            else None
        ),
    ),
    HaudiBinarySensorDescription(
        key="lights_on",
        translation_key="lights_on",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda d: d.lights_on,
    ),
    HaudiBinarySensorDescription(
        key="climatisation_active",
        translation_key="climatisation_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:air-conditioner",
        value_fn=lambda d: d.climatisation_active,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Haudi binary sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[HaudiBinarySensor] = []

    for vin in coordinator.vins:
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            entities.append(HaudiBinarySensor(coordinator, vin, desc))

    async_add_entities(entities)


class HaudiBinarySensor(HaudiEntity, BinarySensorEntity):
    """Representation of a Haudi binary sensor."""

    entity_description: HaudiBinarySensorDescription

    def __init__(
        self,
        coordinator,
        vin: str,
        description: HaudiBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, vin, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        data = self.vehicle_data
        if data is None:
            return None
        return self.entity_description.value_fn(data)

    @property
    def available(self) -> bool:
        """Return True if value is available."""
        return super().available and self.is_on is not None
