import pandas as pd
import pandas_ta as ta
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

        # Ensure OHLC columns are numeric
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Drop rows with NaN in OHLC after conversion, if any (should not happen with good data)
        df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)

        if len(df) < 20: # Re-check after potential NaN drops
            print("Warning: Not enough valid OHLC data points after cleaning.")
            return {
                'rsi': None, 'macd_line': None, 'macd_histogram': None, 'macd_signal': None,
                'bb_lower': None, 'bb_middle': None, 'bb_upper': None
            }

        # Calculate Indicators
        df.ta.rsi(length=14, append=True) # Appends RSI_14
        df.ta.macd(fast=12, slow=26, signal=9, append=True) # Appends MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        df.ta.bbands(length=20, std=2, append=True) # Appends BBL_20_2.0, BBM_20_2.0, BBU_20_2.0

        # Extract latest values
        latest_rsi = df['RSI_14'].iloc[-1]
        latest_macd_line = df['MACD_12_26_9'].iloc[-1]
        latest_macd_histogram = df['MACDh_12_26_9'].iloc[-1]
        latest_macd_signal = df['MACDs_12_26_9'].iloc[-1]
        latest_bb_lower = df['BBL_20_2.0'].iloc[-1]
        latest_bb_middle = df['BBM_20_2.0'].iloc[-1]
        latest_bb_upper = df['BBU_20_2.0'].iloc[-1]

        indicators = {
            'rsi': None if pd.isna(latest_rsi) else float(latest_rsi),
            'macd_line': None if pd.isna(latest_macd_line) else float(latest_macd_line),
            'macd_histogram': None if pd.isna(latest_macd_histogram) else float(latest_macd_histogram),
            'macd_signal': None if pd.isna(latest_macd_signal) else float(latest_macd_signal),
            'bb_lower': None if pd.isna(latest_bb_lower) else float(latest_bb_lower),
            'bb_middle': None if pd.isna(latest_bb_middle) else float(latest_bb_middle),
            'bb_upper': None if pd.isna(latest_bb_upper) else float(latest_bb_upper),
        }
        return indicators

    except Exception as e:
        print(f"Error calculating indicators: {e}")
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
