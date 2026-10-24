"""Config flow for CEB Electricity Bill integration."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_ACCOUNT_NUMBER,
    CONF_SCAN_INTERVAL_HOURS,
    DEFAULT_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
)
from .coordinator import fetch_ceb_bill_sync


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user input by attempting to fetch the bill."""
    account_no = data[CONF_ACCOUNT_NUMBER].strip()
    if not re.match(r"^\d{10}$", account_no):
        raise InvalidAccountNumber

    try:
        bill_data = await hass.async_add_executor_job(fetch_ceb_bill_sync, account_no)
    except Exception as err:
        raise CannotConnect from err

    return {"title": f"CEB {account_no}", "data": bill_data}


class CEBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CEB Electricity Bill."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get options flow for this handler."""
        return CEBOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account_no = user_input[CONF_ACCOUNT_NUMBER].strip()
            await self.async_set_unique_id(account_no)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAccountNumber:
                errors[CONF_ACCOUNT_NUMBER] = "invalid_account_number"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_NUMBER): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL_HOURS, default=DEFAULT_SCAN_INTERVAL_HOURS
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_HOURS)),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )


class CEBOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for CEB integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_HOURS,
            self.config_entry.data.get(CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL_HOURS,
                        default=current_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_HOURS)),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAccountNumber(HomeAssistantError):
    """Error to indicate account number is invalid."""
