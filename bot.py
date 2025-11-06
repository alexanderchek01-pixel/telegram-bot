import os
import requests
import time
from datetime import datetime
import pytz
import telebot   # ✅ правильный импорт для pyTelegramBotAPI

COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL = 60
THRESHOLD = 10
PRAGUE_TZ = pytz.timezone("Europe/Prague")
LOG_FILE = "signals_log.txt"

bot = telebot.TeleBot(TELEGRAM_TOKEN)   # ✅ правильное создание бота

def log_message(message: str):
    timestamp = datetime.now(PRAGUE_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def get_volatility():
    url = "https://open-api.coinglass.com/api/pro/v1/indicator/volatility"
    headers = {"coinglassSecret": COINGLASS_API_KEY}
    response = requests.get(url, headers=headers, timeout=10)
    data = response.json()
    return data.get("data", [])

def send_signal(symbol, vol):
    message = f"⚡ {symbol}: волатильность {vol:.2f}%"
    bot.send_message(chat_id=CHAT_ID, text=message)
    log_message(message)

def reset_alerts_if_needed():
    global last_reset_date, sent_alerts
    now = datetime.now(PRAGUE_TZ)

    if now.date() != last_reset_date and now.hour == 0:
        try:
            with open(LOG_FILE, "rb") as f:
                bot.send_document(chat_id=CHAT_ID, document=f, filename=LOG_FILE)
        except FileNotFoundError:
            pass

        sent_alerts.clear()
        last_reset_date = now.date()
        msg = f"🔄 Сброс дневных сигналов — {now.strftime('%d.%m.%Y')}"
        bot.send_message(chat_id=CHAT_ID, text=msg)
        log_message(msg)

def main_loop():
    while True:
        try:
            reset_alerts_if_needed()
            data = get_volatility() or []

            for item in data:
                symbol = item.get("symbol")
                vol = item.get("volatility", 0)

                if vol >= THRESHOLD and symbol and symbol not in sent_alerts:
                    send_signal(symbol, vol)
                    sent_alerts.add(symbol)

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            log_message(f"Ошибка: {e}")
            time.sleep(30)

if __name__ == "__main__":
    bot.send_message(chat_id=CHAT_ID, text="✅ Бот запущен (bot.py стартовал)")
    log_message("Бот запущен")
    main_loop()
