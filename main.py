import logging
import asyncio
from telegram.ext import Application, JobQueue
from telegram_bot.handlers import setup_telegram_bot
from core.auto_trader import auto_trade_cycle, sync_open_positions
from config import TELEGRAM_TOKEN, CHAT_ID
from core.logger import setup_logging
from utils.safe_send import safe_send_message
from core.order_manager import futures_manager  # Для подсчёта позиций

# Настройка логирования
trades_logger, signals_logger = setup_logging(hours=48)


async def startup_tasks(app):
    """
    Задачи, выполняемые при старте:
    - Синхронизация открытых позиций
    - Уведомление в Telegram
    """
    try:
        await sync_open_positions()  # Проверяем открытые позиции
        open_count = len(futures_manager.active_positions)
        await safe_send_message(
            app.bot,
            CHAT_ID,
            f"♻ Бот запущен и проверка позиций завершена.\n"
            f"Текущие активные позиции: {open_count}"
        )
    except Exception as e:
        logging.error(f"Ошибка при старте: {e}")
        await safe_send_message(app.bot, CHAT_ID, f"⚠ Ошибка при старте: {e}")


def main():
    try:
        logging.warning("Запуск Telegram бота...")

        # Создаём приложение Telegram
        app = setup_telegram_bot()

        # Инициализация JobQueue
        if not app.job_queue:
            app.job_queue = JobQueue()
            app.job_queue.set_application(app)

        # Запускаем автоцикл трейдинга
        app.job_queue.run_repeating(auto_trade_cycle, interval=60, first=5)

        # Выполняем стартовые задачи с контекстом
        asyncio.get_event_loop().create_task(startup_tasks(app))

        logging.warning("Бот запущен.")
        app.run_polling()

    except Exception as e:
        logging.error(f"Ошибка запуска: {e}")


if __name__ == "__main__":
    main()
