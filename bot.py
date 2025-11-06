import os
import requests
import time
from datetime import datetime
import pytz
import telebot

# 🔧 Настройки и переменные окружения
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL = 60  # проверка каждую минуту
THRESHOLD = 10
PRAGUE_TZ = pytz.timezone("Europe/Prague")
LOG_FILE = "signals_log.txt"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 🧾 Логирование
def log_message(message: str):
    timestamp = datetime.now(PRAGUE_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


# 📊 Получение данных волатильности
def get_volatility():
    url = "https://open-api.coinglass.com/api/pro/v1/indicator/volatility"
    headers = {"coinglassSecret": COINGLASS_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        log_message(f"Ошибка API: {e}")
        return []


# 📢 Отправка сигналов в Telegram
def send_signal(symbol, vol):
    message = f"⚡ {symbol}: волатильность {vol:.2f}%"
    bot.send_message(chat_id=CHAT_ID, text=message)
    log_message(message)


# 🔁 Сброс сигналов
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
        msg = f"♻️ Сброс дневных сигналов — {now.strftime('%d.%m.%Y')}"
        bot.send_message(chat_id=CHAT_ID, text=msg)
        log_message(msg)


# 🔄 Основной цикл
sent_alerts = set()
last_reset_date = datetime.now(PRAGUE_TZ).date()

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
            log_message(f"Ошибка main_loop: {e}")
            time.sleep(30)


# 🧠 Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Привет 👋! Бот запущен и работает ✅")


import telebot

def run_polling():
    # Попробуем удалить webhook на всякий случай
    try:
        bot.remove_webhook()
        log_message("Удалил webhook (если был).")
    except Exception as e:
        log_message(f"Не удалось удалить webhook: {e}")

    print("✅ Bot started and polling...")
    try:
        bot.send_message(chat_id=CHAT_ID, text="🚀 Бот запущен на Render и слушает команды!")
    except Exception as e:
        log_message(f"Не получилось послать стартовое сообщение: {e}")

    while True:
        try:
            bot.polling(non_stop=True)
        except telebot.apihelper.ApiTelegramException as e:
            # Специально ловим 409 — конфликты вебхука/другого polling
            if "409" in str(e) or "Conflict" in str(e):
                log_message(f"ApiTelegramException 409 — conflict: {e}. Попытка удалить webhook и перезапустить.")
                try:
                    bot.remove_webhook()
                    log_message("Удалил webhook после 409.")
                except Exception as ex:
                    log_message(f"Ошибка при удалении webhook после 409: {ex}")
                time.sleep(10)
                continue
            else:
                log_message(f"ApiTelegramException polling: {e}")
                time.sleep(15)
        except Exception as e:
            log_message(f"Ошибка polling (общее): {e}")
            time.sleep(15)
