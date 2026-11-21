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

from custom_components.ceb_bill.calculator import (
    calculate_ceb_bill,
    calculate_predicted_consumption,
    get_billing_cycle,
)


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

    def test_calculate_band_1_subsidized_tier_1(self) -> None:
        """Test Band 1 (0-30 kWh) on 30-day base."""
        # 25 units: 25 * 5.00 = 125, fixed = 80, subtotal = 205
        # SSCL = 205 * 2.5 / 97.5 = 5.26, total = 210.26
        res = calculate_ceb_bill(25, days_in_cycle=30, prorate=False)
        self.assertEqual(res["tier_applied"], "band_1_subsidized")
        self.assertEqual(res["energy_charge"], 125.00)
        self.assertEqual(res["fixed_charge"], 80.00)
        self.assertEqual(res["sscl_charge"], 5.26)
        self.assertEqual(res["total_bill"], 210.26)

    def test_calculate_band_1_subsidized_tier_2(self) -> None:
        """Test Band 1 (31-60 kWh) on 30-day base."""
        # 45 units: 30 * 5.00 + 15 * 9.00 = 150 + 135 = 285
        # fixed = 210, subtotal = 495, SSCL = 495 * 2.5 / 97.5 = 12.69, total = 507.69
        res = calculate_ceb_bill(45, days_in_cycle=30, prorate=False)
        self.assertEqual(res["tier_applied"], "band_1_subsidized")
        self.assertEqual(res["energy_charge"], 285.00)
        self.assertEqual(res["fixed_charge"], 210.00)
        self.assertEqual(res["sscl_charge"], 12.69)
        self.assertEqual(res["total_bill"], 507.69)

    def test_calculate_example_a_100_units(self) -> None:
        """Test Example A from PUCSL May 11, 2026 schedule (100 units in Band 2)."""
        # Units 1-60: 60 * 14.00 = 840.00
        # Units 61-90: 30 * 20.00 = 600.00
        # Units 91-100: 10 * 28.00 = 280.00
        # Fixed charge: 1,000.00
        # Subtotal: 2,720.00
        # SSCL: 2,720 * 2.5 / 97.5 = 69.74
        # Total: 2,789.74
        res = calculate_ceb_bill(100, days_in_cycle=30, prorate=False)
        self.assertEqual(res["tier_applied"], "band_2_normal")
        self.assertEqual(res["energy_charge"], 1720.00)
        self.assertEqual(res["fixed_charge"], 1000.00)
        self.assertEqual(res["sscl_charge"], 69.74)
        self.assertEqual(res["total_bill"], 2789.74)

    def test_calculate_example_b_200_units(self) -> None:
        """Test Example B from PUCSL May 11, 2026 schedule (200 units in Band 3)."""
        # Units 1-180: 180 * 32.50 = 5,850.00
        # Units 181-200: 20 * 100.00 = 2,000.00
        # Fixed charge: 2,500.00
        # Subtotal: 10,350.00
        # SSCL: 10,350 * 2.5 / 97.5 = 265.38
        # Total: 10,615.38
        res = calculate_ceb_bill(200, days_in_cycle=30, prorate=False)
        self.assertEqual(res["tier_applied"], "band_3_heavy")
        self.assertEqual(res["energy_charge"], 7850.00)
        self.assertEqual(res["fixed_charge"], 2500.00)
        self.assertEqual(res["sscl_charge"], 265.38)
        self.assertEqual(res["total_bill"], 10615.38)

    def test_calculate_user_325_units(self) -> None:
        """Test user's actual bill of 325 units (Band 3)."""
        # Units 1-180: 180 * 32.50 = 5,850.00
        # Above 180: 145 * 100.00 = 14,500.00
        # Energy charge: 20,350.00
        # Fixed charge: 2,500.00
        # Subtotal: 22,850.00
        # SSCL: 22,850 * 2.5 / 97.5 = 585.90
        # Total: 23,435.90 (~23,000 LKR)
        res = calculate_ceb_bill(325, days_in_cycle=30, prorate=False)
        self.assertEqual(res["tier_applied"], "band_3_heavy")
        self.assertEqual(res["energy_charge"], 20350.00)
        self.assertEqual(res["fixed_charge"], 2500.00)
        self.assertEqual(res["sscl_charge"], 585.90)
        self.assertEqual(res["total_bill"], 23435.90)

    def test_calculate_cliff_threshold_60_vs_61(self) -> None:
        """Test cliff threshold going from 60 units (Band 1) to 61 units (Band 2)."""
        # 60 units: 30 * 5 + 30 * 9 = 420 + 210 = 630 pre-tax
        res_60 = calculate_ceb_bill(60, days_in_cycle=30, prorate=False)
        pre_tax_60 = res_60["energy_charge"] + res_60["fixed_charge"]
        self.assertEqual(pre_tax_60, 630.00)

        # 61 units: 60 * 14 + 1 * 20 = 860 + 400 = 1,260 pre-tax
        res_61 = calculate_ceb_bill(61, days_in_cycle=30, prorate=False)
        pre_tax_61 = res_61["energy_charge"] + res_61["fixed_charge"]
        self.assertEqual(pre_tax_61, 1260.00)

    def test_calculate_cliff_threshold_180_vs_181(self) -> None:
        """Test cliff threshold going from 180 units (Band 2) to 181 units (Band 3)."""
        # 180 units: 60*14 + 30*20 + 30*28 + 60*44 = 4920 + 1500 = 6,420 pre-tax
        res_180 = calculate_ceb_bill(180, days_in_cycle=30, prorate=False)
        pre_tax_180 = res_180["energy_charge"] + res_180["fixed_charge"]
        self.assertEqual(pre_tax_180, 6420.00)

        # 181 units: 180 * 32.50 + 1 * 100.00 = 5950 + 2500 = 8,450 pre-tax
        res_181 = calculate_ceb_bill(181, days_in_cycle=30, prorate=False)
        pre_tax_181 = res_181["energy_charge"] + res_181["fixed_charge"]
        self.assertEqual(pre_tax_181, 8450.00)

    def test_calculate_zero_kwh(self) -> None:
        """Test zero kWh consumption."""
        res = calculate_ceb_bill(0, days_in_cycle=30, prorate=False)
        self.assertEqual(res["energy_charge"], 0.00)
        self.assertEqual(res["fixed_charge"], 80.00)
        self.assertEqual(res["total_bill"], 82.05)

    def test_calculate_predicted_consumption(self) -> None:
        """Test daily average and projected kWh for cycle."""
        res = calculate_predicted_consumption(100.0, days_in_cycle=30, days_elapsed_seconds=864000.0)
        self.assertEqual(res["average_daily_kwh"], 10.0)
        self.assertEqual(res["predicted_kwh"], 300.0)


if __name__ == "__main__":
    unittest.main()
