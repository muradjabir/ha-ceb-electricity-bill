"""Sensor platform for CEB Electricity Bill integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ACCOUNT_NUMBER
from .coordinator import CEBBillCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CEB sensors from config entry."""
    coordinator: CEBBillCoordinator = hass.data[DOMAIN][entry.entry_id]
    account_no = entry.data[CONF_ACCOUNT_NUMBER]

    async_add_entities(
        [
            CEBBillSensor(coordinator, account_no, entry.entry_id),
            CEBConnectionStatusSensor(coordinator, account_no, entry.entry_id),
        ]
    )


class CEBBillSensor(CoordinatorEntity[CEBBillCoordinator], SensorEntity):
    """Representation of CEB Electricity Bill Balance Sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "bill_balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "LKR"
    _attr_icon = "mdi:lightning-bolt-circle"

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
            "status": self.coordinator.data.get("status"),
            "last_synced": self.coordinator.data.get("last_synced"),
        }


class CEBConnectionStatusSensor(CoordinatorEntity[CEBBillCoordinator], SensorEntity):
    """Representation of CEB Electricity Connection Status Sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection_status"

    def __init__(
        self,
        coordinator: CEBBillCoordinator,
        account_number: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_unique_id = f"ceb_status_{account_number}"
        self._attr_name = "Connection Status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_number)},
            name=f"CEB Account {account_number}",
            manufacturer="Ceylon Electricity Board",
            model="InstantPay Bill Account",
            entry_type=None,
        )

    @property
    def native_value(self) -> str:
        """Return the current connection status."""
        if self.coordinator.data:
            return self.coordinator.data.get("status", "Active")
        return "Unknown"

    @property
    def icon(self) -> str:
        """Return dynamic icon based on status."""
        val = self.native_value.lower()
        if "active" in val:
            return "mdi:power-plug"
        if "inactive" in val or "disconnect" in val:
            return "mdi:power-plug-off"
        return "mdi:power-plug-outline"

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
