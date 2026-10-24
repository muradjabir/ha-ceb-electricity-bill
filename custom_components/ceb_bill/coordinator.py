"""Coordinator for fetching CEB bill data."""
from __future__ import annotations

from datetime import timedelta
import logging
import re

import requests
from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL_HOURS

_LOGGER = logging.getLogger(__name__)

URL_GET = "https://payment.ceb.lk/instantpay"
URL_POST = "https://payment.ceb.lk/instantpay/Payment/details"


def fetch_ceb_bill_sync(account_no: str) -> dict:
    """Fetch bill details synchronously from CEB InstantPay portal."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            )
        }
    )

    # 1. Establish session
    resp1 = session.get(URL_GET, timeout=20)
    resp1.raise_for_status()

    # 2. Query account
    payload = {"account_no": account_no}
    resp2 = session.post(URL_POST, data=payload, timeout=25)
    resp2.raise_for_status()

    html = resp2.text
    soup = BeautifulSoup(html, "html.parser")

    customer_name_elem = soup.find("input", {"id": "customername"})
    customer_name = customer_name_elem["value"].strip() if customer_name_elem and customer_name_elem.get("value") else None

    bill_date_elem = soup.find("input", {"id": "billdate"})
    bill_date = bill_date_elem["value"].strip() if bill_date_elem and bill_date_elem.get("value") else None

    # Search for balance pattern
    balance = None
    balance_patterns = [
        r"(?:Total\s*Payable|Outstanding\s*Balance|Bill\s*Amount|Amount\s*Due|Total\s*Due|Payable\s*Amount)[^0-9]{0,40}(?:Rs\.?|LKR)?\s*([0-9,]+\.[0-9]{2})",
        r"(?:Rs\.?|LKR)\s*([0-9,]+\.[0-9]{2})",
        r"value=[\"']([0-9]+\.[0-9]{2})[\"']",
    ]

    for pat in balance_patterns:
        match = re.search(pat, html, re.IGNORECASE)
        if match:
            try:
                candidate = float(match.group(1).replace(",", ""))
                if candidate > 0:
                    balance = candidate
                    break
            except ValueError:
                continue

    if balance is None:
        # Fallback search for any table cell or label with decimal number
        nums = re.findall(r"([0-9,]+\.[0-9]{2})", html)
        if nums:
            balance = float(nums[0].replace(",", ""))

    if balance is None:
        raise ValueError(f"Could not parse bill balance from CEB response for account {account_no}")

    return {
        "account_number": account_no,
        "balance": balance,
        "customer_name": customer_name,
        "bill_date": bill_date,
    }


class CEBBillCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching CEB bill data from the portal."""

    def __init__(self, hass: HomeAssistant, account_number: str) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"CEB Bill ({account_number})",
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
        )
        self.account_number = account_number

    async def _async_update_data(self) -> dict:
        """Fetch data from CEB portal in executor."""
        try:
            return await self.hass.async_add_executor_job(
                fetch_ceb_bill_sync, self.account_number
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with CEB portal: {err}") from err
