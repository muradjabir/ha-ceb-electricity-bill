"""Constants for the Ceylon Electricity Board (CEB) Bill integration."""

DOMAIN = "ceb_bill"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_SCAN_INTERVAL_HOURS = "scan_interval_hours"
CONF_KWH_ENTITY = "kwh_entity"
CONF_BILLING_DAY = "billing_day"

DEFAULT_SCAN_INTERVAL_HOURS = 24
MIN_SCAN_INTERVAL_HOURS = 12
DEFAULT_BILLING_DAY = 1

SSCL_RATE = 0.025  # 2.5% Social Security Contribution Levy
