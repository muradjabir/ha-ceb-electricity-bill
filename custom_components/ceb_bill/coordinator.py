"""Coordinator for fetching CEB bill data with smart caching."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL_HOURS, CACHE_TTL_SECONDS

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
    customer_name = (
        customer_name_elem["value"].strip()
        if customer_name_elem and customer_name_elem.get("value")
        else None
    )

    bill_date_elem = soup.find("input", {"id": "billdate"})
    bill_date = (
        bill_date_elem["value"].strip()
        if bill_date_elem and bill_date_elem.get("value")
        else None
    )

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
        "last_synced": datetime.now().isoformat(),
    }


class CEBBillCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching CEB bill data from the portal with caching and throttling."""

    def __init__(self, hass: HomeAssistant, account_number: str, scan_interval_hours: int = DEFAULT_SCAN_INTERVAL_HOURS) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"CEB Bill ({account_number})",
            update_interval=timedelta(hours=scan_interval_hours),
        )
        self.account_number = account_number
        self._last_fetch_time: float = 0
        self._cached_data: dict | None = None

    async def _async_update_data(self) -> dict:
        """Fetch data from CEB portal in executor with anti-hammer caching."""
        now = time.monotonic()
        # Protect upstream CEB site: If last successful fetch was within cache TTL, reuse cached data
        if self._cached_data and (now - self._last_fetch_time < CACHE_TTL_SECONDS):
            _LOGGER.debug(
                "CEB Bill (%s): Using cached data to prevent overloading portal (%d seconds remaining in TTL)",
                self.account_number,
                int(CACHE_TTL_SECONDS - (now - self._last_fetch_time)),
            )
            return self._cached_data

        try:
            data = await self.hass.async_add_executor_job(
                fetch_ceb_bill_sync, self.account_number
            )
            self._cached_data = data
            self._last_fetch_time = time.monotonic()
            return data
        except Exception as err:
            if self._cached_data:
                _LOGGER.warning(
                    "Error refreshing CEB portal data: %s. Using cached data.", err
                )
                return self._cached_data
            raise UpdateFailed(f"Error communicating with CEB portal: {err}") from err
