# 🚀 XAUUSD ELITE SNIPER BOT (SMART MONEY VERSION)

import requests
import pandas as pd
import time
import threading
from datetime import datetime
import pytz
import yfinance as yf

# ---------------- CONFIG ----------------
SYMBOL = "GC=F"

TELEGRAM_TOKEN = "8601674578:AAHycLEx-6M_r_JHFuS96oKuLTBJqefwKnk"
CHAT_ID = "992623579"

ATR_PERIOD = 14
MIN_CONFIDENCE = 80

last_signal = None
last_sl_tp = None
update_offset = None

# ---------------- TELEGRAM ----------------
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram error:", e)

# ---------------- DATA ----------------
def fetch_data():
    try:
        df = yf.download(SYMBOL, period="1d", interval="1m")

        if df is None or df.empty:
            print("❌ No data from Yahoo")
            return None

        df = df.dropna()
        df.columns = [c.lower() for c in df.columns]

        print(f"✅ PRICE: {df['close'].iloc[-1]}")
        return df

    except Exception as e:
        print("Fetch error:", e)
        return None

# ---------------- INDICATORS ----------------
def atr(df):
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift()),
        abs(df['low'] - df['close'].shift())
    ], axis=1).max(axis=1)
    return tr.rolling(ATR_PERIOD).mean()

def ema(df, period=50):
    return df['close'].ewm(span=period).mean()

def momentum(df):
    return abs(df['close'].iloc[-1] - df['close'].iloc[-5])

# ---------------- SMART MONEY ----------------
def detect_bos(df):
    try:
        last = df['close'].iloc[-1]
        high = df['high'].iloc[-3:-1].max()
        low = df['low'].iloc[-3:-1].min()

        if last > high:
            return "BUY"
        elif last < low:
            return "SELL"
    except:
        pass
    return None

# ---------------- SIGNAL ENGINE ----------------
def generate_signal(force=False):
    global last_signal, last_sl_tp

    df = fetch_data()
    if df is None:
        return "❌ Market data unavailable"

    atr_val = atr(df).iloc[-1]
    if pd.isna(atr_val) or atr_val == 0:
        return "❌ ATR error"

    ema50 = ema(df).iloc[-1]
    price = df['close'].iloc[-1]
    mom = momentum(df)

    trend = "BUY" if price > ema50 else "SELL"
    bos = detect_bos(df)

    direction = bos if bos else trend

    # 🧠 Confidence system
    confidence = 60
    if bos: confidence += 20
    if mom > (0.5 * atr_val): confidence += 10
    if mom > (0.8 * atr_val): confidence += 10

    if not force and confidence < MIN_CONFIDENCE:
        return None

    # ⚠️ PRE SIGNAL
    if last_signal != direction:
        send_telegram("⚠️ BE READY - SMART MONEY IS MOVING...")

    entry_low = price - (0.2 * atr_val)
    entry_high = price + (0.2 * atr_val)

    if direction == "BUY":
        sl = price - 0.6 * atr_val
        tp = price + 1.2 * atr_val
    else:
        sl = price + 0.6 * atr_val
        tp = price - 1.2 * atr_val

    msg = f"""
🔥 XAUUSD ELITE SNIPER 🔥
━━━━━━━━━━━━━━━━━━━
📊 GOLD SCALPING (1M)

📍 DIRECTION: {direction}

🎯 ENTRY ZONE:
{entry_low:.2f} → {entry_high:.2f}

🛑 STOP LOSS: {sl:.2f}
💰 TAKE PROFIT: {tp:.2f}

⚡ CONFIDENCE: {confidence}%

🚀 EXECUTE WITH DISCIPLINE
━━━━━━━━━━━━━━━━━━━
"""

    last_signal = direction
    last_sl_tp = {"sl": sl, "tp": tp}

    return msg

# ---------------- COMMANDS ----------------
def check_commands():
    global update_offset

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        if update_offset:
            url += f"?offset={update_offset}"

        res = requests.get(url).json()

        for upd in res.get("result", []):
            if "message" in upd:
                text = upd["message"].get("text", "").lower()

                if text == "/test":
                    send_telegram("✅ ELITE BOT ACTIVE")

                elif text == "/price":
                    df = fetch_data()
                    if df is not None:
                        price = df['close'].iloc[-1]
                        send_telegram(f"💰 GOLD PRICE: {price:.2f}")

                elif text == "/signal":
                    send_telegram("⚡ SCANNING FOR SNIPER ENTRY...")
                    signal = generate_signal(force=True)
                    send_telegram(signal)

                elif text == "/status":
                    send_telegram("🟢 BOT RUNNING - SCANNING MARKET LIVE")

            update_offset = upd["update_id"] + 1

    except Exception as e:
        print("Command error:", e)

# ---------------- LOOPS ----------------
def run_bot():
    while True:
        signal = generate_signal()
        if signal:
            send_telegram(signal)
        time.sleep(60)

def run_commands():
    while True:
        check_commands()
        time.sleep(2)

# ---------------- START ----------------
if __name__ == "__main__":
    print("🚀 ELITE GOLD BOT RUNNING...")

    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=run_commands, daemon=True).start()

    while True:
        time.sleep(1)
