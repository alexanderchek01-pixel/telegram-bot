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


# ------------- Обработчики команд (должны быть определены до polling) -------------
@bot.message_handler(commands=['start'])
def start(message):
    try:
        bot.reply_to(message, "Привет 👋! Бот запущен и работает ✅")
        log_message(f"/start от {message.from_user.id}")
    except Exception as e:
        log_message(f"Ошибка в handler /start: {e}")

# ------------- Функция запуска polling с защитой от webhook-conflict -------------
def run_polling():
    # попробуем удалить webhook на всякий случай
    try:
        bot.remove_webhook()
        log_message("Удалил webhook (если был).")
    except Exception as e:
        log_message(f"Не удалось удалить webhook (может быть уже удален): {e}")
    # 🧩 ТЕСТОВЫЙ СИГНАЛ: проверяем, что бот умеет отправлять сообщения
    import threading
    import time

    def send_test_signal():
        time.sleep(30)  # подождать 30 секунд после запуска
        try:
            bot.send_message(CHAT_ID, "🚨 Тестовый сигнал! Бот успешно реагирует на события.")
            log_message("✅ Тестовый сигнал отправлен успешно.")
        except Exception as e:
            log_message(f"Ошибка при отправке тестового сигнала: {e}")

    threading.Thread(target=send_test_signal).start()
    # запускаем polling в цикле — ловим ApiTelegramException (409 Conflict)
    while True:
        try:
            print("⚙️ Polling started successfully!")   # <-- метка для логов
            log_message("Запускаю polling...")
            bot.polling(non_stop=True)
        except Exception as e:
            try:
                err = str(e)
                if "409" in err or "Conflict" in err:
                    log_message(f"ApiTelegramException 409 - conflict: {err}. Удаляю webhook и перезапускаю.")
                    try:
                        bot.remove_webhook()
                        log_message("Удалил webhook после 409.")
                    except Exception as ex:
                        log_message(f"Ошибка при удалении webhook после 409: {ex}")
                    time.sleep(5)
                    continue
                else:
                    log_message(f"Ошибка polling: {e}")
            except Exception as ex:
                log_message(f"Ошибка обработки exception polling: {ex}")
            time.sleep(5)  # пауза перед новой попыткой

# ------------- Запускаем background-потоки: polling и основной цикл -------------
import threading

# поток для polling (слушает команды /start)
threading.Thread(target=run_polling, daemon=True).start()

# поток для основной логики (main_loop)
threading.Thread(target=main_loop, daemon=True).start()

# ------------- Сообщение о старте и "держим процесс живым" -------------
if __name__ == "__main__":
    try:
        bot.send_message(chat_id=CHAT_ID, text="✅ Бот запущен (Render запустил main_loop и polling)")
    except Exception as e:
        log_message(f"Не удалось отправить стартовое сообщение: {e}")

    log_message("Бот стартовал: polling и main_loop запущены в фоновых потоках.")
    while True:
        time.sleep(3600)
