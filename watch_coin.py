import requests
import time
import os
from datetime import datetime, timedelta
from collections import deque
from statistics import mean

COIN_ID = "sui"
VS_CURRENCY = "usd"
TARGET_PERCENT = 5
CHECK_INTERVAL = 60 * 60   # seconds
SUMMARY_INTERVAL_HOURS = 1

PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_APP_TOKEN = os.environ.get("PUSHOVER_APP_TOKEN")

initial_price = None
last_alert_price = None
last_summary_time = datetime.now() - timedelta(hours=24)
price_history = deque(maxlen=10)


def fetch_price_data():
    url = f"https://api.coingecko.com/api/v3/coins/{COIN_ID}?localization=false&tickers=false&market_data=true"
    try:
        response = requests.get(url)
        data = response.json()["market_data"]
        return (
            data["current_price"][VS_CURRENCY],
            data.get("price_change_percentage_1h_in_currency", {}).get(VS_CURRENCY, 0),
            data.get("price_change_percentage_24h_in_currency", {}).get(VS_CURRENCY, 0),
            data.get("price_change_percentage_7d_in_currency", {}).get(VS_CURRENCY, 0),
        )
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None, None, None, None


def analyze_trend(price, p1h, p24h, p7d):
    if p1h > 1 and p24h > 2:
        return f"🟢 Uptrend: 1h +{p1h:.2f}%, 24h +{p24h:.2f}% — {COIN_ID.upper()} gaining."
    if p1h < -1 and p24h > 2:
        return f"🟡 Pullback: 1h {p1h:.2f}% drop, but 24h +{p24h:.2f}% uptrend continues."
    if p24h < 0 and p7d < 0:
        return f"🔴 Downtrend: 24h {p24h:.2f}%, 7d {p7d:.2f}% — avoid buying now."
    return f"⚪ Sideways: 1h {p1h:.2f}%, 24h {p24h:.2f}%, 7d {p7d:.2f}%."


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


def detect_dca_opportunity(price_history):
    """Signal DCA if price is 10% below recent 5-sample average."""
    if len(price_history) < 5:
        return None
    avg_price = mean(list(price_history)[-5:])
    curr = price_history[-1]
    if curr < avg_price * 0.90:
        return f"💡 DCA opp: current ${curr:.3f} < 90% of avg ${avg_price:.3f}"
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
        return (
            f"📈 Ranging (${mn:.3f}–${mx:.3f}).\n"
            f"Buy ~${buy:.3f}, Sell ~${sell:.3f}"
        )
    return None


def detect_breakout(price_history, current_price, n=10, buf=0.005):
    """Detect breakout above resistance or below support."""
    if len(price_history) < n:
        return None
    recent = list(price_history)[-n:]
    mx, mn = max(recent), min(recent)
    if current_price > mx * (1 + buf):
        return f"🚀 Breakout UP! Above ${mx:.3f} → ${current_price:.3f}"
    if current_price < mn * (1 - buf):
        return f"📉 Breakout DOWN! Below ${mn:.3f} → ${current_price:.3f}"
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


def send_market_alert(price, label, trend, prediction):
    notify(f"{label} {COIN_ID.upper()} @ ${price:.4f}")
    notify(trend)
    if prediction:
        notify(prediction)


def send_daily_summary():
    if not price_history:
        return
    price = price_history[-1]
    _, p1h, p24h, p7d = fetch_price_data()
    t = analyze_trend(price, p1h, p24h, p7d)
    pred = predict_next_move()
    msg = f"📊 Summary: {COIN_ID.upper()} @ ${price:.4f}\n{t}"
    if pred:
        msg += f"\n{pred}"
    notify(msg)


while True:
    print(f"[{datetime.now()}] Checking {COIN_ID}…")
    price, p1h, p24h, p7d = fetch_price_data()
    if price is None:
        time.sleep(CHECK_INTERVAL)
        continue

    price_history.append(price)

    if initial_price is None:
        initial_price = price
        last_alert_price = price
        last_summary_time = datetime.now() - timedelta(days=1)

    # price-move alerts
    pct = (price - last_alert_price) / last_alert_price * 100
    if pct >= TARGET_PERCENT:
        tr = analyze_trend(price, p1h, p24h, p7d)
        pm = predict_next_move()
        send_market_alert(price, f"🎯 +{TARGET_PERCENT}% hit!", tr, pm)
        last_alert_price = price
    elif pct <= -TARGET_PERCENT:
        tr = analyze_trend(price, p1h, p24h, p7d)
        pm = predict_next_move()
        send_market_alert(price, f"📉 -{TARGET_PERCENT}% drop!", tr, pm)
        last_alert_price = price

    # new features
    rng = detect_range_opportunity(price_history)
    if rng:
        notify(rng)

    brk = detect_breakout(price_history, price)
    if brk:
        notify(brk)

    pred = simple_price_prediction(price, p1h, p24h, p7d)
    notify(pred)

    dca = detect_dca_opportunity(price_history)
    if dca:
        notify(dca)

    # periodic summary
    now = datetime.now()
    if now - last_summary_time >= timedelta(hours=SUMMARY_INTERVAL_HOURS):
        send_daily_summary()
        last_summary_time = now

    time.sleep(CHECK_INTERVAL)
