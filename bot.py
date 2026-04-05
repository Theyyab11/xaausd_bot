# 🚀 FAST PRO SNIPER BOT (Gold + BTC only, 5-min scan)

import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import threading
import requests

# ---------------- CONFIG ----------------
SYMBOLS = {
    "GOLD": "GC=F",
    "BTC": "BTC-USD"
}

ATR_PERIOD = 14
MIN_CONFIDENCE = 70  # sniper mode strength
COOLDOWN_PER_ASSET = 300  # 5 min per asset

TELEGRAM_TOKEN = "8601674578:AAHycLEx-6M_r_JHFuS96oKuLTBJqefwKnk"
CHAT_ID = "992623579"

last_signal_time = {key: 0 for key in SYMBOLS}
update_offset = None

# ---------------- HELPERS ----------------
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print("Telegram error:", e)

def get_active_symbols():
    return ["GOLD", "BTC"]

def get_data(symbol, period="2d", interval="1m"):
    try:
        df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
        df.dropna(inplace=True)
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"Yahoo download error ({symbol}):", e)
        return None

def atr(df):
    try:
        tr = pd.concat([
            df['High'] - df['Low'],
            abs(df['High'] - df['Close'].shift()),
            abs(df['Low'] - df['Close'].shift())
        ], axis=1).max(axis=1)
        return tr.rolling(ATR_PERIOD).mean()
    except:
        return pd.Series([0]*len(df))

# ---------------- SIGNAL LOGIC ----------------
def detect_bos(df):
    try:
        last = float(df['Close'].iloc[-1])
        high = float(df['High'].iloc[-3:-1].max())
        low = float(df['Low'].iloc[-3:-1].min())
        if last > high:
            return "BUY"
        elif last < low:
            return "SELL"
    except:
        pass
    return None

def detect_ob(df):
    try:
        last = df.iloc[-1]
        body = abs(float(last['Close']) - float(last['Open']))
        rng = float(last['High']) - float(last['Low'])
        if rng == 0:
            return None
        if body / rng > 0.6:
            return "BUY" if last['Close'] > last['Open'] else "SELL"
    except:
        pass
    return None

def momentum_strength(df):
    try:
        if len(df['Close']) < 5:
            return 0
        return abs(float(df['Close'].iloc[-1]) - float(df['Close'].iloc[-5]))
    except:
        return 0

def calculate_confidence(bos, ob, trend, momentum, atr_val):
    score = 0
    if bos: score += 25
    if ob: score += 25
    if bos is not None and ob is not None and bos == ob: score += 20
    if trend is not None and bos is not None and trend == bos: score += 15
    if momentum > (0.8 * atr_val): score += 15
    return min(score, 100)

def calculate_sl_tp(price, atr_val, direction):
    try:
        price = float(price)
        atr_val = float(atr_val)
        if direction == "BUY":
            return price - atr_val, price + (1.5 * atr_val)
        else:
            return price + atr_val, price - (1.5 * atr_val)
    except:
        return price, price

# ---------------- SNIPER SIGNAL ----------------
def generate_signal():
    signal_sent = False
    for asset in get_active_symbols():
        try:
            if time.time() - last_signal_time.get(asset, 0) < COOLDOWN_PER_ASSET:
                continue

            df_m1 = get_data(SYMBOLS[asset], "1d", "1m")
            df_m15 = get_data(SYMBOLS[asset], "5d", "15m")
            if df_m1 is None or df_m15 is None or df_m1.empty or df_m15.empty:
                continue

            atr_val = atr(df_m1).iloc[-1]
            if pd.isna(atr_val) or atr_val == 0:
                continue

            bos = detect_bos(df_m1)
            ob = detect_ob(df_m1)
            trend = "BUY" if float(df_m15['Close'].iloc[-1]) > float(df_m15['Close'].iloc[-3]) else "SELL"
            momentum = momentum_strength(df_m1)

            confidence = calculate_confidence(bos, ob, trend, momentum, atr_val)

            if confidence >= MIN_CONFIDENCE:
                direction = bos if bos else trend
                entry_price = float(df_m1['Close'].iloc[-1])
                sl, tp = calculate_sl_tp(entry_price, atr_val, direction)

                asset_name = {"GOLD": "🥇 Gold", "BTC": "🪙 BTC"}.get(asset, asset)

                msg = (
                    f"🎯 SNIPER SIGNAL 🎯\n"
                    f"Asset: {asset_name}\n"
                    f"Direction: {direction}\n"
                    f"Entry: {entry_price:.2f}\n"
                    f"SL: {sl:.2f} | TP: {tp:.2f}\n"
                    f"Confidence: {confidence}% 🔥"
                )
                send_telegram(msg)
                last_signal_time[asset] = time.time()
                signal_sent = True
        except Exception as e:
            print(f"Signal error ({asset}):", e)

    if not signal_sent:
        send_telegram("⏳ I am currently sniping...")

# ---------------- COMMANDS ----------------
def check_commands():
    global update_offset
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        if update_offset:
            url += f"?offset={update_offset}"
        res = requests.get(url, timeout=5).json()
        for upd in res.get("result", []):
            if "message" in upd:
                text = upd["message"].get("text", "").lower()
                if text == "/test":
                    send_telegram("✅ FAST PRO SNIPER BOT ACTIVE 🔥")
            update_offset = upd["update_id"] + 1
    except:
        pass

# ---------------- THREADS ----------------
def run_signals():
    while True:
        generate_signal()
        time.sleep(300)  # 5 min

def run_commands():
    while True:
        check_commands()
        time.sleep(2)

# ---------------- RUN ----------------
if __name__ == "__main__":
    print("🚀 FAST PRO SNIPER BOT RUNNING...")
    threading.Thread(target=run_signals, daemon=True).start()
    threading.Thread(target=run_commands, daemon=True).start()
    while True:
        time.sleep(1)
