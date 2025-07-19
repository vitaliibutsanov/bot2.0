from utils.notifier import send_notification
from utils.logger_plus import setup_logger
from auto_analyze import auto_analyze

if __name__ == "__main__":
    logger = setup_logger()
    logger.info("Тестируем функции...")
    send_notification("Тестовое сообщение от бота!")
    auto_analyze()
    logger.info("Все модули успешно протестированы.")
