# 🚀 ROYAL ELITE MULTI-SYMBOL SNIPER BOT (XAUUSD & BTCUSD)
# 💎 STRONGEST VERSION: RSI + EMA + MACD + ATR

import requests
import pandas as pd
import time
import threading
from datetime import datetime
import pytz
import yfinance as yf

# ---------------- CONFIG ----------------
# Symbols: GC=F (Gold Futures for XAUUSD), BTC-USD (Bitcoin)
SYMBOLS = {
    "XAUUSD": "GC=F",
    "BTCUSD": "BTC-USD"
}
TELEGRAM_TOKEN = "8601674578:AAHycLEx-6M_r_JHFuS96oKuLTBJqefwKnk"
CHAT_ID = "992623579"

# Indicator Periods
ATR_PERIOD = 14
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Signal Confidence
MIN_CONFIDENCE = 80 

# Trading hours (UTC) - 10 AM GMT+4 is 6 AM UTC
TRADING_START_HOUR = 6
TRADING_END_HOUR = 22 # Extended for crypto

# Global variables for signal tracking
last_signals = {s: {"time": None, "direction": None, "sl_tp": None} for s in SYMBOLS}
update_offset = None

# ---------------- TELEGRAM ----------------
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram error:", e)

# ---------------- DATA ----------------
def fetch_data(symbol_key, retries=3, delay=5):
    yf_symbol = SYMBOLS[symbol_key]
    for attempt in range(retries):
        try:
            # Fetch 1-hour data for better precision than daily, but stable enough for signals
            data = yf.download(yf_symbol, period="15d", interval="1h", progress=False)
            
            if data.empty:
                time.sleep(delay)
                continue
            
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            df = data.rename(columns={
                "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"
            })
            
            for col in ["open","high","low","close"]:
                df[col] = df[col].astype(float)
            
            return df
        except Exception as e:
            print(f"Fetch error for {symbol_key}: {e}")
            time.sleep(delay)
    return None

# ---------------- INDICATORS ----------------
def calculate_indicators(df):
    # ATR
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(ATR_PERIOD).mean()

    # EMA
    df['ema_fast'] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df['ema_slow'] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # MACD
    df['macd_line'] = df['close'].ewm(span=MACD_FAST, adjust=False).mean() - df['close'].ewm(span=MACD_SLOW, adjust=False).mean()
    df['macd_signal'] = df['macd_line'].ewm(span=MACD_SIGNAL, adjust=False).mean()
    df['macd_hist'] = df['macd_line'] - df['macd_signal']

    return df

# ---------------- SIGNAL ENGINE ----------------
def generate_signal(symbol_key, force_signal=False):
    global last_signals
    
    now_utc = datetime.now(pytz.utc)
    
    # BTC works 24/7, Gold has market hours
    if symbol_key == "XAUUSD":
        if not force_signal and not (TRADING_START_HOUR <= now_utc.hour < TRADING_END_HOUR):
            return
        if now_utc.weekday() >= 5: # Weekend
            if force_signal: send_telegram("⚠️ Gold market is closed on weekends.")
            return

    df = fetch_data(symbol_key)
    if df is None or df.empty: return
    df = calculate_indicators(df)

    row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    price = row['close']
    atr_val = row['atr']
    rsi_val = row['rsi']
    macd_hist = row['macd_hist']
    ema_fast = row['ema_fast']
    ema_slow = row['ema_slow']

    confidence = 0
    analysis = []

    # 1. EMA Trend (Base)
    if ema_fast > ema_slow:
        direction = "BUY"
        confidence += 30
        analysis.append("Bullish Trend (EMA)")
    else:
        direction = "SELL"
        confidence += 30
        analysis.append("Bearish Trend (EMA)")

    # 2. MACD Confirmation
    if direction == "BUY" and macd_hist > 0:
        confidence += 20
        analysis.append("MACD Positive")
    elif direction == "SELL" and macd_hist < 0:
        confidence += 20
        analysis.append("MACD Negative")

    # 3. RSI Confirmation
    if direction == "BUY":
        if rsi_val < 40: 
            confidence += 20
            analysis.append("RSI Oversold")
        elif rsi_val < 60:
            confidence += 10
            analysis.append("RSI Bullish")
    else:
        if rsi_val > 60:
            confidence += 20
            analysis.append("RSI Overbought")
        elif rsi_val > 40:
            confidence += 10
            analysis.append("RSI Bearish")

    # 4. Price Action (EMA Cross)
    if direction == "BUY" and prev_row['close'] < ema_fast and price > ema_fast:
        confidence += 20
        analysis.append("Price Cross Above EMA")
    elif direction == "SELL" and prev_row['close'] > ema_fast and price < ema_fast:
        confidence += 20
        analysis.append("Price Cross Below EMA")

    if confidence < MIN_CONFIDENCE and not force_signal:
        return

    # Entry/SL/TP Logic
    entry_low = price - (0.05 * atr_val)
    entry_high = price + (0.05 * atr_val)
    
    if direction == "BUY":
        sl = price - (1.5 * atr_val)
        tp1 = price + (1.5 * atr_val)
        tp2 = price + (3.0 * atr_val)
    else:
        sl = price + (1.5 * atr_val)
        tp1 = price - (1.5 * atr_val)
        tp2 = price - (3.0 * atr_val)

    # Avoid duplicate signals
    if not force_signal and last_signals[symbol_key]["direction"] == direction:
        if (now_utc - last_signals[symbol_key]["time"]).total_seconds() < 7200: # 2 hours
            return

    msg = (
        f"🔥 ROYAL {symbol_key} ELITE SIGNAL\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 Asset: {symbol_key}\n"
        f"💡 Type: {direction} NOW\n\n"
        f"📍 Entry: {entry_low:.2f} - {entry_high:.2f}\n"
        f"🎯 TP 1: {tp1:.2f}\n"
        f"🎯 TP 2: {tp2:.2f}\n"
        f"🛑 SL: {sl:.2f}\n\n"
        f"🔍 Analysis: {', '.join(analysis)}\n"
        f"⚡ Confidence: {confidence}%\n"
        f"━━━━━━━━━━━━━━━"
    )

    send_telegram(msg)
    last_signals[symbol_key] = {
        "time": now_utc,
        "direction": direction,
        "sl_tp": {"sl": sl, "tp1": tp1, "tp2": tp2, "direction": direction}
    }

# ---------------- COMMANDS ----------------
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
                    send_telegram("✅ ROYAL SNIPER BOT ONLINE")
                elif text == "/signal":
                    send_telegram("🔍 Scanning markets for strongest setups...")
                    generate_signal("XAUUSD", force_signal=True)
                    generate_signal("BTCUSD", force_signal=True)
                elif text == "/price":
                    prices = []
                    for k in SYMBOLS:
                        df = fetch_data(k)
                        if df is not None: prices.append(f"{k}: {df['close'].iloc[-1]:.2f}")
                    send_telegram("💰 Current Prices:\n" + "\n".join(prices))
            update_offset = upd["update_id"] + 1
    except Exception as e:
        print("Command error:", e)

# ---------------- LOOPS ----------------
def auto_loop():
    while True:
        for s in SYMBOLS:
            generate_signal(s)
            time.sleep(5)
        time.sleep(300) # Check every 5 mins

def command_loop():
    while True:
        check_commands()
        time.sleep(2)

if __name__ == "__main__":
    print("🚀 ROYAL ELITE BOT STARTING...")
    threading.Thread(target=auto_loop, daemon=True).start()
    threading.Thread(target=command_loop, daemon=True).start()
    while True:
        time.sleep(1)
