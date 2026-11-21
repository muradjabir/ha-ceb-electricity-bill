"""Sensor platform for CEB Electricity Bill integration."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .calculator import (
    calculate_ceb_bill,
    calculate_predicted_consumption,
    get_billing_cycle,
)
from .const import (
    DOMAIN,
    CONF_ACCOUNT_NUMBER,
    CONF_KWH_ENTITY,
    CONF_BILLING_DAY,
    CONF_IS_CUMULATIVE,
    DEFAULT_BILLING_DAY,
)
from .coordinator import CEBBillCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CEB sensors from config entry."""
    coordinator: CEBBillCoordinator = hass.data[DOMAIN][entry.entry_id]
    account_no = entry.data[CONF_ACCOUNT_NUMBER]

    kwh_entity_id = entry.options.get(
        CONF_KWH_ENTITY, entry.data.get(CONF_KWH_ENTITY)
    )
    billing_day = int(
        entry.options.get(
            CONF_BILLING_DAY, entry.data.get(CONF_BILLING_DAY, DEFAULT_BILLING_DAY)
        )
    )
    is_cumulative = entry.options.get(
        CONF_IS_CUMULATIVE, entry.data.get(CONF_IS_CUMULATIVE)
    )

    calculated_sensor = CEBCalculatedBillSensor(
        coordinator,
        account_no,
        entry.entry_id,
        kwh_entity_id,
        billing_day,
        is_cumulative,
    )
    predicted_sensor = CEBPredictedBillSensor(
        coordinator,
        account_no,
        entry.entry_id,
        calculated_sensor,
    )

    entities: list[SensorEntity] = [
        CEBBillSensor(coordinator, account_no, entry.entry_id),
        calculated_sensor,
        predicted_sensor,
    ]

    async_add_entities(entities)


class CEBBillSensor(CoordinatorEntity[CEBBillCoordinator], SensorEntity):
    """Representation of CEB Electricity Bill Balance Sensor from InstantPay portal."""

    _attr_has_entity_name = True
    _attr_translation_key = "bill_balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "LKR"
    _attr_icon = "mdi:lightning-bolt-circle"
    _unrecorded_attributes = frozenset({"customer_name"})

    def __init__(
        self,
        coordinator: CEBBillCoordinator,
        account_number: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_unique_id = f"ceb_bill_{account_number}"
        self._attr_name = "Electricity Bill Balance"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_number)},
            name=f"CEB Account {account_number}",
            manufacturer="Ceylon Electricity Board",
            model="InstantPay Bill Account",
            entry_type=None,
        )

    @property
    def native_value(self) -> float | None:
        """Return the current balance."""
        if self.coordinator.data:
            return self.coordinator.data.get("balance")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "account_number": self._account_number,
            "customer_name": self.coordinator.data.get("customer_name"),
            "bill_date": self.coordinator.data.get("bill_date"),
            "last_synced": self.coordinator.data.get("last_synced"),
        }


