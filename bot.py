
import requests
import pandas as pd
import time
import threading
from datetime import datetime
import pytz
import yfinance as yf

# ---------------- CONFIG ----------------
SYMBOL = "GC=F" # Gold Futures (COMEX) - Reliable free source on Yahoo Finance
TELEGRAM_TOKEN = "8601674578:AAHycLEx-6M_r_JHFuS96oKuLTBJqefwKnk"
CHAT_ID = "992623579"

# Indicator Periods
ATR_PERIOD = 14
EMA_FAST = 20
EMA_SLOW = 50

# Signal Confidence
MIN_CONFIDENCE = 75 

# Trading hours (UTC) - 10 AM GMT+4 is 6 AM UTC, 5 PM GMT+4 is 1 PM UTC
TRADING_START_HOUR = 6
TRADING_END_HOUR = 17

# Global variables for signal tracking
last_signal_time = None
last_signal_direction = None
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
def fetch_data(retries=3, delay=5):
    for attempt in range(retries):
        try:
            # Using yfinance for reliable free data
            # GC=F is Gold Futures, very close to XAUUSD spot price
             data = yf.download(SYMBOL, period="100d", interval="1d", progress=False)
            
            if data.empty:
                print(f"Attempt {attempt+1}: No data returned from yfinance.")
                time.sleep(delay)
                continue
            
            # Flatten multi-index columns if they exist (yfinance v1.2.1+ behavior)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            # Standardize column names to lowercase
            df = data.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })
            
            # Ensure data types are float
            for col in ["open","high","low","close"]:
                df[col] = df[col].astype(float)
            
            # Ensure enough data for indicators
            required_data_points = max(ATR_PERIOD, EMA_SLOW) + 5
            if len(df) < required_data_points:
                print(f"Not enough data for full analysis. Need at least {required_data_points} days, got {len(df)}.")
                # Fallback: if not enough data for full analysis, try with what's available
                if len(df) < ATR_PERIOD or len(df) < EMA_SLOW:
                    print("Critically low data. Cannot proceed with signal generation.")
                    return None

            return df

            return df
        except Exception as e:
            print(f"Attempt {attempt+1}: Data fetching error: {e}")
            time.sleep(delay)
    
    print("Failed to fetch market data after multiple attempts.")
    return None

# ---------------- INDICATORS ----------------
def atr(df):
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)
    return tr.rolling(ATR_PERIOD).mean()

def ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()

def rsi(df, period=14):
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def is_uptrend(df, periods=5):
    if len(df) < periods: return False
    recent_df = df.iloc[-periods:]
    return all(recent_df["low"].diff().dropna() > 0) and all(recent_df["high"].diff().dropna() > 0)

def is_downtrend(df, periods=5):
    if len(df) < periods: return False
    recent_df = df.iloc[-periods:]
    return all(recent_df["low"].diff().dropna() < 0) and all(recent_df["high"].diff().dropna() < 0)

def find_zones(df, window=10, threshold_atr_multiplier=1.5):
    zones = []
    atr_val = atr(df).iloc[-1] if len(df) >= ATR_PERIOD else 0.01 # Fallback for ATR
    if pd.isna(atr_val) or atr_val == 0: atr_val = 0.01 # Ensure ATR is never zero or NaN for calculations

    for i in range(window, len(df) - 1):
        high_range = df["high"].iloc[i-window:i].max()
        low_range = df["low"].iloc[i-window:i].min()
        if (high_range - low_range) < (threshold_atr_multiplier * atr_val):
            zone_avg = (high_range + low_range) / 2
            zone_size = (high_range - low_range) / 2
            zones.append({"type": "consolidation", "level": zone_avg, "range": zone_size})
    return zones

