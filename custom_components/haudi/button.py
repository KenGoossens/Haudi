"""Button platform for Haudi."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import HaudiEntity

_LOGGER = logging.getLogger(__name__)

BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="force_refresh",
        translation_key="force_refresh",
        icon="mdi:refresh",
    ),
    ButtonEntityDescription(
        key="vehicle_wakeup",
        translation_key="vehicle_wakeup",
        icon="mdi:power",
    ),
    ButtonEntityDescription(
        key="start_climate",
        translation_key="start_climate",
        icon="mdi:air-conditioner",
    ),
    ButtonEntityDescription(
        key="stop_climate",
        translation_key="stop_climate",
        icon="mdi:air-conditioner",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Haudi button entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[HaudiButton] = []

    for vin in coordinator.vins:
        for desc in BUTTON_DESCRIPTIONS:
            entities.append(HaudiButton(coordinator, vin, desc))

    async_add_entities(entities)


class HaudiButton(HaudiEntity, ButtonEntity):
    """Representation of a Haudi action button."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator,
        vin: str,
        description: ButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator, vin, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle button press."""
        key = self.entity_description.key

        if key == "force_refresh":
            await self.coordinator.async_request_refresh()
        elif key == "vehicle_wakeup":
            await self.coordinator.api.wakeup_vehicle(self._vin)
            await self.coordinator.async_request_refresh()
        elif key == "start_climate":
            await self.coordinator.api.start_climatisation(self._vin)
            await self.coordinator.async_request_refresh()
        elif key == "stop_climate":
            await self.coordinator.api.stop_climatisation(self._vin)
            await self.coordinator.async_request_refresh()
