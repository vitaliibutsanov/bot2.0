import os
import time
import threading

# Путь к файлу истории сигналов
LOG_PATH = os.path.join("logs", "signals_history.log")
LOCK = threading.Lock()


def log_signal(symbol: str, signal: str, price: float, rsi: float, ema: float, atr: float, strength: int):
    """
    Записывает торговый сигнал в файл signals_history.log.
    Формат:
    timestamp | symbol | signal | Price=... | RSI=... | EMA=... | ATR=... | Strength=...
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = (
        f"{timestamp} | {symbol} | {signal} | "
        f"Price={price:.2f} | RSI={rsi:.2f} | EMA={ema:.2f} | ATR={atr:.2f} | Strength={strength}/100\n"
    )
    with LOCK:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
