import logging
import asyncio
from telegram.error import TelegramError, NetworkError

async def safe_send_message(bot, chat_id, text, max_attempts=3, delay=2, **kwargs):
    """
    Безопасная отправка сообщений в Telegram.
    Делает несколько попыток с задержкой, чтобы избежать ошибок при временных сбоях.
    """
    if not text:
        logging.warning("SAFE_SEND: Пустое сообщение — не отправляем.")
        return

    # Если текст слишком длинный — разбиваем на части
    chunks = []
    if len(text) > 4000:
        logging.warning(f"SAFE_SEND: Сообщение длинное ({len(text)} символов), разбиваем на части.")
        while text:
            chunks.append(text[:4000])
            text = text[4000:]
    else:
        chunks = [text]

    for chunk in chunks:
        sent = False
        for attempt in range(1, max_attempts + 1):
            try:
                await bot.send_message(chat_id=chat_id, text=chunk, **kwargs)
                logging.info(f"SAFE_SEND: Отправлено ({len(chunk)} символов). Попытка {attempt}/{max_attempts}")
                sent = True
                break
            except (NetworkError, TelegramError) as e:
                logging.warning(f"SAFE_SEND_FAIL: Попытка {attempt}/{max_attempts}, ошибка: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(delay)
                else:
                    logging.error(f"SAFE_SEND_ERROR: Не удалось отправить сообщение после {max_attempts} попыток.")
        if not sent:
            break