class CEBCalculatedBillSensor(CoordinatorEntity[CEBBillCoordinator], RestoreSensor):
    """Calculated CEB Electricity Bill sensor based on kWh consumed and billing cycle."""

    _attr_has_entity_name = True
    _attr_translation_key = "calculated_bill"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "LKR"
    _attr_icon = "mdi:calculator-variant-outline"

    def __init__(
        self,
        coordinator: CEBBillCoordinator,
        account_number: str,
        entry_id: str,
        kwh_entity_id: str | None,
        billing_day: int,
        is_cumulative: bool | None = None,
    ) -> None:
        """Initialize the calculated bill sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._entry_id = entry_id
        self._kwh_entity_id = kwh_entity_id
        self._billing_day = billing_day
        self._is_cumulative = is_cumulative
        self._cycle_start_kwh: float | None = None
        self._cycle_start_date: str | None = None
        self._attr_unique_id = f"ceb_bill_{account_number}_calculated_bill"
        self._attr_name = "Calculated Electricity Bill"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_number)},
            name=f"CEB Account {account_number}",
            manufacturer="Ceylon Electricity Board",
            model="InstantPay Bill Account",
            entry_type=None,
        )
        self._calc_result: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Register state listener, restore state, and link sensor to coordinator."""
        await super().async_added_to_hass()
        self.coordinator.calculated_bill_sensor = self

        cycle = get_billing_cycle(date.today(), self._billing_day)
        cycle_start_str = cycle["cycle_start"].isoformat()

        if (last_state := await self.async_get_last_state()) is not None:
            attrs = last_state.attributes
            restored_start = attrs.get("billing_cycle_start")
            restored_reading = attrs.get("cycle_start_reading")
            if restored_start == cycle_start_str and restored_reading is not None:
                self._cycle_start_date = str(restored_start)
                try:
                    self._cycle_start_kwh = float(restored_reading)
                except (ValueError, TypeError):
                    self._cycle_start_kwh = None

        if self._kwh_entity_id:
            async def _async_on_kwh_state_change(event: Any) -> None:
                """Handle external sensor state change."""
                await self._async_update_calculation()
                self.async_write_ha_state()

            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._kwh_entity_id], _async_on_kwh_state_change
                )
            )

        await self._async_update_calculation()

    async def _async_fetch_cycle_start_reading(self, start_date: date) -> float | None:
        """Fetch reading at the beginning of the billing cycle from HA recorder statistics."""
        if not self._kwh_entity_id:
            return None
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period
            from homeassistant.util import dt as dt_util

            tz = dt_util.get_time_zone(self.hass.config.time_zone) or dt_util.DEFAULT_TIME_ZONE
            start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=tz)

            def _get_stats():
                for end in (start_dt + timedelta(hours=6), None):
                    res = statistics_during_period(
                        self.hass,
                        start_dt,
                        end,
                        {self._kwh_entity_id},
                        "hour",
                        None,
                        {"state", "sum"},
                    )
                    if res and res.get(self._kwh_entity_id):
                        return res
                return {}

            recorder_instance = get_instance(self.hass)
            stats = await recorder_instance.async_add_executor_job(_get_stats)
            if stats and self._kwh_entity_id in stats and stats[self._kwh_entity_id]:
                first_row = stats[self._kwh_entity_id][0]
                val = first_row.get("state")
                if val is None:
                    val = first_row.get("sum")
                if val is not None:
                    return float(val)
        except Exception as err:
            _LOGGER.debug(
                "Could not fetch recorder statistics for %s: %s",
                self._kwh_entity_id,
                err,
            )
        return None

    async def _async_update_calculation(self) -> None:
        """Calculate bill from kWh consumption and billing cycle."""
        raw_value: float = 0.0
        unit: str | None = None
        is_cumul: bool | None = self._is_cumulative

        if self._kwh_entity_id:
            state = self.hass.states.get(self._kwh_entity_id)
            if state is not None and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    raw_value = float(state.state)
                except (ValueError, TypeError):
                    raw_value = 0.0

                unit = state.attributes.get("unit_of_measurement")
                if unit == "Wh":
                    raw_value = raw_value / 1000.0
                elif unit == "MWh":
                    raw_value = raw_value * 1000.0

                # Auto-detect if not explicitly configured
                if is_cumul is None:
                    state_class = state.attributes.get("state_class")
                    dev_class = state.attributes.get("device_class")
                    is_cumul = (
                        state_class in (
                            SensorStateClass.TOTAL,
                            SensorStateClass.TOTAL_INCREASING,
                            "total",
                            "total_increasing",
                        )
                        or dev_class == SensorDeviceClass.ENERGY
                    ) and not self._kwh_entity_id.startswith(("number.", "input_number."))
        elif hasattr(self.coordinator, "manual_kwh"):
            raw_value = float(self.coordinator.manual_kwh)
            if is_cumul is None:
                is_cumul = False

        if is_cumul is None:
            is_cumul = False

        cycle = get_billing_cycle(date.today(), self._billing_day)
        cycle_start_str = cycle["cycle_start"].isoformat()

        if is_cumul:
            # Query baseline if cycle changed or not yet determined
            if self._cycle_start_date != cycle_start_str or self._cycle_start_kwh is None:
                baseline = await self._async_fetch_cycle_start_reading(cycle["cycle_start"])
                if baseline is not None:
                    if unit == "Wh":
                        baseline = baseline / 1000.0
                    elif unit == "MWh":
                        baseline = baseline * 1000.0
                    self._cycle_start_kwh = baseline
                    self._cycle_start_date = cycle_start_str
                elif self._cycle_start_kwh is None:
                    self._cycle_start_kwh = raw_value
                    self._cycle_start_date = cycle_start_str
                else:
                    self._cycle_start_date = cycle_start_str

            kwh = max(0.0, raw_value - (self._cycle_start_kwh or 0.0))
        else:
            kwh = max(0.0, raw_value)

        bill = calculate_ceb_bill(kwh, days_in_cycle=cycle["days_in_cycle"])

        # Calculate predicted bill based on average daily consumption
        try:
            from homeassistant.util import dt as dt_util
            tz = dt_util.get_time_zone(self.hass.config.time_zone) or dt_util.DEFAULT_TIME_ZONE
            start_dt = datetime.combine(cycle["cycle_start"], datetime.min.time()).replace(tzinfo=tz)
            now_dt = datetime.now(tz)
            elapsed_seconds = (now_dt - start_dt).total_seconds()
        except Exception:
            elapsed_seconds = max(1.0, float(cycle["days_elapsed"])) * 86400.0

        prediction_data = calculate_predicted_consumption(
            kwh, cycle["days_in_cycle"], elapsed_seconds
        )
        predicted_bill = calculate_ceb_bill(
            prediction_data["predicted_kwh"], days_in_cycle=cycle["days_in_cycle"]
        )

        source_entity = (
            self._kwh_entity_id
            if self._kwh_entity_id
            else f"number.ceb_account_{self._account_number}_electricity_consumption_input"
        )

        self._calc_result = {
            **cycle,
            **bill,
            "kwh_entity": source_entity,
            "billing_day": self._billing_day,
            "raw_reading": round(raw_value, 2),
            "cycle_start_reading": (
                round(self._cycle_start_kwh, 2)
                if is_cumul and self._cycle_start_kwh is not None
                else None
            ),
            "is_cumulative": is_cumul,
            "average_daily_kwh": prediction_data["average_daily_kwh"],
            "predicted_kwh": prediction_data["predicted_kwh"],
            "predicted_bill": predicted_bill["total_bill"],
            "predicted_energy_charge": predicted_bill["energy_charge"],
            "predicted_fixed_charge": predicted_bill["fixed_charge"],
            "predicted_sscl_charge": predicted_bill["sscl_charge"],
            "predicted_tier_applied": predicted_bill["tier_applied"],
            "predicted_charge_breakdown": predicted_bill["charge_breakdown"],
            "tariff_category": "Domestic (D-1)",
            "last_calculated": datetime.now().isoformat(),
        }

        if hasattr(self.coordinator, "predicted_bill_sensor") and self.coordinator.predicted_bill_sensor:
            self.coordinator.predicted_bill_sensor.async_write_ha_state()

    async def async_update(self) -> None:
        """Update sensor state."""
        await self._async_update_calculation()

    @property
    def native_value(self) -> float | None:
        """Return the calculated bill in LKR."""
        return self._calc_result.get("total_bill")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed calculation attributes."""
        cycle_start = self._calc_result.get("cycle_start")
        cycle_end = self._calc_result.get("cycle_end")
        return {
            "account_number": self._account_number,
            "kwh_consumed": self._calc_result.get("kwh_consumed"),
            "kwh_entity": self._calc_result.get("kwh_entity"),
            "billing_day": self._calc_result.get("billing_day"),
            "raw_reading": self._calc_result.get("raw_reading"),
            "cycle_start_reading": self._calc_result.get("cycle_start_reading"),
            "is_cumulative": self._calc_result.get("is_cumulative"),
            "billing_cycle_start": cycle_start.isoformat() if hasattr(cycle_start, "isoformat") else cycle_start,
            "billing_cycle_end": cycle_end.isoformat() if hasattr(cycle_end, "isoformat") else cycle_end,
            "days_in_cycle": self._calc_result.get("days_in_cycle"),
            "days_elapsed": self._calc_result.get("days_elapsed"),
            "days_remaining": self._calc_result.get("days_remaining"),
            "energy_charge": self._calc_result.get("energy_charge"),
            "fixed_charge": self._calc_result.get("fixed_charge"),
            "sscl_charge": self._calc_result.get("sscl_charge"),
            "tier_applied": self._calc_result.get("tier_applied"),
            "tariff_category": self._calc_result.get("tariff_category"),
            "charge_breakdown": self._calc_result.get("charge_breakdown"),
            "average_daily_kwh": self._calc_result.get("average_daily_kwh"),
            "predicted_kwh": self._calc_result.get("predicted_kwh"),
            "predicted_bill": self._calc_result.get("predicted_bill"),
            "last_calculated": self._calc_result.get("last_calculated"),
        }


class CEBPredictedBillSensor(CoordinatorEntity[CEBBillCoordinator], SensorEntity):
    """Predicted CEB Electricity Bill sensor based on average daily consumption."""

    _attr_has_entity_name = True
    _attr_translation_key = "predicted_bill"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "LKR"
    _attr_icon = "mdi:chart-line"

    def __init__(
        self,
        coordinator: CEBBillCoordinator,
        account_number: str,
        entry_id: str,
        calculated_sensor: CEBCalculatedBillSensor,
    ) -> None:
        """Initialize the predicted bill sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._entry_id = entry_id
        self._calc_sensor = calculated_sensor
        self._attr_unique_id = f"ceb_bill_{account_number}_predicted_bill"
        self._attr_name = "Predicted Electricity Bill"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_number)},
            name=f"CEB Account {account_number}",
            manufacturer="Ceylon Electricity Board",
            model="InstantPay Bill Account",
            entry_type=None,
        )

    async def async_added_to_hass(self) -> None:
        """Link sensor to coordinator."""
        await super().async_added_to_hass()
        self.coordinator.predicted_bill_sensor = self

    @property
    def native_value(self) -> float | None:
        """Return the predicted bill in LKR."""
        return self._calc_sensor._calc_result.get("predicted_bill")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed prediction attributes."""
        res = self._calc_sensor._calc_result
        cycle_start = res.get("cycle_start")
        cycle_end = res.get("cycle_end")
        return {
            "account_number": self._account_number,
            "predicted_kwh": res.get("predicted_kwh"),
            "average_daily_kwh": res.get("average_daily_kwh"),
            "kwh_consumed_to_date": res.get("kwh_consumed"),
            "kwh_entity": res.get("kwh_entity"),
            "billing_day": res.get("billing_day"),
            "billing_cycle_start": cycle_start.isoformat() if hasattr(cycle_start, "isoformat") else cycle_start,
            "billing_cycle_end": cycle_end.isoformat() if hasattr(cycle_end, "isoformat") else cycle_end,
            "days_in_cycle": res.get("days_in_cycle"),
            "days_elapsed": res.get("days_elapsed"),
            "days_remaining": res.get("days_remaining"),
            "predicted_energy_charge": res.get("predicted_energy_charge"),
            "predicted_fixed_charge": res.get("predicted_fixed_charge"),
            "predicted_sscl_charge": res.get("predicted_sscl_charge"),
            "tier_applied": res.get("predicted_tier_applied"),
            "tariff_category": res.get("tariff_category"),
            "charge_breakdown": res.get("predicted_charge_breakdown"),
            "last_calculated": res.get("last_calculated"),
        }
