import requests
import time
import os
from datetime import datetime, timedelta
from collections import deque

COIN_ID = "sui"
VS_CURRENCY = "usd"
TARGET_PERCENT = 5
CHECK_INTERVAL = 60  # seconds

PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_APP_TOKEN = os.environ.get("PUSHOVER_APP_TOKEN")

print("App Token:", PUSHOVER_APP_TOKEN)
print("User Key:", PUSHOVER_USER_KEY)

initial_price = None
last_alert_price = None
last_summary_time = datetime.now() - timedelta(hours=24)
price_history = deque(maxlen=10)

def fetch_price_data():
    url = f"https://api.coingecko.com/api/v3/coins/{COIN_ID}?localization=false&tickers=false&market_data=true"
    try:
        response = requests.get(url)
        data = response.json()
        price = data["market_data"]["current_price"][VS_CURRENCY]
        percent_1h = data["market_data"].get("price_change_percentage_1h_in_currency", {}).get(VS_CURRENCY, 0)
        percent_24h = data["market_data"].get("price_change_percentage_24h_in_currency", {}).get(VS_CURRENCY, 0)
        percent_7d = data["market_data"].get("price_change_percentage_7d_in_currency", {}).get(VS_CURRENCY, 0)
        return price, percent_1h, percent_24h, percent_7d
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None, None, None, None

def analyze_trend(price, p1h, p24h, p7d):
    if p1h > 1 and p24h > 2:
        return f"🟢 Uptrend: 1h +{p1h:.2f}%, 24h +{p24h:.2f}% — {COIN_ID.upper()} gaining."
    elif p1h < -1 and p24h > 2:
        return f"🟡 Pullback: 1h {p1h:.2f}% drop, but 24h +{p24h:.2f}% uptrend continues."
    elif p24h < 0 and p7d < 0:
        return f"🔴 Downtrend: 24h {p24h:.2f}%, 7d {p7d:.2f}% — avoid buying now."
    else:
        return f"⚪ Sideways: 1h {p1h:.2f}%, 24h {p24h:.2f}%, 7d {p7d:.2f}%."

def predict_next_move():
    if len(price_history) < 5:
        return None
    short_ma = sum(list(price_history)[-3:]) / 3
    long_ma = sum(list(price_history)[-5:]) / 5
    if short_ma > long_ma:
        return "📈 Momentum up: short-term prices rising above average."
    elif short_ma < long_ma:
        return "📉 Weakening: short-term prices below average."
    return "- No clear direction."

def notify(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    url = "https://api.pushover.net/1/messages.json"
    payload = {
        "token": PUSHOVER_APP_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"Notification error: {response.text}")
    except Exception as e:
        print(f"Pushover exception: {e}")

def send_market_alert(price, direction, trend, prediction):
    notify(f"{direction} {COIN_ID.upper()} at ${price:.4f}")
    notify(trend)
    if prediction:
        notify(prediction)

def send_daily_summary():
    latest_price = price_history[-1] if price_history else None
    if not latest_price:
        return
    p1h, p24h, p7d = fetch_price_data()[1:]  # skip price
    trend = analyze_trend(latest_price, p1h, p24h, p7d)
    prediction = predict_next_move()
    message = f"📊 Daily Summary for {COIN_ID.upper()} — Price: ${latest_price:.4f}\n{trend}"
    if prediction:
        message += f"\n{prediction}"
    notify(message)

while True:
    print(f"[{datetime.now()}] Checking {COIN_ID}...")
    price, p1h, p24h, p7d = fetch_price_data()

    if price is None:
        time.sleep(CHECK_INTERVAL)
        continue

    price_history.append(price)

    if initial_price is None:
        initial_price = price
        last_alert_price = price
        last_summary_time = datetime.now() - timedelta(days=1)  # force first summary

    percent_change = ((price - last_alert_price) / last_alert_price) * 100

    if percent_change >= TARGET_PERCENT:
        trend = analyze_trend(price, p1h, p24h, p7d)
        prediction = predict_next_move()
        send_market_alert(price, f"🎯 +{TARGET_PERCENT}% target hit!", trend, prediction)
        last_alert_price = price

    elif percent_change <= -TARGET_PERCENT:
        trend = analyze_trend(price, p1h, p24h, p7d)
        prediction = predict_next_move()
        send_market_alert(price, f"📉 Dropped -{TARGET_PERCENT}% — buy signal!", trend, prediction)
        last_alert_price = price

    # Daily summary every 24 hours
    now = datetime.now()
    if now - last_summary_time >= timedelta(hours=24):
        send_daily_summary()
        last_summary_time = now

    time.sleep(CHECK_INTERVAL)
