"""Tariff and billing cycle calculations for Ceylon Electricity Board (CEB) / EDL.

Exact 1-to-1 Python implementation of the official PUCSL Electricity Bill Calculator:
https://www.pucsl.gov.lk/calculator/js/calculator.js
Approved Tariff Effective from 11 May 2026.
"""
from __future__ import annotations

import calendar
from datetime import date
import math
from typing import Any

from .const import DEFAULT_BILLING_DAY


def _clamp_day(year: int, month: int, day: int) -> int:
    """Clamp day to the maximum number of days in the specified month."""
    max_days = calendar.monthrange(year, month)[1]
    return min(max(1, day), max_days)


def get_billing_cycle(reference_date: date, billing_day: int = DEFAULT_BILLING_DAY) -> dict[str, Any]:
    """Calculate the billing cycle dates, elapsed days, and total cycle duration.

    Args:
        reference_date: Reference date, typically date.today().
        billing_day: Target day of the month for the meter read (1 - 31).

    Returns:
        Dictionary with cycle_start, cycle_end, days_in_cycle, days_elapsed, and days_remaining.
    """
    year = reference_date.year
    month = reference_date.month

    target_day = _clamp_day(year, month, billing_day)
    this_month_billing_date = date(year, month, target_day)

    if reference_date >= this_month_billing_date:
        cycle_start = this_month_billing_date
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1
        next_day = _clamp_day(next_year, next_month, billing_day)
        cycle_end = date(next_year, next_month, next_day)
    else:
        cycle_end = this_month_billing_date
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        prev_day = _clamp_day(prev_year, prev_month, billing_day)
        cycle_start = date(prev_year, prev_month, prev_day)

    days_in_cycle = (cycle_end - cycle_start).days
    days_elapsed = max(0, (reference_date - cycle_start).days)
    days_remaining = max(0, (cycle_end - reference_date).days)

    return {
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
        "days_in_cycle": days_in_cycle,
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
    }


def calculate_ceb_bill(
    kwh: float,
    days_in_cycle: int = 30,
    prorate: bool = True,
) -> dict[str, Any]:
    """Calculate the CEB / EDL domestic electricity bill for a given kWh consumption.

    Directly replicates the official PUCSL calculator logic:
    https://www.pucsl.gov.lk/calculator/js/calculator.js
    Approved Tariff Effective from 11 May 2026.

    Args:
        kwh: Total energy consumed in the billing cycle (kWh).
        days_in_cycle: Number of days in the billing cycle.
        prorate: Whether to prorate block limits based on billing cycle days.

    Returns:
        Dictionary with energy charge, fixed charge, SSCL levy, and total bill.
    """
    units = max(0.0, float(kwh))
    billing_days = max(1, int(days_in_cycle)) if prorate else 30

    # Official PUCSL block limit proration formula
    block30 = math.floor(30 * billing_days / 30)
    block60 = math.floor(60 * billing_days / 30)
    block90 = math.floor(90 * billing_days / 30)
    block120 = math.floor(120 * billing_days / 30)
    block180 = math.floor(180 * billing_days / 30)

    energy_charge = 0.0
    fixed_charge = 0.0
    breakdown: list[dict[str, Any]] = []

    if units <= block60:
        band = "Band 1 (0-60 kWh Subsidized)"
        tier_applied = "band_1_subsidized"

        b1 = min(units, block30)
        b2 = max(units - block30, 0.0)

        energy_charge += b1 * 5.0
        energy_charge += b2 * 9.0

        fixed_charge = 80.0 if units <= block30 else 210.0

        breakdown.append({"block": f"0-{block30}", "units": round(b1, 2), "rate": 5.0, "cost": round(b1 * 5.0, 2)})
        if b2 > 0:
            breakdown.append({"block": f"{block30 + 1}-{block60}", "units": round(b2, 2), "rate": 9.0, "cost": round(b2 * 9.0, 2)})

    elif units <= block180:
        band = "Band 2 (61-180 kWh)"
        tier_applied = "band_2_normal"

        b1 = min(units, block60)
        b2 = max(min(units, block90) - block60, 0.0)
        b3 = max(min(units, block120) - block90, 0.0)
        b4 = max(units - block120, 0.0)

        energy_charge += b1 * 14.0
        energy_charge += b2 * 20.0
        energy_charge += b3 * 28.0
        energy_charge += b4 * 44.0

        if units <= block90:
            fixed_charge = 400.0
        elif units <= block120:
            fixed_charge = 1000.0
        else:
            fixed_charge = 1500.0

        breakdown.append({"block": f"0-{block60}", "units": round(b1, 2), "rate": 14.0, "cost": round(b1 * 14.0, 2)})
        if b2 > 0:
            breakdown.append({"block": f"{block60 + 1}-{block90}", "units": round(b2, 2), "rate": 20.0, "cost": round(b2 * 20.0, 2)})
        if b3 > 0:
            breakdown.append({"block": f"{block90 + 1}-{block120}", "units": round(b3, 2), "rate": 28.0, "cost": round(b3 * 28.0, 2)})
        if b4 > 0:
            breakdown.append({"block": f"{block120 + 1}-{block180}", "units": round(b4, 2), "rate": 44.0, "cost": round(b4 * 44.0, 2)})

    else:
        band = "Band 3 (>180 kWh)"
        tier_applied = "band_3_heavy"

        first_tier = float(block180)
        second_tier = max(0.0, units - block180)

        energy_charge += first_tier * 32.50
        energy_charge += second_tier * 100.00

        fixed_charge = 2500.0

        breakdown.append({"block": f"0-{block180}", "units": round(first_tier, 2), "rate": 32.50, "cost": round(first_tier * 32.50, 2)})
        breakdown.append({"block": f">{block180}", "units": round(second_tier, 2), "rate": 100.00, "cost": round(second_tier * 100.00, 2)})

    subtotal = energy_charge + fixed_charge
    # Statutory grossed-up SSCL levy: Subtotal * 2.5 / 97.5 (~2.5641%)
    sscl_charge = (subtotal * 2.5) / 97.5
    total_bill = subtotal + sscl_charge

    return {
        "kwh_consumed": round(units, 2),
        "energy_charge": round(energy_charge, 2),
        "fixed_charge": round(fixed_charge, 2),
        "subtotal": round(subtotal, 2),
        "sscl_charge": round(sscl_charge, 2),
        "total_bill": round(total_bill, 2),
        "tier_applied": tier_applied,
        "band": band,
        "days_in_cycle": billing_days,
        "charge_breakdown": breakdown,
    }


def calculate_predicted_consumption(
    kwh_consumed: float,
    days_in_cycle: int,
    days_elapsed_seconds: float,
) -> dict[str, float]:
    """Calculate average daily consumption and projected cycle kWh.

    Args:
        kwh_consumed: Units consumed so far in the current billing cycle.
        days_in_cycle: Total days in the billing cycle (typically 28 to 31).
        days_elapsed_seconds: Number of seconds elapsed since the start of the cycle.

    Returns:
        Dictionary with average_daily_kwh, predicted_kwh, and days_elapsed_fractional.
    """
    units = max(0.0, float(kwh_consumed))
    effective_seconds = max(3600.0, float(days_elapsed_seconds))
    days_elapsed_frac = effective_seconds / 86400.0

    avg_daily_kwh = units / days_elapsed_frac
    predicted_kwh = round(avg_daily_kwh * days_in_cycle, 2)

    return {
        "average_daily_kwh": round(avg_daily_kwh, 2),
        "predicted_kwh": predicted_kwh,
        "days_elapsed_fractional": round(days_elapsed_frac, 2),
    }
