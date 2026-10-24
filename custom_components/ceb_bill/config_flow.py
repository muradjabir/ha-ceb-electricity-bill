"""Config flow for CEB Electricity Bill integration."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_ACCOUNT_NUMBER
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
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAccountNumber(HomeAssistantError):
    """Error to indicate account number is invalid."""
