# CEB Electricity Bill (Sri Lanka) - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/v/release/muradjabir/ha-ceb-electricity-bill?style=for-the-badge)](https://github.com/muradjabir/ha-ceb-electricity-bill/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

Track your **Ceylon Electricity Board (CEB)** electricity bill balance and account details directly in Home Assistant, and calculate your real-time estimated monthly bill based on your actual or manual kWh consumption.

This custom component pulls official bill balance details daily from the [CEB InstantPay](https://payment.ceb.lk/instantpay) portal with zero credentials required (only your 10-digit account number), and accurately calculates your ongoing electricity bill following the official **PUCSL Domestic Tariff (Category D-1)** including billing cycle proration and Social Security Contribution Levy (SSCL).

---

## Features

- **Automatic Bill Balance Updates:** Fetches your current outstanding balance from the CEB InstantPay portal.
- **Configurable Energy Entity:** Select any Home Assistant entity (utility meter, smart meter, or energy sensor) providing kWh consumption to automatically calculate your live monthly bill.
- **Configurable Monthly Billing Date:** Select the day of the month (1 - 31) when your CEB meter is read. The integration automatically determines the billing cycle, elapsed days, days remaining, and applies PUCSL-mandated 30-day block limit proration.
- **Manual Consumption Input:** A built-in number entity (`Electricity Consumption Input`) allows you to type or simulate any kWh consumption directly from your dashboard without needing an external sensor.
- **Accurate PUCSL Tariff Calculation:**
  - Implements the subsidized low-user tariff (for consumption $\le 60$ kWh) and progressive non-subsidized slabs (for consumption $> 60$ kWh).
  - Includes energy charges, fixed charges, and the 2.5% Social Security Contribution Levy (SSCL).
- **Entities Provided per Account:**
  - `sensor.electricity_bill_balance`: Official outstanding bill balance in `LKR` (`monetary` device class).
  - `sensor.calculated_electricity_bill`: Real-time calculated bill based on consumption and billing date (`monetary` device class).
  - `number.electricity_consumption_input`: Configurable manual consumption input in `kWh`.
- **Rich Attributes on Calculated Bill Sensor:**
  - `kwh_consumed`: Consumption in kWh used for the calculation
  - `kwh_entity`: Source entity used for the calculation
  - `billing_day`: Selected meter reading day of the month (1 - 31)
  - `billing_cycle_start` & `billing_cycle_end`: Dates of the active billing cycle
  - `days_in_cycle`, `days_elapsed`, `days_remaining`
  - `energy_charge`: Total energy charge component in LKR
  - `fixed_charge`: Applicable monthly fixed charge in LKR
  - `sscl_charge`: 2.5% Social Security Contribution Levy in LKR
  - `charge_breakdown`: Detailed block-by-block breakdown of units, rates, and costs
  - `tier_applied`: `low_user` ($\le 60$ units) or `normal_user` ($> 60$ units)

---

## Installation

### Method 1: Via HACS (1-Click Install)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=muradjabir&repository=ha-ceb-electricity-bill&category=integration)

1. In Home Assistant, open **HACS** > **Integrations**.
2. Click the **three dots** in the top right corner and select **Custom repositories**.
3. Paste the repository URL:
   ```text
   https://github.com/muradjabir/ha-ceb-electricity-bill
   ```
4. Select Category: **Integration** and click **Add**.
5. Search for **CEB Electricity Bill (Sri Lanka)** and click **Download**.
6. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release `.zip` or clone this repository.
2. Copy the `custom_components/ceb_bill` directory into your Home Assistant `<config_dir>/custom_components/` folder.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** in the bottom right corner.
3. Search for **CEB Electricity Bill (Sri Lanka)**.
4. Fill in the configuration fields:
   - **Account Number (10 digits):** Your CEB account number (e.g. `2792108118`).
   - **Update Interval:** Frequency in hours to check the CEB portal (default: 24, minimum: 12).
   - **kWh Consumed Entity (optional):** Choose your energy sensor or utility meter (e.g. `sensor.monthly_grid_import`). If left empty, you can use the built-in `number.electricity_consumption_input` entity.
   - **Monthly Billing Day (1 - 31):** Day of the month your meter is read (e.g. 15).
5. All settings can be adjusted at any time via **Configure** on the integration card.

---

## Example Automation: Bill Change Notification

Get a notification whenever your CEB bill balance changes:

```yaml
alias: "CEB Electricity Bill Notification"
description: "Notify when CEB electricity bill balance changes"
trigger:
  - platform: state
    entity_id: sensor.ceb_account_2792108118_electricity_bill_balance
condition:
  - condition: template
    value_template: >-
      {{ trigger.from_state is not none and
         trigger.to_state is not none and
         trigger.from_state.state not in ['unavailable', 'unknown'] and
         trigger.to_state.state not in ['unavailable', 'unknown'] and
         trigger.from_state.state != trigger.to_state.state }}
action:
  - service: notify.notify
    data:
      title: "CEB Electricity Bill Updated"
      message: >-
        Your CEB bill balance changed from {{ trigger.from_state.state }} LKR to {{ trigger.to_state.state }} LKR.
mode: single
```

---

## Disclaimer

This integration is an independent open-source project and is not officially affiliated with, endorsed by, or sponsored by the Ceylon Electricity Board (CEB) or PUCSL.

---

## License

[MIT License](LICENSE)
