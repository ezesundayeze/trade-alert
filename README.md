# Crypto Price Watcher & Trading Bot

## Project Overview

This Python script monitors cryptocurrency prices, analyzes market trends, calculates technical indicators, and can optionally execute trades on the Bybit exchange based on a defined strategy. It provides notifications via Pushover for significant price movements, daily summaries, and trading actions.

The primary goals of this project are:
- Real-time cryptocurrency price tracking.
- Calculation of common technical indicators (RSI, MACD, Bollinger Bands).
- Generation of trading signals (BUY/SELL/HOLD) based on these indicators.
- Optional automated trading integration with Bybit (testnet by default).
- User notifications for market events and bot actions.
- Modular code structure for maintainability and future expansion.

## File Structure

```
.
├── watch_coin.py            # Main application script
├── bybit_operations.py      # Functions for Bybit API interaction
├── data_sources.py          # Functions for fetching market data
├── technical_analysis.py    # Functions for calculating indicators and signals
├── config.py                # Configuration variables
├── requirements.txt         # Python package dependencies
└── README.md                # This file
```

## Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

All core configurations are managed in `config.py`. API keys and sensitive information are loaded from environment variables.

1.  **Environment Variables:**
    Create a `.env` file in the project root or set environment variables directly.
    Refer to `config.py` for the names of environment variables used (e.g., `PUSHOVER_USER_KEY_ENV_VAR`, `BYBIT_API_KEY_ENV_VAR`).

    Example `.env` file content:
    ```env
    PUSHOVER_USER_KEY="your_pushover_user_key"
    PUSHOVER_APP_TOKEN="your_pushover_app_token"
    BYBIT_API_KEY="your_bybit_api_key"
    BYBIT_API_SECRET="your_bybit_api_secret"
    ```
    *   **Pushover Keys**: Obtain from your Pushover account.
    *   **Bybit API Keys**: Generate from your Bybit account. Ensure appropriate permissions are set if you intend to trade (e.g., Spot Trading). **It is highly recommended to use testnet API keys for initial setup and testing.**

2.  **`config.py` Settings:**
    Modify variables in `config.py` to adjust script behavior:
    *   `COIN_ID`: Cryptocurrency to monitor (e.g., "sui", "bitcoin").
    *   `VS_CURRENCY`: Currency to compare against (e.g., "usd").
    *   `TARGET_PERCENT`: Percentage change for price movement alerts.
    *   `CHECK_INTERVAL`: How often to fetch new price data (in seconds).
    *   `SUMMARY_INTERVAL_HOURS`: How often to send a summary notification.
    *   `ENABLE_BYBIT_TRADING_DEFAULT`: Set to `True` or `False` to enable/disable Bybit trading by default (can be overridden by command-line flag).
    *   `TRADE_SIZE_USD`: The amount in USD for each trade.

## Core Logic (`watch_coin.py`)

The main script `watch_coin.py` orchestrates the bot's operations:

1.  **Initialization**:
    *   Loads configuration from `config.py`.
    *   Loads API keys from environment variables.
    *   Handles command-line arguments (e.g., `--enable-bybit`).
    *   Initializes `price_history` deque.

2.  **Main Loop**:
    *   Fetches current market data (price, OHLC) using `fetch_price_data` from `data_sources.py`.
    *   Calculates technical indicators (RSI, MACD, Bollinger Bands) using `calculate_indicators` from `technical_analysis.py`.
    *   Generates a trading signal (BUY/SELL/HOLD) using `generate_trading_signal` from `technical_analysis.py`.
    *   **Price Alerts**: Checks for significant price changes based on `config.TARGET_PERCENT` and sends alerts via `send_market_alert`.
    *   **Notifications**: Sends regular updates including the current strategy signal and key indicator values.
    *   **Bybit Trading (Optional)**: If `ENABLE_BYBIT_TRADING` is true and a BUY/SELL signal is generated:
        *   Connects to Bybit using `get_bybit_client` from `bybit_operations.py`.
        *   Checks account balance using `get_spot_balance`.
        *   Places market orders using `place_spot_market_order`.
        *   Sends notifications for trade actions or errors.
    *   **Daily Summary**: Periodically sends a summary notification using `send_daily_summary`, which includes trend analysis and the current strategy signal.
    *   **Other Features**: Includes detection for DCA opportunities, ranging markets, and breakouts (currently notified, not acted upon).

