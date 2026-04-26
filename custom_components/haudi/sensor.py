"""Sensor platform for Haudi."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HaudiConfigEntry
from .coordinator import HaudiVehicleData
from .entity import HaudiEntity


@dataclass(frozen=True, kw_only=True)
class HaudiSensorDescription(SensorEntityDescription):
    """Describe a Haudi sensor."""

    value_fn: Callable[[HaudiVehicleData], Any]


SENSOR_DESCRIPTIONS: tuple[HaudiSensorDescription, ...] = (
    HaudiSensorDescription(
        key="state_of_charge",
        translation_key="state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.state_of_charge_pct,
    ),
    HaudiSensorDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-station",
        value_fn=lambda d: d.fuel_level_pct,
    ),
    HaudiSensorDescription(
        key="range_electric",
        translation_key="range_electric",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ev-station",
        value_fn=lambda d: d.range_electric_km,
    ),
    HaudiSensorDescription(
        key="range_total",
        translation_key="range_total",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
        value_fn=lambda d: d.range_total_km,
    ),
    HaudiSensorDescription(
        key="mileage",
        translation_key="mileage",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        value_fn=lambda d: d.mileage_km,
    ),
    HaudiSensorDescription(
        key="charge_power",
        translation_key="charge_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.charge_power_kw,
    ),
    HaudiSensorDescription(
        key="charge_rate",
        translation_key="charge_rate",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
        value_fn=lambda d: d.charge_rate_kmph,
    ),
    HaudiSensorDescription(
        key="remaining_charge_time",
        translation_key="remaining_charge_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline",
        value_fn=lambda d: d.remaining_charge_time_min,
    ),
    HaudiSensorDescription(
        key="charging_state",
        translation_key="charging_state",
        icon="mdi:ev-plug-type2",
        value_fn=lambda d: d.charging_state,
    ),
    HaudiSensorDescription(
        key="charge_type",
        translation_key="charge_type",
        icon="mdi:ev-plug-type2",
        value_fn=lambda d: d.charge_type,
    ),
    HaudiSensorDescription(
        key="climatisation_state",
        translation_key="climatisation_state",
        icon="mdi:air-conditioner",
        value_fn=lambda d: d.climatisation_state,
    ),
    HaudiSensorDescription(
        key="oil_level",
        translation_key="oil_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:oil",
        value_fn=lambda d: d.oil_level_pct,
    ),
    HaudiSensorDescription(
        key="remaining_climatisation_time",
        translation_key="remaining_climatisation_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline",
        value_fn=lambda d: d.remaining_climatisation_min,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaudiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Haudi sensor entities."""
    coordinator = entry.runtime_data
    entities: list[HaudiSensor] = []

    for vin in coordinator.vins:
        for desc in SENSOR_DESCRIPTIONS:
            entities.append(HaudiSensor(coordinator, vin, desc))

    async_add_entities(entities)


class HaudiSensor(HaudiEntity, SensorEntity):
    """Representation of a Haudi sensor."""

    entity_description: HaudiSensorDescription

    def __init__(
        self,
        coordinator: HaudiCoordinator,
        vin: str,
        description: HaudiSensorDescription,
    ) -> None:
        super().__init__(coordinator, vin, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        data = self.vehicle_data
        if data is None:
            return None
        return self.entity_description.value_fn(data)

    @property
    def available(self) -> bool:
        """Return True if value is available."""
        return super().available and self.native_value is not None
