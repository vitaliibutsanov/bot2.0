import logging
import os

# Создаем папку logs, если ее нет
if not os.path.exists("logs"):
    os.makedirs("logs")

# ===== Основной лог (bot.log) =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
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