## Modules

*   **`config.py`**: Centralized configuration for the application.
*   **`data_sources.py`**: Handles fetching raw price and OHLC data from external APIs (e.g., CoinGecko).
    *   `fetch_price_data()`: Fetches current price, percentage changes, and OHLC data.
*   **`technical_analysis.py`**: Performs calculations and generates trading signals.
    *   `calculate_indicators(ohlc_data)`: Calculates RSI, MACD, Bollinger Bands.
    *   `generate_trading_signal(indicators, current_price)`: Determines BUY/SELL/HOLD based on indicator values.
    *   `analyze_trend(price, p1h, p24h, p7d)`: Provides a human-readable trend analysis.
    *   `simple_price_prediction(price, p1h, p24h, p7d_percentage)`: Basic heuristic price projections.
*   **`bybit_operations.py`**: Manages interactions with the Bybit exchange API.
    *   `get_bybit_client()`: Initializes and returns a Bybit HTTP client.
    *   `get_spot_balance(client, currency_symbol)`: Fetches spot balance for a currency.
    *   `place_spot_market_order(...)`: Places spot market orders.
*   **`watch_coin.py`**: Contains the main application logic, including the primary loop, notification functions, and coordination between other modules.

## How to Run

1.  Ensure all setup and configuration steps are complete.
2.  Activate your virtual environment.
3.  Run the script from the project root:
    ```bash
    python watch_coin.py
    ```
4.  **To enable Bybit trading (uses testnet by default):**
    ```bash
    python watch_coin.py --enable-bybit
    ```
    *   **IMPORTANT**: Bybit trading is set to use the **testnet** by default. This is configured in `bybit_operations.py` within the `get_bybit_client` function (`testnet=True`).
    *   For live trading, you must change `testnet=True` to `testnet=False` in `bybit_operations.py` and ensure you are using live API keys. **Proceed with extreme caution.**

## Bybit Integration Details

*   **API Client**: Uses `pybit` library for interacting with Bybit's Unified Trading Account API.
*   **Testnet First**: The integration is hardcoded to use `testnet=True` in `get_bybit_client()` for safety. **Do not switch to live trading (`testnet=False`) without extensive testing and understanding the risks.**
*   **Credentials**: API key and secret are loaded from environment variables specified in `config.py` (e.g., `BYBIT_API_KEY_ENV_VAR`, `BYBIT_API_SECRET_ENV_VAR`).
*   **Functions (`bybit_operations.py`)**:
    *   `get_bybit_client()`: Establishes connection.
    *   `get_spot_balance()`: Retrieves balance for `config.BYBIT_BASE_CURRENCY` (e.g., SUI) or `config.BYBIT_QUOTE_CURRENCY` (e.g., USDT).
    *   `place_spot_market_order()`: Executes market BUY or SELL orders for `config.BYBIT_SYMBOL` (e.g., SUIUSDT) with a quantity derived from `config.TRADE_SIZE_USD` and current price. Order quantity precision is rounded to 6 decimal places.
*   **Error Handling**: Includes `try-except` blocks for API calls and notifies errors via Pushover.
*   **Notifications**: Successful trades and errors are reported via Pushover.

## Disclaimers

*   **NOT FINANCIAL ADVICE**: This script is for educational and experimental purposes only. It is not financial advice.
*   **RISK OF LOSS**: Trading cryptocurrencies is highly speculative and carries a significant risk of loss. You could lose all of your invested capital.
*   **USE AT YOUR OWN RISK**: You are solely responsible for any decisions or actions taken as a result of using this script. The authors or contributors are not liable for any losses or damages.
*   **TEST THOROUGHLY**: Always test thoroughly on a testnet or with paper trading before using real funds. Bugs or errors in the script could lead to unintended trading actions.
*   **SECURITY**: Ensure your API keys are stored securely and have restricted permissions if possible. Do not share your API keys.
