import pandas as pd
from finta import TA # Replaced pandas_ta with finta
import config # For any config variables directly used by analysis functions

def analyze_trend(price, p1h, p24h, p7d):
    if p1h > 1 and p24h > 2:
        return f"🟢 Uptrend: 1h +{p1h:.2f}%, 24h +{p24h:.2f}% — {config.COIN_ID.upper()} gaining."
    if p1h < -1 and p24h > 2:
        return f"🟡 Pullback: 1h {p1h:.2f}% drop, but 24h +{p24h:.2f}% uptrend continues."
    if p24h < 0 and p7d < 0:
        return f"🔴 Downtrend: 24h {p24h:.2f}%, 7d {p7d:.2f}% — avoid buying now."
    return f"⚪ Sideways: 1h {p1h:.2f}%, 24h {p24h:.2f}%, 7d {p7d:.2f}%."


def simple_price_prediction(price, p1h, p24h, p7d_percentage): # p7d parameter is the 7-day percentage change
    """Basic heuristic price projections."""
    # Print input parameters for debugging
    print(f"Debug: simple_price_prediction inputs - price: {price}, p1h: {p1h}, p24h: {p24h}, p7d: {p7d_percentage}")

    P1H_THRESHOLD = 0.5  # Significant 1-hour percentage change threshold

    # New logic for 1-day price prediction
    if p24h < 0 and p1h > P1H_THRESHOLD:
        # If 24-hour trend is down AND 1-hour trend is significantly up
        effective_daily_change = (p1h + p24h) / 2
        p1d_price = price * (1 + effective_daily_change / 100)
        print(f"Debug: Using modified daily prediction. Effective change: {effective_daily_change}, p1d_price: {p1d_price}")
    else:
        # Original logic for 1-day price prediction
        p1d_price = price * (1 + p24h / 100)
        print(f"Debug: Using original daily prediction. p1d_price: {p1d_price}")

    p7d_price = price * (1 + p7d_percentage / 100)  # This calculates the projected price after 7 days
    # Corrected 30-day prediction: compounds the weekly rate (derived from p7d_percentage) for 4 weeks.
    # p7d_percentage is the 7-day price change percentage.
    p30d_price = price * ((1 + p7d_percentage / 100) ** 4)
    return (
        f"📊 Prediction:\n"
        f"1D: ${p1d_price:.3f} | 7D: ${p7d_price:.3f} | 30D: ${p30d_price:.3f}"
    )


def calculate_indicators(ohlc_data):
    """
    Calculates technical indicators (RSI, MACD, Bollinger Bands) from OHLC data.
    """
    if not ohlc_data or len(ohlc_data) < 20: # Need enough data for a 20-period BB
        print("Warning: Not enough OHLC data to calculate indicators.")
        return {
            'rsi': None, 'macd_line': None, 'macd_histogram': None, 'macd_signal': None,
            'bb_lower': None, 'bb_middle': None, 'bb_upper': None, 'atr': None
        }

    try:
        df = pd.DataFrame(ohlc_data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')

        # Ensure OHLC columns are numeric (finta expects these columns in lowercase)
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Drop rows with NaN in OHLC after conversion
        df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)

        # Ensure enough data after cleaning for the longest period (e.g., 26 for MACD slow, 20 for BB)
        # Smallest period for finta to return non-NaN for MACD is typically period_slow + signal_period for full MACD.
        # RSI period 14, BB period 20. MACD slow 26. So, ~26 to 35 data points might be needed.
        # The initial check for 20 is a bit too low for finta's MACD with default params.
        # Let's use a slightly higher threshold, e.g., 35, to be safer with finta.
        print(f"Debug: DataFrame length for TA before length check: {len(df)}")
        required_data_points = 35 
        if len(df) < required_data_points:
            print(f"Warning: Not enough valid OHLC data points ({len(df)}) after cleaning for finta. Need at least {required_data_points}.")
            return {
                'rsi': None, 'macd_line': None, 'macd_histogram': None, 'macd_signal': None,
                'bb_lower': None, 'bb_middle': None, 'bb_upper': None, 'atr': None
            }

        # Calculate Indicators using finta
        # finta methods return Series or DataFrames directly, not appending to df unless assigned.
        rsi_series = TA.RSI(df, period=14)
        macd_df = TA.MACD(df, period_fast=12, period_slow=26, signal=9) # Columns: 'MACD', 'SIGNAL'
        print(f"Debug: macd_df tail:\n{macd_df.tail().to_string()}")
        bb_df = TA.BBANDS(df, period=20) # Corrected: std_deviation removed, using finta's default (usually 2.0)
        atr_series = TA.ATR(df, period=14) # Calculate ATR

        # Extract latest values
        latest_rsi = rsi_series.iloc[-1]
        
        latest_macd_line = macd_df['MACD'].iloc[-1]
        latest_macd_signal = macd_df['SIGNAL'].iloc[-1]
        print(f"Debug: latest_macd_line: {latest_macd_line}, latest_macd_signal: {latest_macd_signal}")
        # Manual calculation for MACD Histogram
        latest_macd_histogram = None
        if pd.notna(latest_macd_line) and pd.notna(latest_macd_signal):
            latest_macd_histogram = latest_macd_line - latest_macd_signal

        latest_bb_lower = bb_df['BB_LOWER'].iloc[-1]
        latest_bb_middle = bb_df['BB_MIDDLE'].iloc[-1]
        latest_bb_upper = bb_df['BB_UPPER'].iloc[-1]
        latest_atr = atr_series.iloc[-1] # Extract latest ATR

        indicators = {
            'rsi': float(latest_rsi) if pd.notna(latest_rsi) else None,
            'macd_line': float(latest_macd_line) if pd.notna(latest_macd_line) else None,
            'macd_histogram': float(latest_macd_histogram) if pd.notna(latest_macd_histogram) else None,
            'macd_signal': float(latest_macd_signal) if pd.notna(latest_macd_signal) else None,
            'bb_lower': float(latest_bb_lower) if pd.notna(latest_bb_lower) else None,
            'bb_middle': float(latest_bb_middle) if pd.notna(latest_bb_middle) else None,
            'bb_upper': float(latest_bb_upper) if pd.notna(latest_bb_upper) else None,
            'atr': float(latest_atr) if pd.notna(latest_atr) else None, # Add ATR to indicators
        }
        return indicators

    except Exception as e:
        print(f"Error calculating indicators with finta: {e}")
        # Return dict of Nones if any error occurs during calculation
        return {
            'rsi': None, 'macd_line': None, 'macd_histogram': None, 'macd_signal': None,
            'bb_lower': None, 'bb_middle': None, 'bb_upper': None, 'atr': None
        }


