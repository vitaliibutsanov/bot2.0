import logging
import os

# Создаем папку logs, если ее нет
if not os.path.exists("logs"):
    os.makedirs("logs")

# ===== Основной лог (bot.log) =====
# Отдельный обработчик для файла
file_handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

# Отдельный обработчик для терминала
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # в терминале показывать только WARNING и ERROR
console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

# Привязываем оба обработчика
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

# ===== Лог для сделок (trades.log) =====
trades_logger = logging.getLogger("trades")
trades_handler = logging.FileHandler("logs/trades.log", encoding="utf-8")
trades_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
trades_logger.addHandler(trades_handler)
trades_logger.setLevel(logging.INFO)

# ===== Лог для сигналов (signals.log) =====
signals_logger = logging.getLogger("signals")
signals_handler = logging.FileHandler("logs/signals.log", encoding="utf-8")
signals_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
signals_logger.addHandler(signals_handler)
signals_logger.setLevel(logging.INFO)
