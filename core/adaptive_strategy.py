import time
import logging
from core.strategy import analyze_market_smart, get_technical_indicators
from config import binance
import pandas as pd
from ta.trend import EMAIndicator

# Время последней сделки
last_trade_time = 0
NO_TRADE_LIMIT_1 = 3 * 3600  # 3 часа
NO_TRADE_LIMIT_2 = 6 * 3600  # 6 часов

def register_trade():
    global last_trade_time
    last_trade_time = time.time()
    logging.info("ADAPTIVE_STRATEGY | Зарегистрирована новая сделка.")

def get_adaptive_signal(symbol="BTC/USDT"):
    """
    Возвращает сигнал с учетом адаптивной стратегии:
    - Сначала обычный анализ.
    - Если сигналов нет долго — ослабляем фильтры.
    - Если долго нет сделок — fallback EMA стратегия.
    """

    global last_trade_time
    time_since_trade = time.time() - last_trade_time if last_trade_time > 0 else 999999

    # 1. Обычный анализ
    result = analyze_market_smart(symbol)
    if "СИГНАЛ" in result:
        return result

    # 2. Если сделок нет > 3 часов — ослабляем критерии RSI
    if time_since_trade > NO_TRADE_LIMIT_1:
        try:
            price, rsi, bb_upper, bb_lower, volume = get_technical_indicators(symbol)
            if price and (rsi < 45 or rsi > 55):  # более мягкие уровни
                logging.info(f"ADAPTIVE_STRATEGY | Мягкий сигнал по RSI={rsi:.2f}")
                return f"⚠ МЯГКИЙ СИГНАЛ (RSI={rsi:.2f})\nЦена: {price}"
        except Exception as e:
            logging.error(f"ADAPTIVE_STRATEGY_ERROR (RSI): {e}")

    # 3. Если сделок нет > 6 часов — EMA fallback
    if time_since_trade > NO_TRADE_LIMIT_2:
        try:
            closes = [c[4] for c in binance.fetch_ohlcv(symbol, timeframe="15m", limit=50)]
            ema_fast = EMAIndicator(pd.Series(closes), window=10).ema_indicator().iloc[-1]
            ema_slow = EMAIndicator(pd.Series(closes), window=30).ema_indicator().iloc[-1]
            price = closes[-1]

            if ema_fast > ema_slow:
                logging.info(f"ADAPTIVE_STRATEGY | EMA BUY (fast={ema_fast}, slow={ema_slow})")
                return f"📈 EMA-СИГНАЛ: ПОКУПАТЬ (fast={ema_fast:.2f}, slow={ema_slow:.2f})"
            elif ema_fast < ema_slow:
                logging.info(f"ADAPTIVE_STRATEGY | EMA SELL (fast={ema_fast}, slow={ema_slow})")
                return f"📉 EMA-СИГНАЛ: ПРОДАВАТЬ (fast={ema_fast:.2f}, slow={ema_slow:.2f})"
        except Exception as e:
            logging.error(f"ADAPTIVE_STRATEGY_ERROR (EMA): {e}")

    return "❕ Нет условий для входа (адаптивная стратегия)"