def generate_trading_signal(indicators, current_price):
    """
    Generates a trading signal (BUY, SELL, HOLD) based on technical indicators.
    """
    macd_histogram = indicators.get('macd_histogram')
    macd_line = indicators.get('macd_line') # Retrieve MACD line
    rsi = indicators.get('rsi')
    bb_middle = indicators.get('bb_middle')
    bb_lower = indicators.get('bb_lower') # Retrieved for potential future use or logging
    bb_upper = indicators.get('bb_upper') # Retrieved for potential future use or logging

    # Prerequisites: Ensure necessary indicator values are not None
    # If MACD histogram, MACD line, RSI, or Bollinger Band middle value is missing, cannot make a reliable decision.
    if macd_histogram is None or rsi is None or bb_middle is None or macd_line is None:
        print(f"Debug: generate_trading_signal returning HOLD due to missing indicator(s): MACD Hist: {macd_histogram}, MACD Line: {macd_line}, RSI: {rsi}, BB_Middle: {bb_middle}")
        return "HOLD"

    # BUY Signal Logic:
    # 1. MACD histogram is positive (bullish momentum).
    # 2. RSI is not overbought (still room to rise).
    # 3. Current price is below the middle Bollinger Band (potential undervaluation or upward mean reversion).
    # 4. MACD line is positive (confirming bullish trend).
    is_macd_hist_positive = macd_histogram > 0
    is_macd_line_positive = macd_line > 0
    is_rsi_not_overbought = rsi < 70
    is_price_below_bb_middle = current_price < bb_middle
    
    if is_macd_hist_positive and is_rsi_not_overbought and is_price_below_bb_middle and is_macd_line_positive:
        print(f"Debug: BUY signal generated. MACD Hist: {macd_histogram:.2f}, MACD Line: {macd_line:.2f}, RSI: {rsi:.2f}, Price: {current_price:.2f}, BB_Middle: {bb_middle:.2f}")
        return "BUY"

    # SELL Signal Logic:
    # 1. MACD histogram is negative (bearish momentum).
    # 2. RSI is not oversold (still room to fall).
    # 3. Current price is above the middle Bollinger Band (potential overvaluation or downward mean reversion).
    # 4. MACD line is negative (confirming bearish trend).
    is_macd_hist_negative = macd_histogram < 0
    is_macd_line_negative = macd_line < 0
    is_rsi_not_oversold = rsi > 30
    is_price_above_bb_middle = current_price > bb_middle

    if is_macd_hist_negative and is_rsi_not_oversold and is_price_above_bb_middle and is_macd_line_negative:
        print(f"Debug: SELL signal generated. MACD Hist: {macd_histogram:.2f}, MACD Line: {macd_line:.2f}, RSI: {rsi:.2f}, Price: {current_price:.2f}, BB_Middle: {bb_middle:.2f}")
        return "SELL"

    # HOLD Signal Logic
    print(f"Debug: HOLD signal. No BUY/SELL conditions met. MACD Hist: {macd_histogram:.2f}, MACD Line: {macd_line:.2f}, RSI: {rsi:.2f}, Price: {current_price:.2f}, BB_Middle: {bb_middle:.2f}")
    # If none of the above conditions for BUY or SELL are met
    return "HOLD"
