import requests
import time
import os
from datetime import datetime, timedelta
from collections import deque
from statistics import mean
# pandas and pandas_ta imports removed as they are no longer used directly in this file.
# Their usage is encapsulated in technical_analysis.py.
# HTTP import removed as it's handled by bybit_operations.py
import argparse
from bybit_operations import get_bybit_client, get_spot_balance, place_spot_market_order
from data_sources import fetch_price_data # Import for fetching price data
from technical_analysis import calculate_indicators, generate_trading_signal, analyze_trend, simple_price_prediction
import config # Import the new config file
import os # Ensure os is imported

# Load API keys using names from config
PUSHOVER_USER_KEY = os.environ.get(config.PUSHOVER_USER_KEY_ENV_VAR)
PUSHOVER_APP_TOKEN = os.environ.get(config.PUSHOVER_APP_TOKEN_ENV_VAR)
BYBIT_API_KEY = os.environ.get(config.BYBIT_API_KEY_ENV_VAR)
BYBIT_API_SECRET = os.environ.get(config.BYBIT_API_SECRET_ENV_VAR)

# Initialize ENABLE_BYBIT_TRADING with the default from config
ENABLE_BYBIT_TRADING = config.ENABLE_BYBIT_TRADING_DEFAULT

# --- Argument Parsing for Enabling Bybit Trading ---
parser = argparse.ArgumentParser(description="Cryptocurrency monitoring and trading bot.")
parser.add_argument(
    "--enable-bybit",
    action="store_true",
    help="Enable Bybit trading functionality. Uses testnet by default (see get_bybit_client). Requires API keys."
)
args = parser.parse_args()

if args.enable_bybit:
    ENABLE_BYBIT_TRADING = True
    print("Bybit trading has been ENABLED via command-line flag.")
else:
    # This else block is important to ensure ENABLE_BYBIT_TRADING respects its default
    # or a value potentially set by other means if we add more config options later.
    # For now, it just means it remains what it was defined as globally (False).
    if ENABLE_BYBIT_TRADING: # If it was True by default (e.g. for testing) and flag not given
        print("Bybit trading remains ENABLED (defaulted to True, no --enable-bybit flag to override to False, though this flag only enables).")
    else:
        print("Bybit trading is DISABLED. Use --enable-bybit flag to enable it.")

initial_price = None
last_alert_price = None
last_summary_time = datetime.now() - timedelta(hours=24)
price_history = deque(maxlen=10)


# Note on `predict_next_move` vs `analyze_trend`:
# `predict_next_move` reflects very short-term (e.g., 3-5 hour, assuming hourly checks) momentum
# using spot price moving averages from the local `price_history` deque.
# Its output can sometimes appear to contradict the broader trend identified by `analyze_trend`
# (which uses 1-hour, 24-hour, and 7-day percentage changes from the API).
# This is normal, as short-term bounces or pullbacks can occur within longer-term trends.
# The two signals provide different timeframe perspectives on market behavior.
def predict_next_move():
    if len(price_history) < 5:
        return None
    short_ma = sum(list(price_history)[-3:]) / 3
    long_ma = sum(list(price_history)[-5:]) / 5
    if short_ma > long_ma:
        return "📈 Momentum up: short-term prices rising above average."
    if short_ma < long_ma:
        return "📉 Weakening: short-term prices below average."
    return "- No clear direction."


def detect_dca_opportunity(price_history, indicators):
    """Signal DCA if price is significantly below recent average, based on ATR."""
    if len(price_history) < 5: # Need some history for an average
        return None
    
    atr = indicators.get('atr')
    if atr is None or atr == 0:
        # ATR not available or zero, cannot use ATR-based logic.
        # Optionally, could fall back to old percentage-based logic here,
        # but returning None is safer if ATR is expected.
        print("Debug: DCA check skipped, ATR not available or is zero.")
        return None

    avg_price = mean(list(price_history)[-5:])
    curr = price_history[-1]
    
    # Condition: Current price is more than DCA_ATR_MULTIPLIER * ATR below the average price
    if curr < avg_price - (config.DCA_ATR_MULTIPLIER * atr):
        return f"💡 DCA opp (ATR based): current ${curr:.3f} significantly below avg ${avg_price:.3f} (ATR: ${atr:.3f})"
    return None


def detect_range_opportunity(price_history, tol=0.03):
    """Detect tight range, suggest buy/sell levels."""
    if len(price_history) < 10:
        return None
    recent = list(price_history)[-10:]
    mx, mn = max(recent), min(recent)
    avg = sum(recent) / len(recent)
    if (mx - mn) / avg <= tol:
        buy = mn * 1.01
        sell = mx * 0.99
        
        # If the calculated buy level is greater than or equal to the sell level,
        # the range is too tight to provide meaningful buy/sell levels with the current percentage buffers.
        # In such cases, no actionable opportunity is identified.
        if buy >= sell:
            print(f"Debug: Range opportunity skipped, range too tight. Buy: {buy:.3f}, Sell: {sell:.3f}, Min: {mn:.3f}, Max: {mx:.3f}")
            return None  # Range too tight for meaningful buy/sell levels with current buffer
            
        return (
            f"📈 Ranging (${mn:.3f}–${mx:.3f}).\n"
            f"Buy ~${buy:.3f}, Sell ~${sell:.3f}"
        )
    return None


