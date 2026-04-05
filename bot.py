# 🚀 XAUUSD ELITE M1 SCALPER BOT (TWELVEDATA LIVE MARKET)

import requests
import pandas as pd
import time
import threading
from datetime import datetime
import pytz

# ---------------- CONFIG ----------------
SYMBOL = "XAU/USD"
API_KEY = "c3c3a13b07cb486b81622aa58a73e9c0"  # Updated Twelve Data API
TELEGRAM_TOKEN = "8601674578:AAHycLEx-6M_r_JHFuS96oKuLTBJqefwKnk"
CHAT_ID = "992623579"

ATR_PERIOD = 14
EMA_FAST = 20
EMA_SLOW = 50
MIN_CONFIDENCE = 90

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
def fetch_data(retries=3, delay=1):
    for attempt in range(retries):
        try:
            url = f"https://api.twelvedata.com/time_series?symbol={SYMBOL}&interval=1min&outputsize=100&apikey={API_KEY}"
            res = requests.get(url, timeout=5).json()
            if "values" not in res:
                print(f"Attempt {attempt+1}: Market data unavailable or API limit reached")
                time.sleep(delay)
                continue
            df = pd.DataFrame(res["values"])[::-1]  # oldest to newest
            for col in ["open","high","low","close"]:
                df[col] = df[col].astype(float)
            return df
        except Exception as e:
            print(f"Attempt {attempt+1}: Fetch error:", e)
            time.sleep(delay)
    return None

# ---------------- INDICATORS ----------------
def atr(df):
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift()),
        abs(df['low'] - df['close'].shift())
    ], axis=1).max(axis=1)
    return tr.rolling(ATR_PERIOD).mean()

def ema(df, period):
    return df['close'].ewm(span=period).mean()

def momentum(df):
    return abs(df['close'].iloc[-1] - df['close'].iloc[-5])

# ---------------- SIGNAL ENGINE ----------------
def generate_signal(be_ready=False):
    global last_signal, last_sl_tp
    df = fetch_data()
    if df is None or df.empty: return

    atr_val = atr(df).iloc[-1]
    if pd.isna(atr_val) or atr_val == 0: return

    ema_fast = ema(df, EMA_FAST).iloc[-1]
    ema_slow = ema(df, EMA_SLOW).iloc[-1]
    price = df['close'].iloc[-1]
    mom = momentum(df)

    direction = "BUY" if ema_fast > ema_slow else "SELL"

    confidence = 70
    if mom > 0.5 * atr_val: confidence += 10
    if mom > 0.8 * atr_val: confidence += 10
    if (direction=="BUY" and price>ema_slow) or (direction=="SELL" and price<ema_slow): confidence += 10

    if confidence < MIN_CONFIDENCE: return

    if be_ready:
        send_telegram(f"⚠️ BE READY — {direction} ZONE NOW! Prepare!")
        return

    entry_low = price - 0.05 * atr_val
    entry_high = price + 0.05 * atr_val

    if direction == "BUY":
        sl = price - 0.5 * atr_val
        tp = price + 1.5 * atr_val
    else:
        sl = price + 0.5 * atr_val
        tp = price - 1.5 * atr_val

    msg = (
        f"🚀 ELITE GOLD M1 SCALPER SIGNAL\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 XAUUSD (1M)\n"
        f"📍 {direction}\n"
        f"🎯 Entry: {entry_low:.2f} - {entry_high:.2f}\n"
        f"🛑 SL: {sl:.2f}\n"
        f"💰 TP: {tp:.2f}\n"
        f"⚡ Confidence: {confidence}%\n"
        f"━━━━━━━━━━━━━━━"
    )

    send_telegram(msg)
    last_signal = direction
    last_sl_tp = {"sl": sl, "tp": tp}

# ---------------- TELEGRAM COMMANDS ----------------
def check_commands():
    global update_offset
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        if update_offset: url += f"?offset={update_offset}"
        res = requests.get(url, timeout=5).json()
        for upd in res.get("result", []):
            if "message" in upd:
                text = upd["message"].get("text", "").lower()
                if text == "/test":
                    send_telegram("🔥 ELITE GOLD M1 SCALPER BOT ACTIVE")
                elif text == "/signal":
                    generate_signal()
                elif text == "/price":
                    df = fetch_data()
                    if df is not None:
                        send_telegram(f"💰 XAUUSD Price: {df['close'].iloc[-1]:.2f}")
                    else:
                        send_telegram("⚠️ Market data unavailable")
            update_offset = upd["update_id"] + 1
    except Exception as e:
        print("Command error:", e)

def check_commands_loop():
    while True:
        check_commands()
        time.sleep(2)

# ---------------- AUTO SCALP LOOP ----------------
def run_auto_scalper():
    while True:
        df = fetch_data()
        if df is not None:
            generate_signal(be_ready=True)  # BE READY alert 10 sec
            time.sleep(10)
            generate_signal(be_ready=False)  # Actual M1 signal
        time.sleep(60)  # Wait 1 minute for next candle

# ---------------- START ----------------
if __name__ == "__main__":
    print("🚀 ELITE GOLD M1 SCALPER BOT RUNNING...")
    threading.Thread(target=run_auto_scalper, daemon=True).start()
    threading.Thread(target=check_commands_loop, daemon=True).start()
    while True:
        time.sleep(1)
