"""Tariff and billing cycle calculations for Ceylon Electricity Board (CEB)."""
from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from .const import DEFAULT_BILLING_DAY, SSCL_RATE


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
    """Calculate the CEB domestic electricity bill for a given kWh consumption.

    Follows the official PUCSL approved Domestic Tariff (Category D-1)
    Increasing Block Tariff schedule with proration for billing cycle length.

    Args:
        kwh: Total energy consumed in the billing cycle (kWh).
        days_in_cycle: Number of days in the billing cycle.
        prorate: Whether to prorate block limits and fixed charges based on a 30-day base.

    Returns:
        Dictionary with breakdown of energy charge, fixed charge, SSCL, and total bill.
    """
    units = max(0.0, float(kwh))
    p = (days_in_cycle / 30.0) if (prorate and days_in_cycle > 0) else 1.0

    threshold_60 = 60.0 * p
    breakdown: list[dict[str, Any]] = []

    if units <= threshold_60:
        tier_applied = "low_user"
        limit_30 = 30.0 * p

        # Block 1: 0 - 30 units
        u1 = min(units, limit_30)
        c1 = u1 * 6.00
        breakdown.append({"block": "0-30", "units": round(u1, 2), "rate": 6.00, "cost": round(c1, 2)})

        # Block 2: 31 - 60 units
        u2 = max(0.0, units - limit_30)
        c2 = u2 * 9.00
        if u2 > 0 or units > 0:
            breakdown.append({"block": "31-60", "units": round(u2, 2), "rate": 9.00, "cost": round(c2, 2)})

        energy_charge = c1 + c2

        # Fixed charge for low users
        if units <= limit_30:
            fixed_charge = 100.00 * p
        else:
            fixed_charge = 250.00 * p

    else:
        tier_applied = "normal_user"
        limit_60 = 60.0 * p
        limit_90 = 90.0 * p
        limit_120 = 120.0 * p
        limit_180 = 180.0 * p

        # Tier 1: 0 - 60 units @ 15.00
        u1 = min(units, limit_60)
        c1 = u1 * 15.00
        breakdown.append({"block": "0-60", "units": round(u1, 2), "rate": 15.00, "cost": round(c1, 2)})

        # Tier 2: 61 - 90 units @ 18.00
        u2 = min(max(0.0, units - limit_60), 30.0 * p)
        c2 = u2 * 18.00
        breakdown.append({"block": "61-90", "units": round(u2, 2), "rate": 18.00, "cost": round(c2, 2)})

        # Tier 3: 91 - 120 units @ 30.00
        u3 = min(max(0.0, units - limit_90), 30.0 * p)
        c3 = u3 * 30.00
        if u3 > 0 or units > limit_90:
            breakdown.append({"block": "91-120", "units": round(u3, 2), "rate": 30.00, "cost": round(c3, 2)})

        # Tier 4: 121 - 180 units @ 42.00
        u4 = min(max(0.0, units - limit_120), 60.0 * p)
        c4 = u4 * 42.00
        if u4 > 0 or units > limit_120:
            breakdown.append({"block": "121-180", "units": round(u4, 2), "rate": 42.00, "cost": round(c4, 2)})

        # Tier 5: Above 180 units @ 65.00
        u5 = max(0.0, units - limit_180)
        c5 = u5 * 65.00
        if u5 > 0:
            breakdown.append({"block": ">180", "units": round(u5, 2), "rate": 65.00, "cost": round(c5, 2)})

        energy_charge = c1 + c2 + c3 + c4 + c5

        # Fixed charge for normal users
        if units <= limit_90:
            fixed_charge = 400.00 * p
        elif units <= limit_120:
            fixed_charge = 1000.00 * p
        elif units <= limit_180:
            fixed_charge = 1500.00 * p
        else:
            fixed_charge = 2000.00 * p

    subtotal = energy_charge + fixed_charge
    sscl_charge = subtotal * SSCL_RATE
    total_bill = subtotal + sscl_charge

    return {
        "kwh_consumed": round(units, 2),
        "energy_charge": round(energy_charge, 2),
        "fixed_charge": round(fixed_charge, 2),
        "sscl_charge": round(sscl_charge, 2),
        "total_bill": round(total_bill, 2),
        "tier_applied": tier_applied,
        "proration_factor": round(p, 4),
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

