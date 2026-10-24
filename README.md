# CEB Electricity Bill (Sri Lanka) - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/v/release/muradjabir/ha-ceb-electricity-bill?style=for-the-badge)](https://github.com/muradjabir/ha-ceb-electricity-bill/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

Track your **Ceylon Electricity Board (CEB)** electricity bill balance and account details directly in Home Assistant.

This custom component pulls bill details daily from the official [CEB InstantPay](https://payment.ceb.lk/instantpay) portal with zero credentials required—only your 10-digit account number.

---

## Features

- **Automatic Daily Updates:** Fetches current outstanding balance once every 24 hours.
- **Config Flow Setup:** Easy UI configuration directly in Home Assistant (Settings -> Devices & Services -> Add Integration).
- **Multiple Accounts:** Track multiple CEB electricity connections in the same Home Assistant instance.
- **Rich Attributes:**
  - `account_number`: Your 10-digit CEB account number
  - `customer_name`: Name registered with CEB
  - `bill_date`: Date of the latest issued bill
  - `unit_of_measurement`: `LKR`
  - `device_class`: `monetary`

---

## Installation

### Method 1: Via HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant.
2. In Home Assistant, open **HACS** > **Integrations**.
3. Click the **three dots** in the top right corner and select **Custom repositories**.
4. Paste the repository URL:
   ```text
   https://github.com/muradjabir/ha-ceb-electricity-bill
   ```
5. Select Category: **Integration** and click **Add**.
6. Search for **CEB Electricity Bill (Sri Lanka)** and click **Download**.
7. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release `.zip` or clone this repository.
2. Copy the `custom_components/ceb_bill` directory into your Home Assistant `<config_dir>/custom_components/` folder.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** in the bottom right corner.
3. Search for **CEB Electricity Bill (Sri Lanka)**.
4. Enter your 10-digit CEB Account Number (e.g. `2792108118`) and submit.
5. A new sensor `sensor.electricity_bill_balance` (or similar) will be created under your CEB device.

---

## Example Automation: Bill Change Notification

Get a push notification whenever your monthly electricity bill is updated:

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

This integration is an independent open-source project and is not officially affiliated with, endorsed by, or sponsored by the Ceylon Electricity Board (CEB).

---

## License

[MIT License](LICENSE)
