"""Number platform for CEB Electricity Bill integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, CONF_ACCOUNT_NUMBER
from .coordinator import CEBBillCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CEB number entities."""
    coordinator: CEBBillCoordinator = hass.data[DOMAIN][entry.entry_id]
    account_no = entry.data[CONF_ACCOUNT_NUMBER]

    number_entity = CEBConsumptionInputNumber(coordinator, account_no, entry.entry_id)
    coordinator.number_entity = number_entity
    async_add_entities([number_entity])


class CEBConsumptionInputNumber(RestoreEntity, NumberEntity):
    """Configurable number entity for manual kWh consumption input."""

    _attr_has_entity_name = True
    _attr_translation_key = "kwh_consumed_input"
    _attr_device_class = NumberDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_native_min_value = 0.0
    _attr_native_max_value = 10000.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:counter"

    def __init__(
        self,
        coordinator: CEBBillCoordinator,
        account_number: str,
        entry_id: str,
    ) -> None:
        """Initialize the number entity."""
        self.coordinator = coordinator
        self._account_number = account_number
        self._entry_id = entry_id
        self._attr_unique_id = f"ceb_bill_{account_number}_kwh_input"
        self._attr_name = "Electricity Consumption Input"
        self._attr_native_value = 0.0
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_number)},
            name=f"CEB Account {account_number}",
            manufacturer="Ceylon Electricity Board",
            model="InstantPay Bill Account",
            entry_type=None,
        )

    async def async_added_to_hass(self) -> None:
        """Restore last state on restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                val = float(last_state.state)
                self._attr_native_value = val
                self.coordinator.manual_kwh = val
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        """Set new kWh value."""
        self._attr_native_value = float(value)
        self.coordinator.manual_kwh = float(value)
        self.async_write_ha_state()

        if hasattr(self.coordinator, "calculated_bill_sensor") and self.coordinator.calculated_bill_sensor:
            self.coordinator.calculated_bill_sensor.async_schedule_update_ha_state(True)
