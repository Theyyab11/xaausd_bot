# ⚡ ROYAL FAST M1 SCALPER (XAUUSD & BTCUSD)
# 🎯 REAL-TIME ACCURACY: BINANCE WEBSOCKET + GOLD-API.COM (NO KEY REQUIRED)

import websocket
import json
import threading
import time
import pandas as pd
import requests
from datetime import datetime
import pytz

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = "8601674578:AAHycLEx-6M_r_JHFuS96oKuLTBJqefwKnk"
CHAT_ID = "992623579"

# Scalping Parameters
ATR_PERIOD = 14
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 7
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Trading Hours (UTC) - 10 AM GMT+4 is 6 AM UTC
TRADING_START_HOUR = 6
TRADING_END_HOUR = 22

# Data Storage
klines = {"BTCUSD": [], "XAUUSD": []}
last_signal_time = {"BTCUSD": 0, "XAUUSD": 0}

# ---------------- TELEGRAM ----------------
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})
    except Exception as e:
        print("Telegram error:", e)

# ---------------- INDICATORS ----------------
def calculate_indicators(df):
    # ATR
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_PERIOD).mean()

    # EMA
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    return df

# ---------------- SIGNAL ENGINE ----------------
def check_signal(symbol, df):
    global last_signal_time
    
    if len(df) < 30: return
    
    row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    price = row["close"]
    atr_val = row["atr"]
    rsi_val = row["rsi"]
    ema_f = row["ema_fast"]
    ema_s = row["ema_slow"]
    
    # M1 Scalping Logic: EMA Cross + RSI Confirmation
    direction = None
    if ema_f > ema_s and prev_row["ema_fast"] <= prev_row["ema_slow"] and rsi_val < 65:
        direction = "BUY"
    elif ema_f < ema_s and prev_row["ema_fast"] >= prev_row["ema_slow"] and rsi_val > 35:
        direction = "SELL"
        
    if direction:
        # Avoid duplicate signals within 5 minutes for M1
        if time.time() - last_signal_time[symbol] < 300:
            return
            
        # SL/TP for Scalping (Tight)
        if direction == "BUY":
            sl = price - (1.5 * atr_val)
            tp = price + (2.0 * atr_val)
        else:
            sl = price + (1.5 * atr_val)
            tp = price - (2.0 * atr_val)
            
        # Format message to match user's image
        msg = (
            f"<b>{symbol} {direction} NOW</b> 🔥\n\n"
            f"» POINT      : {price:.2f}\n"
            f"» STOPLOSS   : {sl:.2f}\n"
            f"» TAKE PROFIT : OPEN\n\n"
            f"<i>PLEASE ENSURE PROPER MONEY MANAGEMENT</i> ‼️\n"
            f"#168FX"
        )
        send_telegram(msg)
        last_signal_time[symbol] = time.time()

# ---------------- DATA FETCHING ----------------
def fetch_gold_price():
    # Gold-API.com for Gold (REST) - No Key Required
    # Free endpoint: https://api.gold-api.com/price/XAU/USD
    while True:
        try:
            url = "https://api.gold-api.com/price/XAU/USD"
            res = requests.get(url).json()
            if "price" in res:
                price = float(res["price"])
                # Build M1 candles from prices
                klines["XAUUSD"].append({
                    "close": price, "high": price, "low": price, "open": price
                })
                if len(klines["XAUUSD"]) > 100: klines["XAUUSD"].pop(0)
                df = pd.DataFrame(klines["XAUUSD"])
                df = calculate_indicators(df)
                check_signal("XAUUSD", df)
            time.sleep(60) # Recommended interval to avoid IP block
        except Exception as e:
            print(f"Gold fetch error: {e}")
            time.sleep(60)

def on_btc_message(ws, message):
    data = json.loads(message)
    if "k" in data:
        k = data["k"]
        if k["x"]: # Candle closed
            klines["BTCUSD"].append({
                "open": float(k["o"]),
                "high": float(k["h"]),
                "low": float(k["l"]),
                "close": float(k["c"]),
                "volume": float(k["v"])
            })
            if len(klines["BTCUSD"]) > 100: klines["BTCUSD"].pop(0)
            df = pd.DataFrame(klines["BTCUSD"])
            df = calculate_indicators(df)
            check_signal("BTCUSD", df)

def run_btc_ws():
    ws_url = "wss://fstream.binance.com/ws/btcusdt@kline_1m"
    ws = websocket.WebSocketApp(ws_url, on_message=on_btc_message)
    ws.run_forever()

# ---------------- START ----------------
if __name__ == "__main__":
    print("🚀 ROYAL FAST M1 SCALPER STARTING...")
    send_telegram("✅ ROYAL M1 SCALPER ONLINE - REAL-TIME MODE")
    
    # Start BTC WebSocket
    threading.Thread(target=run_btc_ws, daemon=True).start()
    
    # Start Gold REST Fetcher
    threading.Thread(target=fetch_gold_price, daemon=True).start()
    
    while True:
        time.sleep(1)
