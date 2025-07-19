import os
from telegram import Bot
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("Ошибка: TELEGRAM_TOKEN или TELEGRAM_CHAT_ID не найдены в .env")
    exit()

try:
    bot = Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="✅ Тестовое сообщение от Bot 2.0")
    print("Успех: сообщение отправлено в Telegram!")
except Exception as e:
    print(f"Ошибка: {e}")
