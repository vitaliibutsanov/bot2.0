import logging 
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta

# === Папка для логов ===
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# === Автоочистка логов старше 30 дней ===
def cleanup_old_logs(days=30):
    cutoff = datetime.now() - timedelta(days=days)
    for file in os.listdir(LOG_DIR):
        path = os.path.join(LOG_DIR, file)
        if os.path.isfile(path):
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if mtime < cutoff:
                try:
                    os.remove(path)
                    logging.info(f"[LOG_CLEANUP] Удалён старый лог: {file}")
                except Exception as e:
                    logging.error(f"[LOG_CLEANUP_ERROR] {file} | {e}")

cleanup_old_logs(days=30)

# === Форматы ===
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
TRADE_FORMAT = "%(asctime)s | %(message)s"

# === Настройки ротации ===
MAX_LOG_SIZE = 4 * 1024 * 1024  # 4 MB
BACKUP_COUNT = 5

# === Основной лог (bot.log) ===
bot_log_file = os.path.join(LOG_DIR, "bot.log")
file_handler = RotatingFileHandler(bot_log_file, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # В терминал идут только WARNING+
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

# === Отключаем спам от сторонних библиотек (ccxt, urllib, asyncio) ===
for noisy_logger in ["ccxt", "urllib3", "asyncio"]:
    logging.getLogger(noisy_logger).setLevel(logging.ERROR)

# === Лог для сделок ===
trades_logger = logging.getLogger("trades")
trades_handler = RotatingFileHandler(os.path.join(LOG_DIR, "trades.log"),
                                     maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT, encoding="utf-8")
trades_handler.setFormatter(logging.Formatter(TRADE_FORMAT))
trades_logger.addHandler(trades_handler)
trades_logger.setLevel(logging.INFO)

# === Лог для сигналов ===
signals_logger = logging.getLogger("signals")
signals_handler = RotatingFileHandler(os.path.join(LOG_DIR, "signals.log"),
                                      maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT, encoding="utf-8")
signals_handler.setFormatter(logging.Formatter(TRADE_FORMAT))
signals_logger.addHandler(signals_handler)
signals_logger.setLevel(logging.INFO)

# === Лог для аналитики ===
analytics_logger = logging.getLogger("analytics")
analytics_handler = RotatingFileHandler(os.path.join(LOG_DIR, "analytics.log"),
                                        maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT, encoding="utf-8")
analytics_handler.setFormatter(logging.Formatter(TRADE_FORMAT))
analytics_logger.addHandler(analytics_handler)
analytics_logger.setLevel(logging.INFO)