# ---------------- SIGNAL ENGINE ----------------
def generate_signal(force_signal=False):
    global last_signal_time, last_signal_direction, last_sl_tp
    
    now_utc = datetime.now(pytz.utc)
    if not force_signal and not (TRADING_START_HOUR <= now_utc.hour < TRADING_END_HOUR):
        print(f"Current UTC hour {now_utc.hour} is outside trading hours. Skipping.")
        return

    if not force_signal and last_signal_time and (now_utc - last_signal_time).total_seconds() < 1800:
        print("Skipping: Too soon since last signal.")
        return

    df = fetch_data()
    if df is None or df.empty: return

    atr_val = atr(df).iloc[-1] if len(df) >= ATR_PERIOD else 0.01 # Fallback for ATR
    if pd.isna(atr_val) or atr_val == 0: atr_val = 0.01 # Ensure ATR is never zero or NaN for calculations

    ema_fast = ema(df, EMA_FAST).iloc[-1] if len(df) >= EMA_FAST else df["close"].iloc[-1]
    ema_slow = ema(df, EMA_SLOW).iloc[-1] if len(df) >= EMA_SLOW else df["close"].iloc[-1]
    rsi_val = rsi(df).iloc[-1] if len(df) >= 14 else 50 # Fallback for RSI (neutral)
    price = df["close"].iloc[-1]
    
    current_trend = "UPTREND" if is_uptrend(df) else ("DOWNTREND" if is_downtrend(df) else "SIDEWAYS")
    zones = find_zones(df)

    primary_direction = "BUY" if ema_fast > ema_slow else "SELL"
    confidence = 50
    analysis_text = []

    # EMA Cross
    if primary_direction == "BUY" and df["close"].iloc[-2] <= ema_slow and price > ema_slow:
        confidence += 15
        analysis_text.append("EMA Crossover (Bullish)")
    elif primary_direction == "SELL" and df["close"].iloc[-2] >= ema_slow and price < ema_slow:
        confidence += 15
        analysis_text.append("EMA Crossover (Bearish)")
    else:
        primary_direction = "NONE"

    if primary_direction == "NONE":
        if force_signal:
            send_telegram("⚠️ No strong EMA crossover found. Analysis continues with trend.")
            primary_direction = "BUY" if ema_fast > ema_slow else "SELL" # Default to trend
        else:
            print("No strong EMA crossover signal. Skipping.")
            return

    # Trend
    if primary_direction == "BUY" and current_trend == "UPTREND":
        confidence += 20
        analysis_text.append("Confirmed Uptrend")
    elif primary_direction == "SELL" and current_trend == "DOWNTREND":
        confidence += 20
        analysis_text.append("Confirmed Downtrend")
    else:
        confidence -= 10
        analysis_text.append(f"Trend ({current_trend}) not aligned.")

    # Zones
    zone_found = False
    for zone in zones:
        if abs(price - zone["level"]) < (zone["range"] + 0.5 * atr_val):
            confidence += 15
            analysis_text.append(f"Near Zone ({zone['level']:.2f})")
            zone_found = True
            break
    if not zone_found: analysis_text.append("No clear zone.")

    # RSI
    if primary_direction == "BUY" and rsi_val < 40:
        confidence += 10
        analysis_text.append(f"RSI ({rsi_val:.2f}) Oversold")
    elif primary_direction == "SELL" and rsi_val > 60:
        confidence += 10
        analysis_text.append(f"RSI ({rsi_val:.2f}) Overbought")
    else:
        analysis_text.append(f"RSI ({rsi_val:.2f}) Neutral")

    if confidence < MIN_CONFIDENCE:
        if force_signal and confidence >= 60:
            analysis_text.append(f"Forced: Confidence {confidence}%")
        else:
            if force_signal: send_telegram(f"⚠️ Weak signal (Confidence: {confidence}%). Waiting for better setup.")
            return

    # Signal Generation
    direction = primary_direction
    entry_buffer = 0.1 * atr_val
    entry_low = price - entry_buffer
    entry_high = price + entry_buffer

    if direction == "BUY":
        sl = price - 1.0 * atr_val
        tp1 = price + 1.0 * atr_val
        tp2 = price + 2.0 * atr_val
        tp3 = price + 3.0 * atr_val
    else:
        sl = price + 1.0 * atr_val
        tp1 = price - 1.0 * atr_val
        tp2 = price - 2.0 * atr_val
        tp3 = price - 3.0 * atr_val

    if not force_signal and last_signal_direction == direction and last_sl_tp and \
       abs(last_sl_tp["entry_low"] - entry_low) < (0.1 * atr_val):
        return

    msg = (
        f"🚀 ROYAL XAUUSD ELITE SIGNAL\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 Asset: XAUUSD (GOLD)\n"
        f"🕒 Timeframe: Daily Analysis\n"
        f"💡 Type: {direction} ZONE\n\n"
        f"📍 Entry: {entry_low:.2f} - {entry_high:.2f}\n"
        f"🎯 TP 1: {tp1:.2f}\n"
        f"🎯 TP 2: {tp2:.2f}\n"
        f"🎯 TP 3: {tp3:.2f}\n"
        f"🛑 SL: {sl:.2f}\n\n"
        f"🔍 Analysis: {'; '.join(analysis_text)}. Confidence: {confidence}%\n"
        f"━━━━━━━━━━━━━━━"
    )

    send_telegram(msg)
    last_signal_time = now_utc
    last_signal_direction = direction
    last_sl_tp = {"sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3, "direction": direction, "entry_low": entry_low, "entry_high": entry_high}

# ---------------- TP/SL MONITOR ----------------
def monitor_tp_sl():
    global last_sl_tp
    while True:
        if last_sl_tp is None: 
            time.sleep(10)
            continue
        df = fetch_data()
        if df is None or df.empty:
            time.sleep(10)
            continue
        price = df["close"].iloc[-1]
        sl = last_sl_tp["sl"]
        tp1, tp2, tp3 = last_sl_tp["tp1"], last_sl_tp["tp2"], last_sl_tp["tp3"]
        direction = last_sl_tp["direction"]

        if direction == "BUY":
            if price <= sl:
                send_telegram(f"❌ BUY SL HIT at {price:.2f}")
                last_sl_tp = None
            elif price >= tp3:
                send_telegram(f"✅ BUY TP3 HIT at {price:.2f}")
                last_sl_tp = None
            elif price >= tp1:
                send_telegram(f"✅ BUY TP1 HIT at {price:.2f}")
        else:
            if price >= sl:
                send_telegram(f"❌ SELL SL HIT at {price:.2f}")
                last_sl_tp = None
            elif price <= tp3:
                send_telegram(f"✅ SELL TP3 HIT at {price:.2f}")
                last_sl_tp = None
            elif price <= tp1:
                send_telegram(f"✅ SELL TP1 HIT at {price:.2f}")
        time.sleep(60)

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
                    send_telegram("🔥 ROYAL XAUUSD ELITE BOT ACTIVE")
                elif text == "/signal":
                    send_telegram("🔍 Analyzing chart for a strong signal...")
                    generate_signal(force_signal=True)
                elif text == "/price":
                    df = fetch_data()
                    if df is not None:
                        send_telegram(f"💰 XAUUSD Price: {df['close'].iloc[-1]:.2f}")
            update_offset = upd["update_id"] + 1
    except Exception as e:
        print("Command error:", e)

def check_commands_loop():
    while True:
        check_commands()
        time.sleep(2)

def run_auto_signaler():
    while True:
        generate_signal()
        time.sleep(300)

if __name__ == "__main__":
    print("🚀 ROYAL XAUUSD ELITE BOT RUNNING (YFINANCE)...")
    threading.Thread(target=run_auto_signaler, daemon=True).start()
    threading.Thread(target=check_commands_loop, daemon=True).start()
    threading.Thread(target=monitor_tp_sl, daemon=True).start()
    while True:
        time.sleep(1)
