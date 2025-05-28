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
    p1d_price = price * (1 + p24h / 100)
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
            'bb_lower': None, 'bb_middle': None, 'bb_upper': None
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
                'bb_lower': None, 'bb_middle': None, 'bb_upper': None
            }

        # Calculate Indicators using finta
        # finta methods return Series or DataFrames directly, not appending to df unless assigned.
        rsi_series = TA.RSI(df, period=14)
        macd_df = TA.MACD(df, period_fast=12, period_slow=26, signal=9) # Columns: 'MACD', 'SIGNAL'
        print(f"Debug: macd_df tail:\n{macd_df.tail().to_string()}")
        bb_df = TA.BBANDS(df, period=20) # Corrected: std_deviation removed, using finta's default (usually 2.0)

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

        indicators = {
            'rsi': float(latest_rsi) if pd.notna(latest_rsi) else None,
            'macd_line': float(latest_macd_line) if pd.notna(latest_macd_line) else None,
            'macd_histogram': float(latest_macd_histogram) if pd.notna(latest_macd_histogram) else None,
            'macd_signal': float(latest_macd_signal) if pd.notna(latest_macd_signal) else None,
            'bb_lower': float(latest_bb_lower) if pd.notna(latest_bb_lower) else None,
            'bb_middle': float(latest_bb_middle) if pd.notna(latest_bb_middle) else None,
            'bb_upper': float(latest_bb_upper) if pd.notna(latest_bb_upper) else None,
        }
        return indicators

    except Exception as e:
        print(f"Error calculating indicators with finta: {e}")
        # Return dict of Nones if any error occurs during calculation
        return {
            'rsi': None, 'macd_line': None, 'macd_histogram': None, 'macd_signal': None,
            'bb_lower': None, 'bb_middle': None, 'bb_upper': None
        }


def generate_trading_signal(indicators, current_price):
    """
    Generates a trading signal (BUY, SELL, HOLD) based on technical indicators.
    """
    macd_histogram = indicators.get('macd_histogram')
    rsi = indicators.get('rsi')

    # Prerequisites: Ensure necessary indicator values are not None
    if macd_histogram is None or rsi is None:
        return "HOLD"

    # BUY Signal Logic
    # MACD histogram is positive and RSI is not overbought
    is_macd_buy = macd_histogram > 0
    is_rsi_not_overbought = rsi < 70
    if is_macd_buy and is_rsi_not_overbought:
        return "BUY"

    # SELL Signal Logic
    # MACD histogram is negative and RSI is not oversold
    is_macd_sell = macd_histogram < 0
    is_rsi_not_oversold = rsi > 30
    if is_macd_sell and is_rsi_not_oversold:
        return "SELL"

    # HOLD Signal Logic
    # If none of the above conditions for BUY or SELL are met
    return "HOLD"
