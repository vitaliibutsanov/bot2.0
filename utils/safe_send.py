import logging
import asyncio
from telegram.error import TelegramError, NetworkError

async def safe_send_message(bot, chat_id, text, **kwargs):
    """
    Безопасная отправка сообщений в Telegram.
    Делает 3 попытки с задержкой, чтобы избежать падения при временных сбоях.
    """
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            # Ограничение длины сообщения
            if len(text) > 4000:
                logging.warning(f"SAFE_SEND: Сообщение слишком длинное ({len(text)} символов), урезаем.")
                text = text[:4000] + "..."

            await bot.send_message(chat_id=chat_id, text=text, **kwargs)
            logging.info(f"SAFE_SEND: Успешно отправлено [{len(text)} символов].")
            break
        except (NetworkError, TelegramError) as e:
            logging.warning(f"SAFE_SEND_FAIL: Попытка {attempt}/{max_attempts}, ошибка: {e}")
            if attempt < max_attempts:
                await asyncio.sleep(2)  # задержка между попытками
            else:
                logging.error(f"SAFE_SEND_ERROR: Не удалось отправить сообщение: {e}")
