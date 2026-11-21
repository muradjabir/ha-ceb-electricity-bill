"""Unit tests for CEB bill and cycle calculator."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Allow running tests in lightweight environments without Home Assistant installed
if "homeassistant" not in sys.modules:
    for mod in (
        "homeassistant",
        "homeassistant.components",
        "homeassistant.components.sensor",
        "homeassistant.components.number",
        "homeassistant.config_entries",
        "homeassistant.const",
        "homeassistant.core",
        "homeassistant.data_entry_flow",
        "homeassistant.exceptions",
        "homeassistant.helpers",
        "homeassistant.helpers.entity",
        "homeassistant.helpers.entity_platform",
        "homeassistant.helpers.event",
        "homeassistant.helpers.restore_state",
        "homeassistant.helpers.selector",
        "homeassistant.helpers.update_coordinator",
    ):
        sys.modules.setdefault(mod, MagicMock())

from datetime import date
import unittest

from custom_components.ceb_bill.calculator import calculate_ceb_bill, get_billing_cycle


class TestCEBCalculator(unittest.TestCase):
    """Test suite for billing cycle and CEB bill calculations."""

    def test_billing_cycle_same_month_after_billing_day(self) -> None:
        """Test cycle when current date is after billing day in the same month."""
        ref = date(2026, 11, 21)
        cycle = get_billing_cycle(ref, billing_day=15)
        self.assertEqual(cycle["cycle_start"], date(2026, 11, 15))
        self.assertEqual(cycle["cycle_end"], date(2026, 12, 15))
        self.assertEqual(cycle["days_in_cycle"], 30)
        self.assertEqual(cycle["days_elapsed"], 6)
        self.assertEqual(cycle["days_remaining"], 24)

    def test_billing_cycle_same_month_before_billing_day(self) -> None:
        """Test cycle when current date is before billing day in the same month."""
        ref = date(2026, 11, 10)
        cycle = get_billing_cycle(ref, billing_day=15)
        self.assertEqual(cycle["cycle_start"], date(2026, 10, 15))
        self.assertEqual(cycle["cycle_end"], date(2026, 11, 15))
        self.assertEqual(cycle["days_in_cycle"], 31)
        self.assertEqual(cycle["days_elapsed"], 26)
        self.assertEqual(cycle["days_remaining"], 5)

    def test_billing_cycle_exact_billing_day(self) -> None:
        """Test cycle on the exact billing day."""
        ref = date(2026, 11, 15)
        cycle = get_billing_cycle(ref, billing_day=15)
        self.assertEqual(cycle["cycle_start"], date(2026, 11, 15))
        self.assertEqual(cycle["cycle_end"], date(2026, 12, 15))
        self.assertEqual(cycle["days_elapsed"], 0)
        self.assertEqual(cycle["days_remaining"], 30)

    def test_billing_cycle_month_end_clamping(self) -> None:
        """Test 31st billing day in shorter months like February."""
        ref = date(2026, 2, 10)
        cycle = get_billing_cycle(ref, billing_day=31)
        self.assertEqual(cycle["cycle_start"], date(2026, 1, 31))
        self.assertEqual(cycle["cycle_end"], date(2026, 2, 28))
        self.assertEqual(cycle["days_in_cycle"], 28)

    def test_billing_cycle_year_rollover(self) -> None:
        """Test year rollover in December/January."""
        ref = date(2026, 12, 20)
        cycle = get_billing_cycle(ref, billing_day=15)
        self.assertEqual(cycle["cycle_start"], date(2026, 12, 15))
        self.assertEqual(cycle["cycle_end"], date(2027, 1, 15))
        self.assertEqual(cycle["days_in_cycle"], 31)

    def test_calculate_low_user_tier_1(self) -> None:
        """Test low user tier 1 (<= 30 kWh) on 30-day base."""
        res = calculate_ceb_bill(25, days_in_cycle=30, prorate=False)
        self.assertEqual(res["tier_applied"], "low_user")
        self.assertEqual(res["energy_charge"], 150.00)
        self.assertEqual(res["fixed_charge"], 100.00)
        self.assertEqual(res["sscl_charge"], 6.25)
        self.assertEqual(res["total_bill"], 256.25)

    def test_calculate_low_user_tier_2(self) -> None:
        """Test low user tier 2 (31 - 60 kWh) on 30-day base."""
        res = calculate_ceb_bill(45, days_in_cycle=30, prorate=False)
        self.assertEqual(res["tier_applied"], "low_user")
        self.assertEqual(res["energy_charge"], 315.00)
        self.assertEqual(res["fixed_charge"], 250.00)
        self.assertEqual(res["sscl_charge"], 14.12)
        self.assertEqual(res["total_bill"], 579.12)

    def test_calculate_normal_user_80_kwh(self) -> None:
        """Test normal user tier (61 - 90 kWh) on 30-day base."""
        res = calculate_ceb_bill(80, days_in_cycle=30, prorate=False)
        self.assertEqual(res["tier_applied"], "normal_user")
        self.assertEqual(res["energy_charge"], 1260.00)
        self.assertEqual(res["fixed_charge"], 400.00)
        self.assertEqual(res["sscl_charge"], 41.50)
        self.assertEqual(res["total_bill"], 1701.50)

    def test_calculate_normal_user_150_kwh(self) -> None:
        """Test normal user tier (121 - 180 kWh) on 30-day base."""
        res = calculate_ceb_bill(150, days_in_cycle=30, prorate=False)
        self.assertEqual(res["tier_applied"], "normal_user")
        self.assertEqual(res["energy_charge"], 3600.00)
        self.assertEqual(res["fixed_charge"], 1500.00)
        self.assertEqual(res["sscl_charge"], 127.50)
        self.assertEqual(res["total_bill"], 5227.50)

    def test_calculate_cycle_delta_vs_cumulative(self) -> None:
        """Test difference between cumulative lifetime reading and monthly cycle delta."""
        cumulative_reading = 764.96
        cycle_start_reading = 594.63
        cycle_kwh = cumulative_reading - cycle_start_reading  # 170.33 kWh

        # Raw cumulative reading evaluates to ~46,000 LKR
        res_cumulative = calculate_ceb_bill(cumulative_reading, days_in_cycle=30)
        self.assertEqual(res_cumulative["total_bill"], 46004.46)

        # Actual cycle delta consumption evaluates to ~6,102.71 LKR
        res_cycle = calculate_ceb_bill(cycle_kwh, days_in_cycle=30)
        self.assertEqual(res_cycle["kwh_consumed"], 170.33)
        self.assertEqual(res_cycle["energy_charge"], 4453.86)
        self.assertEqual(res_cycle["fixed_charge"], 1500.00)
        self.assertEqual(res_cycle["total_bill"], 6102.71)

    def test_calculate_zero_kwh(self) -> None:
        """Test zero kWh consumption."""
        res = calculate_ceb_bill(0, days_in_cycle=30, prorate=False)
        self.assertEqual(res["energy_charge"], 0.00)
        self.assertEqual(res["fixed_charge"], 100.00)
        self.assertEqual(res["total_bill"], 102.50)

    def test_calculate_negative_kwh_clamps_to_zero(self) -> None:
        """Test negative input safely clamps to zero."""
        res = calculate_ceb_bill(-10, days_in_cycle=30, prorate=False)
        self.assertEqual(res["kwh_consumed"], 0.0)
        self.assertEqual(res["energy_charge"], 0.00)


if __name__ == "__main__":
    unittest.main()