def detect_breakout(price_history, current_price, indicators, n=10):
    """Detect breakout above resistance or below support using ATR."""
    if len(price_history) < n:
        return None

    atr = indicators.get('atr')
    if atr is None or atr == 0:
        # ATR not available or zero, cannot use ATR-based logic.
        print("Debug: Breakout check skipped, ATR not available or is zero.")
        return None
        
    recent = list(price_history)[-n:]
    mx, mn = max(recent), min(recent)
    
    # Breakout UP condition: Current price is above max price + BREAKOUT_ATR_MULTIPLIER * ATR
    if current_price > mx + (config.BREAKOUT_ATR_MULTIPLIER * atr):
        return f"🚀 Breakout UP (ATR)! Above ${mx:.3f} + ({config.BREAKOUT_ATR_MULTIPLIER}*ATR ${atr:.3f}) → ${current_price:.3f}"
    # Breakout DOWN condition: Current price is below min price - BREAKOUT_ATR_MULTIPLIER * ATR
    if current_price < mn - (config.BREAKOUT_ATR_MULTIPLIER * atr):
        return f"📉 Breakout DOWN (ATR)! Below ${mn:.3f} - ({config.BREAKOUT_ATR_MULTIPLIER}*ATR ${atr:.3f}) → ${current_price:.3f}"
    return None


