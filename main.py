import logging
from telegram.ext import Application, JobQueue
from telegram_bot.handlers import setup_telegram_bot
from core.auto_trader import auto_trade_cycle
from config import TELEGRAM_TOKEN, CHAT_ID, binance

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.WARNING  # Показывать только предупреждения и ошибки
)

# Отключаем спам от сторонних библиотек
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main():
    try:
        logger.warning("Запуск Telegram бота...")

        # Создаём приложение Telegram
        app = setup_telegram_bot()

        # Инициализация JobQueue
        if not app.job_queue:
            app.job_queue = JobQueue()
            app.job_queue.set_application(app)

        app.job_queue.run_repeating(auto_trade_cycle, interval=60, first=5)

        logger.warning("Бот запущен.")
        app.run_polling()
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")


if __name__ == "__main__":
    main()
