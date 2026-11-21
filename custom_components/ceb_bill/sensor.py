"""Sensor platform for CEB Electricity Bill integration."""
from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
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

from .calculator import calculate_ceb_bill, get_billing_cycle
from .const import (
    DOMAIN,
    CONF_ACCOUNT_NUMBER,
    CONF_KWH_ENTITY,
    CONF_BILLING_DAY,
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

    entities: list[SensorEntity] = [
        CEBBillSensor(coordinator, account_no, entry.entry_id),
        CEBCalculatedBillSensor(coordinator, account_no, entry.entry_id, kwh_entity_id, billing_day),
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


class CEBCalculatedBillSensor(CoordinatorEntity[CEBBillCoordinator], SensorEntity):
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
    ) -> None:
        """Initialize the calculated bill sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._entry_id = entry_id
        self._kwh_entity_id = kwh_entity_id
        self._billing_day = billing_day
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
        """Register state listener and link sensor to coordinator."""
        await super().async_added_to_hass()
        self.coordinator.calculated_bill_sensor = self

        if self._kwh_entity_id:
            @callback
            def _async_on_kwh_state_change(event: Any) -> None:
                """Handle external sensor state change."""
                self._update_calculation()
                self.async_write_ha_state()

            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._kwh_entity_id], _async_on_kwh_state_change
                )
            )

        self._update_calculation()

    @callback
    def _update_calculation(self) -> None:
        """Calculate bill from kWh consumption and billing cycle."""
        kwh: float = 0.0

        if self._kwh_entity_id:
            state = self.hass.states.get(self._kwh_entity_id)
            if state is not None and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    kwh = float(state.state)
                except (ValueError, TypeError):
                    kwh = 0.0
        elif hasattr(self.coordinator, "manual_kwh"):
            kwh = float(self.coordinator.manual_kwh)

        cycle = get_billing_cycle(date.today(), self._billing_day)
        bill = calculate_ceb_bill(kwh, days_in_cycle=cycle["days_in_cycle"])

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
            "tariff_category": "Domestic (D-1)",
            "last_calculated": datetime.now().isoformat(),
        }

    @property
    def native_value(self) -> float | None:
        """Return the calculated bill in LKR."""
        self._update_calculation()
        return self._calc_result.get("total_bill")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed calculation attributes."""
        if not self._calc_result:
            self._update_calculation()
        cycle_start = self._calc_result.get("cycle_start")
        cycle_end = self._calc_result.get("cycle_end")
        return {
            "account_number": self._account_number,
            "kwh_consumed": self._calc_result.get("kwh_consumed"),
            "kwh_entity": self._calc_result.get("kwh_entity"),
            "billing_day": self._calc_result.get("billing_day"),
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
            "last_calculated": self._calc_result.get("last_calculated"),
        }