def notify(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")
    payload = {"token": PUSHOVER_APP_TOKEN, "user": PUSHOVER_USER_KEY, "message": msg}
    try:
        r = requests.post("https://api.pushover.net/1/messages.json", data=payload)
        if r.status_code != 200:
            print(f"Notify error: {r.text}")
    except Exception as e:
        print(f"Pushover error: {e}")


def send_market_alert(price, label, trend, prediction, strategy_signal):
    notify(f"{label} {config.COIN_ID.upper()} @ ${price:.4f}")
    notify(trend)
    if prediction:
        notify(prediction)
    notify(f"🚦 Strategy Signal: {strategy_signal}")


def send_daily_summary():
    if not price_history:
        return
    price_data = fetch_price_data()
    if not price_data:
        notify("Error: Could not fetch price data for daily summary.")
        return

    price = price_data["current_price"]
    p1h = price_data["p1h"]
    p24h = price_data["p24h"]
    p7d = price_data["p7d"]
    ohlc_data = price_data.get("ohlc") # Get OHLC data for indicators

    t = analyze_trend(price, p1h, p24h, p7d)
    pred = predict_next_move() # Existing simple prediction
    
    # Calculate indicators and strategy signal for summary
    indicators = calculate_indicators(ohlc_data)
    current_strategy_signal = generate_trading_signal(indicators, price)

    msg = f"📊 Summary: {config.COIN_ID.upper()} @ ${price:.4f}\n{t}"
    if pred:
        msg += f"\n{pred}"
    msg += f"\n🚦 Strategy Signal: {current_strategy_signal}"
    notify(msg)


while True:
    print(f"[{datetime.now()}] Checking {config.COIN_ID}…")
    price_data = fetch_price_data()

    if price_data is None:
        # Error already printed by fetch_price_data or no data returned
        time.sleep(config.CHECK_INTERVAL)
        continue

    current_price = price_data["current_price"]
    p1h = price_data["p1h"]
    p24h = price_data["p24h"]
    p7d = price_data["p7d"]
    ohlc_data = price_data["ohlc"] # This is now available

    price_history.append(current_price)

    if initial_price is None:
        initial_price = current_price
        last_alert_price = current_price
        last_summary_time = datetime.now() - timedelta(days=1)

    # Calculate indicators and strategy signal for each check
    indicators = calculate_indicators(ohlc_data)
    strategy_signal = generate_trading_signal(indicators, current_price)

    # price-move alerts
    pct = (current_price - last_alert_price) / last_alert_price * 100
    if pct >= config.TARGET_PERCENT:
        tr = analyze_trend(current_price, p1h, p24h, p7d)
        pm = predict_next_move()
        send_market_alert(current_price, f"🎯 +{config.TARGET_PERCENT}% hit!", tr, pm, strategy_signal)
        last_alert_price = current_price
    elif pct <= -config.TARGET_PERCENT:
        tr = analyze_trend(current_price, p1h, p24h, p7d)
        pm = predict_next_move()
        send_market_alert(current_price, f"📉 -{config.TARGET_PERCENT}% drop!", tr, pm, strategy_signal)
        last_alert_price = current_price

    # new features / regular notifications
    # Notify current strategy signal on each check for observation
    # Prepare display strings for indicators to avoid formatting errors
    rsi_val = indicators.get('rsi')  # This can be None if not calculated
    macd_hist_val = indicators.get('macd_histogram') # This can be None

    rsi_display_str = f"{rsi_val:.2f}" if isinstance(rsi_val, (int, float)) else "N/A"
    macd_hist_display_str = f"{macd_hist_val:.4f}" if isinstance(macd_hist_val, (int, float)) else "N/A"

    notify_message = f"🚦 {config.COIN_ID.upper()} Strategy Signal: {strategy_signal} (RSI: {rsi_display_str}, MACD Hist: {macd_hist_display_str})"
    notify(notify_message)

    rng = detect_range_opportunity(price_history)
    if rng:
        notify(rng)

    brk = detect_breakout(price_history, current_price, indicators) # Pass indicators
    if brk:
        notify(brk)

    # Pass the necessary price_data components to simple_price_prediction
    pred = simple_price_prediction(current_price, p1h, p24h, p7d)
    notify(pred)

    dca = detect_dca_opportunity(price_history, indicators) # Pass indicators
    if dca:
        notify(dca)

    # --- BYBIT TRADING LOGIC ---
    # !!! --- WARNING: AUTOMATED TRADING IS RISKY --- !!!
    # The following section implements automated trading on Bybit if enabled.
    # Ensure you understand the code, the strategy, and the risks involved.
    # Start with small amounts and use the testnet extensively before live trading.
    # You are solely responsible for any financial outcomes.
    # !!! --- WARNING: AUTOMATED TRADING IS RISKY --- !!!
    if ENABLE_BYBIT_TRADING and strategy_signal in ["BUY", "SELL"]:
        print(f"Attempting Bybit trade action for signal: {strategy_signal}") # Logging
        bybit_client = get_bybit_client()

        if bybit_client:
            # current_price is already available from price_data['current_price'] at the start of the loop

            if strategy_signal == "BUY":
                quote_currency_balance = get_spot_balance(bybit_client, config.BYBIT_QUOTE_CURRENCY)
                print(f"Bybit: {config.BYBIT_QUOTE_CURRENCY} balance: {quote_currency_balance}") # Logging
                if quote_currency_balance >= config.TRADE_SIZE_USD:
                    quantity_to_buy = config.TRADE_SIZE_USD / current_price
                    quantity_to_buy = round(quantity_to_buy, 6) # Basic precision handling
                    
                    notify(f"Attempting to BUY {quantity_to_buy:.6f} {config.BYBIT_BASE_CURRENCY} on Bybit.")
                    place_spot_market_order(bybit_client, config.BYBIT_SYMBOL, "Buy", quantity_to_buy, config.BYBIT_QUOTE_CURRENCY, notify)
                else:
                    msg = f"Bybit: Insufficient {config.BYBIT_QUOTE_CURRENCY} balance ({quote_currency_balance:.2f}) to buy {config.TRADE_SIZE_USD} USD worth of {config.BYBIT_BASE_CURRENCY}."
                    print(msg)
                    notify(msg)

            elif strategy_signal == "SELL":
                base_currency_balance = get_spot_balance(bybit_client, config.BYBIT_BASE_CURRENCY)
                print(f"Bybit: {config.BYBIT_BASE_CURRENCY} balance: {base_currency_balance}") # Logging
                
                if base_currency_balance > 0:
                    quantity_equivalent_to_trade_size = config.TRADE_SIZE_USD / current_price
                    
                    if base_currency_balance >= quantity_equivalent_to_trade_size:
                        quantity_to_sell = quantity_equivalent_to_trade_size
                        msg_sell = f"Attempting to SELL {quantity_to_sell:.6f} {config.BYBIT_BASE_CURRENCY} (approx. {config.TRADE_SIZE_USD} USD) on Bybit."
                    else:
                        quantity_to_sell = base_currency_balance # Sell all available if less than TRADE_SIZE_USD worth
                        msg_sell = f"Attempting to SELL all available {quantity_to_sell:.6f} {config.BYBIT_BASE_CURRENCY} on Bybit."
                    
                    quantity_to_sell = round(quantity_to_sell, 6) # Basic precision handling
                    notify(msg_sell)
                    place_spot_market_order(bybit_client, config.BYBIT_SYMBOL, "Sell", quantity_to_sell, config.BYBIT_QUOTE_CURRENCY, notify)
                else:
                    msg = f"Bybit: No {config.BYBIT_BASE_CURRENCY} balance to sell."
                    print(msg)
                    notify(msg)
        else:
            msg = "Bybit: Could not connect to Bybit client. Trading actions skipped."
            print(msg)
            notify(msg)
    # --- END OF BYBIT TRADING LOGIC ---

    # periodic summary
    now = datetime.now()
    if now - last_summary_time >= timedelta(hours=config.SUMMARY_INTERVAL_HOURS):
        send_daily_summary()
        last_summary_time = now

    time.sleep(config.CHECK_INTERVAL)
