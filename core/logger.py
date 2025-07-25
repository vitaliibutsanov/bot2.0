import logging
import os
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
import json

LOG_DIR = "logs"
MAX_LOG_SIZE_MB = 4  # Максимальный размер одного файла лога
BACKUP_COUNT = 5     # Количество архивных копий
PROTECTED_FILES = {"open_positions.log", "portfolio.json"}  # Файлы, которые нельзя удалять


def ensure_base_files():
    """Создаёт необходимые файлы open_positions.log и portfolio.json, если их нет."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)

        open_positions_file = os.path.join(LOG_DIR, "open_positions.log")
        if not os.path.exists(open_positions_file):
            with open(open_positions_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            print("[INIT] Создан open_positions.log")

        portfolio_file = os.path.join(LOG_DIR, "portfolio.json")
        if not os.path.exists(portfolio_file):
            with open(portfolio_file, "w", encoding="utf-8") as f:
                json.dump({"balance": 1000, "trades": []}, f, ensure_ascii=False, indent=2)
            print("[INIT] Создан portfolio.json")
    except Exception as e:
        print(f"[INIT_ERROR] {e}")


def get_folder_size(directory):
    """Возвращает размер папки в байтах."""
    total_size = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total_size += os.path.getsize(fp)
    return total_size


def cleanup_old_logs(directory=LOG_DIR, hours=48):
    """
    Удаляет файлы логов старше N часов или при превышении размера папки > MAX_LOG_SIZE_MB.
    """
    if not os.path.exists(directory):
        return

    cutoff_time = datetime.now() - timedelta(hours=hours)

    # Удаляем старые логи по времени, кроме защищённых файлов
    for filename in os.listdir(directory):
        if filename in PROTECTED_FILES:
            continue
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                if mtime < cutoff_time:
                    os.remove(filepath)
                    print(f"[LOG_CLEANUP] Удален старый лог: {filename}")
            except PermissionError:
                print(f"[LOG_CLEANUP_WARN] Файл занят: {filename}")
            except Exception as e:
                print(f"[LOG_CLEANUP_ERROR] {filename}: {e}")

    # Контроль общего размера папки
    safety_counter = 20  # чтобы не зациклиться
    while get_folder_size(directory) > MAX_LOG_SIZE_MB * 1024 * 1024 and safety_counter > 0:
        safety_counter -= 1
        try:
            log_files = sorted(
                [os.path.join(directory, f) for f in os.listdir(directory) if f not in PROTECTED_FILES],
                key=lambda x: os.path.getmtime(x)
            )
            if log_files:
                try:
                    os.remove(log_files[0])
                    print(f"[LOG_CLEANUP] Удален лог по размеру: {os.path.basename(log_files[0])}")
                except PermissionError:
                    print(f"[LOG_CLEANUP_WARN] Файл занят: {os.path.basename(log_files[0])}")
                    break
            else:
                break
        except Exception as e:
            print(f"[LOG_CLEANUP_ERROR] {e}")
            break


def setup_logging(hours=48):
    """Настраивает логирование с автоочисткой и ротацией логов."""
    ensure_base_files()
    cleanup_old_logs(hours=hours)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []

    # Консоль — только WARNING и ERROR
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
    root_logger.addHandler(console_handler)

    # Основной лог (bot.log) с ротацией
    bot_log_file = os.path.join(LOG_DIR, "bot.log")
    file_handler = RotatingFileHandler(
        bot_log_file,
        maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
        errors="ignore"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root_logger.addHandler(file_handler)

    # Лог сделок (trades.log) с ротацией
    trades_logger = logging.getLogger("trades")
    trades_logger.setLevel(logging.INFO)
    trades_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "trades.log"),
        maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
        errors="ignore"
    )
    trades_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    trades_logger.addHandler(trades_handler)

    # Лог сигналов (signals.log) с ротацией
    signals_logger = logging.getLogger("signals")
    signals_logger.setLevel(logging.INFO)
    signals_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "signals.log"),
        maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
        errors="ignore"
    )
    signals_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    signals_logger.addHandler(signals_handler)

    return trades_logger, signals_logger
