import logging
from core.market_state import get_market_state
from core.strategy import analyze_market_smart
from log_config import signals_logger

# --- Пороговые значения ---
MIN_TREND_ADX = 20       # Минимальный ADX для трендовой стратегии
MIN_SLOPE = 0.5          # Минимальный наклон EMA для тренда
MAX_RANGE_ATR = 1.0      # ATR% для определения боковика

def trend_follow_strategy(symbol='BTC/USDT'):
    """
    Стратегия для трендового рынка:
    Использует EMA + RSI для поиска входа по направлению тренда.
    """
    try:
        signal = analyze_market_smart(symbol)
        signals_logger.info(f"[TREND_STRATEGY] {symbol} | {signal}")
        return signal
    except Exception as e:
        logging.error(f"[TREND_STRATEGY_ERROR] {e}")
        return f"❌ Ошибка трендовой стратегии: {e}"


def mean_reversion_strategy(symbol='BTC/USDT'):
    """
    Стратегия возврата к среднему:
    Использует Bollinger Bands + RSI для торговли от границ канала.
    """
    try:
        signal = analyze_market_smart(symbol)
        signals_logger.info(f"[MEAN_REVERSION] {symbol} | {signal}")
        return signal
    except Exception as e:
        logging.error(f"[MEAN_REVERSION_ERROR] {e}")
        return f"❌ Ошибка стратегии возврата к среднему: {e}"


def safe_mode_strategy(symbol='BTC/USDT'):
    """
    Защитная стратегия при высокой волатильности:
    Бот старается не открывать новые позиции или минимизировать риск.
    """
    signals_logger.warning(f"[SAFE_MODE] {symbol} | Рынок слишком волатилен, сделки ограничены.")
    return "⚠ SAFE MODE: Рынок нестабилен — сделки ограничены."


def select_strategy(symbol='BTC/USDT'):
    """
    Определяет текущую стратегию на основе состояния рынка и метрик.
    """
    try:
        state, metrics = get_market_state(symbol)

        atr_percent = metrics.get('atr_percent', 0)
        adx = metrics.get('adx', 0)
        slope = metrics.get('slope', 0)

        # Логируем метрики состояния
        signals_logger.info(
            f"[STRATEGY_MANAGER] {symbol} | State={state} | "
            f"ATR={metrics.get('atr', 0):.4f} ({atr_percent:.3f}%) | "
            f"ADX={adx:.2f} | Slope={slope:.4f}"
        )

        # Логика выбора стратегии
        if state in ("TREND_UP", "TREND_DOWN") and adx >= MIN_TREND_ADX and abs(slope) > MIN_SLOPE:
            return trend_follow_strategy(symbol)

        elif state == "RANGE" and atr_percent <= MAX_RANGE_ATR:
            return mean_reversion_strategy(symbol)

        elif state == "VOLATILE" or atr_percent > MAX_RANGE_ATR:
            return safe_mode_strategy(symbol)

        else:
            logging.info(f"[STRATEGY_MANAGER] Неопознанное или слабое состояние рынка: {state}")
            return "❕ Нет чёткой стратегии (рынок слабый или неустойчив)."

    except Exception as e:
        logging.error(f"[STRATEGY_MANAGER_ERROR] {e}")
        return f"❌ Ошибка выбора стратегии: {e}"
