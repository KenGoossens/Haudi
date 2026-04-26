"""Base entity for Haudi integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HaudiCoordinator, HaudiVehicleData


class HaudiEntity(CoordinatorEntity[HaudiCoordinator]):
    """Base class for Haudi entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HaudiCoordinator,
        vin: str,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._vin = vin
        self._attr_unique_id = f"{vin}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=f"Audi {vin[-6:]}",
            manufacturer="Audi",
            model="Vehicle",
            serial_number=vin,
        )

    @property
    def vehicle_data(self) -> HaudiVehicleData | None:
        """Return vehicle data for this entity's VIN."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._vin)
        return None
