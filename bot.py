# 📌 Institutional XAUUSD Signal Bot → Ready Alerts + Smart Risk Signals
# ✅ Features: M1 + M15 trend filter, BOS, Order Blocks, ATR-based SL/TP, Kill Zones
# 🚀 Sends signals only when conditions are favorable
# 🔹 Includes risk assessment and "Be ready" alerts

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timezone
import asyncio
import aiohttp

# ---------------- CONFIG ----------------
SYMBOL = "XAUUSD=X"
TIMEFRAME = "1m"
TIMEFRAME_M15 = "15m"
ATR_PERIOD = 14
TP_ATR = 1.5
SL_ATR = 1
KILL_ZONES = [("09:00", "11:00"), ("13:00", "15:00")]

TELEGRAM_TOKEN = "8601674578:AAHycLEx-6M_r_JHFuS96oKuLTBJqefwKnk"
CHAT_ID = "992623579"
update_offset = None

# ---------------- HELPERS ----------------
async def send_telegram(message, chat_id=CHAT_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, data={"chat_id": chat_id, "text": message})

def get_data(symbol, period="2d", interval="1m"):
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
    df.dropna(inplace=True)
    return df

def atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift())
    low_close = abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def in_kill_zone():
    now = datetime.now(timezone.utc).time()
    for start, end in KILL_ZONES:
        start_t = time(int(start.split(":")[0]), int(start.split(":")[1]))
        end_t = time(int(end.split(":")[0]), int(end.split(":")[1]))
        if start_t <= now <= end_t:
            return True
    return False

def detect_bos(df):
    if len(df) < 3:
        return None
    if df['Close'].iloc[-1] > df['High'].iloc[-3:-1].max():
        return "BOS_UP"
    elif df['Close'].iloc[-1] < df['Low'].iloc[-3:-1].min():
        return "BOS_DOWN"
    return None

def detect_order_block(df):
    last = df.iloc[-1]
    body = abs(last['Close'] - last['Open'])
    candle_range = last['High'] - last['Low']
    if candle_range == 0:
        return None
    if body / candle_range > 0.7:
        if last['Close'] > last['Open']:
            return "BUY_OB"
        else:
            return "SELL_OB"
    return None

def calculate_sl_tp(price, atr_value, direction):
    if direction == "BUY":
        sl = price - SL_ATR * atr_value
        tp = price + TP_ATR * atr_value
    else:
        sl = price + SL_ATR * atr_value
        tp = price - TP_ATR * atr_value
    return sl, tp

# ---------------- SIGNAL GENERATOR ----------------
async def generate_signal():
    if not in_kill_zone():
        print("⏱️ Outside Kill Zones.")
        return

    df_m1 = get_data(SYMBOL, period="1d", interval="1m")
    df_m15 = get_data(SYMBOL, period="5d", interval="15m")
    atr_m1 = atr(df_m1, ATR_PERIOD).iloc[-1]

    bos_signal = detect_bos(df_m1)
    ob_signal = detect_order_block(df_m1)

    trend_m15 = "BUY" if df_m15['Close'].iloc[-1] > df_m15['Close'].iloc[-3] else "SELL"

    direction = None
    risk_percent = 50

    if bos_signal and ob_signal:
        if bos_signal == "BOS_UP" and ob_signal == "BUY_OB" and trend_m15 == "BUY":
            direction = "BUY"
            risk_percent = 85
        elif bos_signal == "BOS_DOWN" and ob_signal == "SELL_OB" and trend_m15 == "SELL":
            direction = "SELL"
            risk_percent = 85
        else:
            direction = "BUY" if trend_m15 == "BUY" else "SELL"
            risk_percent = 40

    if direction:
        # Send "Be ready" alert first
        ready_msg = "⚡ Be ready! Potential XAUUSD signal detected. Monitoring M1..."
        await send_telegram(ready_msg)

        # Wait a short time to confirm signal (simulate live market wait)
        await asyncio.sleep(10)  # 10 seconds for example, can increase

        # Send full signal
        price = df_m1['Close'].iloc[-1]
        sl, tp = calculate_sl_tp(price, atr_m1, direction)
        message = (
            f"💰 XAUUSD SIGNAL 💰\n"
            f"Direction: {direction}\n"
            f"Entry: {price:.2f}\n"
            f"SL: {sl:.2f} | TP: {tp:.2f}\n"
            f"Risk: {risk_percent}% {'✅ Safe' if risk_percent>=70 else '⚠️ Risky'}\n"
            f"Kill Zone: Active 🔥"
        )
        await send_telegram(message)
        print("✅ Signal sent!")
    else:
        print("❌ No valid signal now.")

# ---------------- TEST SIGNAL ----------------
async def generate_test_signal(chat_id):
    message = (
        "💰 XAUUSD SIGNAL (TEST) 💰\n"
        "Direction: BUY\n"
        "Entry: 1965.50\n"
        "SL: 1960.50 | TP: 1975.50\n"
        "Risk: 80% ✅ Safe\n"
        "Kill Zone: Active 🔥\n"
        "This is a test example signal"
    )
    await send_telegram(message, chat_id)
    print("✅ Test signal sent!")

# ---------------- TELEGRAM COMMAND CHECK ----------------
async def check_for_commands():
    global update_offset
    async with aiohttp.ClientSession() as session:
        while True:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?timeout=10"
            if update_offset:
                url += f"&offset={update_offset}"
            async with session.get(url) as resp:
                data = await resp.json()
            for update in data.get("result", []):
                update_offset = update["update_id"] + 1
                if "message" in update:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"].get("text", "")
                    if text.lower() == "/test":
                        await generate_test_signal(chat_id)
            await asyncio.sleep(1)

# ---------------- RUN ASYNC ----------------
async def main():
    async def signal_loop():
        while True:
            await generate_signal()
            await asyncio.sleep(60)  # check every minute for signals

    await asyncio.gather(
        signal_loop(),
        check_for_commands()
    )

if __name__ == "__main__":
    print("📡 XAUUSD Smart Risk Signal Bot Running...")
    asyncio.run(main())
