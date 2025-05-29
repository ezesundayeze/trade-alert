# config.py

# Basic coin/market settings
COIN_ID = "sui"
VS_CURRENCY = "usd"

# Script behavior settings
TARGET_PERCENT = 5
CHECK_INTERVAL = 60 * 60   # seconds
SUMMARY_INTERVAL_HOURS = 1

# Environment variable names for API keys
PUSHOVER_USER_KEY_ENV_VAR = "PUSHOVER_USER_KEY"
PUSHOVER_APP_TOKEN_ENV_VAR = "PUSHOVER_APP_TOKEN"
BYBIT_API_KEY_ENV_VAR = "BYBIT_API_KEY"
BYBIT_API_SECRET_ENV_VAR = "BYBIT_API_SECRET"

# Bybit Trading Parameters
ENABLE_BYBIT_TRADING_DEFAULT = False  # Default value for enabling Bybit trading
TRADE_SIZE_USD = 10.0                 # Standard trade size in USD

# Derived Bybit symbols (defined from other config variables)
BYBIT_BASE_CURRENCY = COIN_ID.upper()
BYBIT_QUOTE_CURRENCY = VS_CURRENCY.upper()
BYBIT_SYMBOL = f"{BYBIT_BASE_CURRENCY}{BYBIT_QUOTE_CURRENCY}"
