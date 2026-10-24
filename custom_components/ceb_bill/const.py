"""Constants for the Ceylon Electricity Board (CEB) Bill integration."""

DOMAIN = "ceb_bill"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_SCAN_INTERVAL_HOURS = "scan_interval_hours"

DEFAULT_SCAN_INTERVAL_HOURS = 24
MIN_SCAN_INTERVAL_HOURS = 12
CACHE_TTL_SECONDS = 3600  # 1 hour minimum between network calls
