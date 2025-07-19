import telegram
from core.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def send_notification(message: str):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
