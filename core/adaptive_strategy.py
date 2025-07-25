import time
import logging
import pandas as pd
from ta.trend import EMAIndicator
from core.strategy import analyze_market_smart, get_technical_indicators
from config import binance
from log_config import signals_logger

# Таймеры и кэш
last_trade_time = 0
last_adaptive_signal = None
last_signal_time = 0

# Настройки
SIGNAL_CACHE_TIME = 60  # кэш сигнала 1 минута
NO_TRADE_LIMIT_1 = 3 * 3600  # 3 часа
NO_TRADE_LIMIT_2 = 6 * 3600  # 6 часов
VERBOSE_ADAPTIVE = False  # включить подробный лог?


def register_trade():
    """Сбрасывает таймер последней сделки."""
    global last_trade_time
    last_trade_time = time.time()
    signals_logger.info("ADAPTIVE_STRATEGY | Зарегистрирована новая сделка.")


def get_adaptive_signal(symbol="BTC/USDT"):
    """
    Адаптивная стратегия:
    1. Использует analyze_market_smart().
    2. Если сделок нет > 3ч — ослабляет RSI-фильтры.
    3. Если сделок нет > 6ч — использует EMA fallback.
    """
    global last_trade_time, last_adaptive_signal, last_signal_time

    now = time.time()

    # Возврат кэша сигнала
    if last_adaptive_signal and (now - last_signal_time < SIGNAL_CACHE_TIME):
        return last_adaptive_signal

    time_since_trade = now - last_trade_time if last_trade_time > 0 else 999999

    # === 1. Smart-анализ
    try:
        result = analyze_market_smart(symbol)
        if "СИГНАЛ" in result:
            last_adaptive_signal = result
            last_signal_time = now
            return result
    except Exception as e:
        logging.error(f"ADAPTIVE_STRATEGY_ERROR (SMART): {e}")

    # === 2. Мягкий RSI (если давно не было сделок)
    if time_since_trade > NO_TRADE_LIMIT_1:
        try:
            price, rsi, bb_upper, bb_lower, volume = get_technical_indicators(symbol)
            if price and rsi is not None and (rsi < 45 or rsi > 55):
                msg = f"⚠ МЯГКИЙ СИГНАЛ (RSI={rsi:.2f})\nЦена: {price:.2f}"
                if VERBOSE_ADAPTIVE:
                    signals_logger.info(f"ADAPTIVE_STRATEGY | Мягкий сигнал (RSI={rsi:.2f})")
                last_adaptive_signal = msg
                last_signal_time = now
                return msg
        except Exception as e:
            logging.error(f"ADAPTIVE_STRATEGY_ERROR (RSI): {e}")

    # === 3. EMA fallback (если сделок нет > 6ч)
    if time_since_trade > NO_TRADE_LIMIT_2:
        try:
            ohlcv = binance.fetch_ohlcv(symbol, timeframe="15m", limit=50)
            closes = [c[4] for c in ohlcv if c and c[4] is not None]

            if len(closes) < 30:
                msg = "❕ Недостаточно данных для EMA fallback."
                signals_logger.warning("ADAPTIVE_STRATEGY | Недостаточно данных для EMA анализа.")
                last_adaptive_signal = msg
                last_signal_time = now
                return msg

            ema_fast = EMAIndicator(pd.Series(closes), window=10).ema_indicator().iloc[-1]
            ema_slow = EMAIndicator(pd.Series(closes), window=30).ema_indicator().iloc[-1]
            price = closes[-1]

            if ema_fast > ema_slow:
                msg = f"📈 EMA-СИГНАЛ: ПОКУПАТЬ (fast={ema_fast:.2f}, slow={ema_slow:.2f})"
            elif ema_fast < ema_slow:
                msg = f"📉 EMA-СИГНАЛ: ПРОДАВАТЬ (fast={ema_fast:.2f}, slow={ema_slow:.2f})"
            else:
                msg = "❕ EMA нейтрален."

            if VERBOSE_ADAPTIVE:
                signals_logger.info(f"ADAPTIVE_STRATEGY | {msg}")
            last_adaptive_signal = msg
            last_signal_time = now
            return msg
        except Exception as e:
            logging.error(f"ADAPTIVE_STRATEGY_ERROR (EMA): {e}")

    last_adaptive_signal = "❕ Нет условий для входа (адаптивная стратегия)"
    last_signal_time = now
    return last_adaptive_signal
