import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

async def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Ошибка: TELEGRAM_TOKEN или TELEGRAM_CHAT_ID не найдены в .env")
        return

    try:
        bot = Bot(token=token)
        me = await bot.get_me()
        print(f"Бот найден: @{me.username} (ID: {me.id})")

        await bot.send_message(chat_id=chat_id, text="✅ Bot 2.0 успешно подключен к Telegram!")
        print("Сообщение успешно отправлено!")

    except Exception as e:
        print(f"Ошибка при подключении к Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(main())
