import os
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

def notify(text: str):
    """
    Отправляет сообщение в Telegram чат.
    Использовать: notify("Тестовое сообщение")
    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        return True
    except Exception as e:
        print(f"[ERROR] Не удалось отправить сообщение в Telegram: {e}")
        return False
