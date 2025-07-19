import os
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

def send_message(text: str):
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    return "Message sent successfully"
