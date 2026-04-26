"""Climate platform for Haudi."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HaudiConfigEntry
from .entity import HaudiEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaudiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Haudi climate entities."""
    coordinator = entry.runtime_data
    entities = [
        HaudiClimate(coordinator, vin) for vin in coordinator.vins
    ]
    async_add_entities(entities)


class HaudiClimate(HaudiEntity, ClimateEntity):
    """Representation of the vehicle's climate control."""

    _attr_translation_key = "climatisation"
    _attr_icon = "mdi:air-conditioner"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "climatisation")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        data = self.vehicle_data
        if data and data.climatisation_active:
            return HVACMode.AUTO
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        data = self.vehicle_data
        if not data:
            return None
        state = data.climatisation_state
        if state is None:
            return None
        state_lower = str(state).lower()
        if state_lower == "cooling":
            return HVACAction.COOLING
        if state_lower in ("heating", "heating_auxiliary"):
            return HVACAction.HEATING
        if state_lower == "ventilation":
            return HVACAction.FAN
        return HVACAction.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature (not available from API)."""
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        data = self.vehicle_data
        return data.target_temperature_c if data else None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.api.stop_climatisation(self._vin)
        elif hvac_mode == HVACMode.AUTO:
            await self.coordinator.api.start_climatisation(self._vin)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.coordinator.api.start_climatisation(
                self._vin, target_temp=float(temp)
            )
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on climate."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Turn off climate."""
        await self.async_set_hvac_mode(HVACMode.OFF)
