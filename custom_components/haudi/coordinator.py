"""Data update coordinator for Haudi."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AudiAPI, AudiAPIError
from .auth import AuthError
from .const import DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HaudiVehicleData:
    """Parsed vehicle data from API responses."""

    def __init__(self, vin: str, raw_status: dict, parking: dict | None) -> None:
        self.vin = vin
        self.raw = raw_status
        self._parking = parking

    # --- Helpers to navigate nested status ---

    def _get_job(self, job_name: str) -> dict:
        """Get a status job's data."""
        # BFF response format: { "<jobName>": { "data": [...] } }
        # or { "<jobName>Data": { ... } }
        job = self.raw.get(job_name, {})
        if isinstance(job, dict):
            return job.get("data", job)
        return {}

    def _get_field(self, job_name: str, field_name: str) -> Any:
        """Get a specific field from a status job."""
        data = self._get_job(job_name)
        if isinstance(data, dict):
            return data.get(field_name)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("id") == field_name:
                    return item.get("value")
        return None

    def _get_value(self, *paths: str) -> Any:
        """Try multiple dot-paths to find a value."""
        for path in paths:
            parts = path.split(".")
            current: Any = self.raw
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    current = None
                    break
            if current is not None:
                return current
        return None

    # --- Measurements ---

    @property
    def mileage_km(self) -> int | None:
        val = self._get_value(
            "measurements.odometerStatus.value.odometer",
            "measurementsData.odometer",
            "measurements.odometer",
        )
        return int(val) if val is not None else None

    @property
    def range_total_km(self) -> int | None:
        val = self._get_value(
            "measurements.rangeStatus.value.totalRange_km",
            "measurementsData.totalRange_km",
            "measurements.totalRange_km",
        )
        return int(val) if val is not None else None

    @property
    def range_electric_km(self) -> int | None:
        val = self._get_value(
            "measurements.rangeStatus.value.electricRange",
            "measurementsData.electricRange",
            "measurements.electricRange",
        )
        return int(val) if val is not None else None

    @property
    def fuel_level_pct(self) -> int | None:
        val = self._get_value(
            "measurements.fuelLevelStatus.value.currentFuelLevel_pct",
            "measurementsData.currentFuelLevel_pct",
            "measurements.currentFuelLevel_pct",
        )
        return int(val) if val is not None else None

    @property
    def state_of_charge_pct(self) -> int | None:
        val = self._get_value(
            "measurements.fuelLevelStatus.value.currentSOC_pct",
            "charging.batteryStatus.value.currentSOC_pct",
            "chargingData.currentSOC_pct",
            "measurements.currentSOC_pct",
        )
        return int(val) if val is not None else None

    # --- Charging ---

    @property
    def charging_state(self) -> str | None:
        return self._get_value(
            "charging.chargingStatus.value.chargingState",
            "chargingData.chargingState",
            "charging.chargingState",
        )

    @property
    def charge_power_kw(self) -> float | None:
        val = self._get_value(
            "charging.chargingStatus.value.chargePower_kW",
            "chargingData.chargePower_kW",
            "charging.chargePower_kW",
        )
        return float(val) if val is not None else None

    @property
    def charge_rate_kmph(self) -> float | None:
        val = self._get_value(
            "charging.chargingStatus.value.chargeRate_kmph",
            "chargingData.chargeRate_kmph",
            "charging.chargeRate_kmph",
        )
        return float(val) if val is not None else None

    @property
    def charge_type(self) -> str | None:
        return self._get_value(
            "charging.chargingStatus.value.chargeType",
            "chargingData.chargeType",
            "charging.chargeType",
        )

    @property
    def remaining_charge_time_min(self) -> int | None:
        val = self._get_value(
            "charging.chargingStatus.value.remainingChargingTimeToComplete_min",
            "chargingData.remainingChargingTimeToComplete_min",
            "charging.remainingChargingTimeToComplete_min",
        )
        return int(val) if val is not None else None

    @property
    def plug_connected(self) -> bool | None:
        val = self._get_value(
            "charging.plugStatus.value.plugConnectionState",
            "chargingData.plugConnectionState",
            "charging.plugConnectionState",
        )
        if val is None:
            return None
        return str(val).lower() in ("connected", "true", "1")

    @property
    def plug_locked(self) -> bool | None:
        val = self._get_value(
            "charging.plugStatus.value.plugLockState",
            "chargingData.plugLockState",
            "charging.plugLockState",
        )
        if val is None:
            return None
        return str(val).lower() in ("locked", "true", "1")

    # --- Climatisation ---

    @property
    def climatisation_state(self) -> str | None:
        return self._get_value(
            "climatisation.climatisationStatus.value.climatisationState",
            "climatisationData.climatisationState",
            "climatisation.climatisationState",
        )

    @property
    def climatisation_active(self) -> bool:
        state = self.climatisation_state
        if state is None:
            return False
        return str(state).lower() in (
            "cooling",
            "heating",
            "ventilation",
            "heating_auxiliary",
        )

    @property
    def target_temperature_c(self) -> float | None:
        val = self._get_value(
            "climatisation.climatisationSettings.value.targetTemperature_C",
            "climatisationData.targetTemperature_C",
            "climatisation.targetTemperature_C",
        )
        return float(val) if val is not None else None

    @property
    def remaining_climatisation_min(self) -> int | None:
        val = self._get_value(
            "climatisation.climatisationStatus.value.remainingClimatisationTime_min",
            "climatisationData.remainingClimatisationTime_min",
            "climatisation.remainingClimatisationTime_min",
        )
        return int(val) if val is not None else None

    # --- Access (doors/locks) ---

    @property
    def doors_locked(self) -> bool | None:
        val = self._get_value(
            "access.accessStatus.value.overallStatus",
            "accessData.overallStatus",
            "access.overallStatus",
        )
        if val is None:
            return None
        return str(val).lower() in ("locked", "safe", "true", "1")

    @property
    def doors_closed(self) -> bool | None:
        val = self._get_value(
            "access.accessStatus.value.doorStatus",
            "accessData.doorStatus",
        )
        if isinstance(val, dict):
            return all(
                str(v).lower() in ("closed", "true", "1")
                for v in val.values()
            )
        return None

    @property
    def trunk_open(self) -> bool | None:
        val = self._get_value(
            "access.accessStatus.value.trunk",
            "accessData.trunk",
        )
        if val is None:
            return None
        return str(val).lower() in ("open", "true", "1")

    @property
    def hood_open(self) -> bool | None:
        val = self._get_value(
            "access.accessStatus.value.bonnet",
            "accessData.bonnet",
        )
        if val is None:
            return None
        return str(val).lower() in ("open", "true", "1")

    # --- Lights ---

    @property
    def lights_on(self) -> bool | None:
        val = self._get_value(
            "lights.lightsStatus.value.overallStatus",
            "lightsData.overallStatus",
            "lights.overallStatus",
        )
        if val is None:
            return None
        return str(val).lower() in ("on", "true", "1")

    # --- Oil ---

    @property
    def oil_level_pct(self) -> int | None:
        val = self._get_value(
            "oilLevel.oilLevelStatus.value.value",
            "oilLevelData.value",
            "oilLevel.value",
        )
        return int(val) if val is not None else None

    # --- Parking position ---

    @property
    def latitude(self) -> float | None:
        if self._parking:
            val = (
                self._parking.get("data", self._parking).get("latitude")
                or self._parking.get("lat")
            )
            return float(val) if val is not None else None
        return None

    @property
    def longitude(self) -> float | None:
        if self._parking:
            val = (
                self._parking.get("data", self._parking).get("longitude")
                or self._parking.get("lon")
            )
            return float(val) if val is not None else None
        return None


class HaudiCoordinator(DataUpdateCoordinator[dict[str, HaudiVehicleData]]):
    """Coordinator to poll vehicle data from Audi APIs."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: AudiAPI,
        vins: list[str],
        update_interval: int = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Haudi",
            update_interval=timedelta(seconds=update_interval),
        )
        self.api = api
        self.vins = vins

    async def _async_update_data(self) -> dict[str, HaudiVehicleData]:
        """Fetch data for all vehicles."""
        data: dict[str, HaudiVehicleData] = {}

        for vin in self.vins:
            try:
                status = await self.api.get_vehicle_status(vin)
                parking = await self.api.get_parking_position(vin)
                data[vin] = HaudiVehicleData(vin, status, parking)
            except AuthError as err:
                raise UpdateFailed(f"Authentication error: {err}") from err
            except AudiAPIError as err:
                _LOGGER.warning("Failed to update %s: %s", vin, err)
                # Keep old data for this VIN if available
                if self.data and vin in self.data:
                    data[vin] = self.data[vin]

        return data
