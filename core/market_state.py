import logging
from config import binance
from log_config import signals_logger

# --- Параметры ---
ADX_PERIOD = 14
EMA_PERIOD = 50
ATR_PERIOD = 14
ATR_VOL_THRESHOLD = 0.015  # 1.5% от цены — порог волатильности
STRONG_TREND_ADX = 25      # Порог для сильного тренда


def get_ohlcv(symbol: str, timeframe="1m", limit=100):
    """Загрузка OHLCV данных с биржи."""
    try:
        return binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        logging.error(f"OHLCV_ERROR | {e}")
        return []


def calculate_atr(symbol: str, period=ATR_PERIOD):
    """Вычисление ATR (средний диапазон движения)."""
    ohlcv = get_ohlcv(symbol, limit=period + 1)
    if not ohlcv or len(ohlcv) < period:
        return None

    trs = []
    for i in range(1, len(ohlcv)):
        high = ohlcv[i][2]
        low = ohlcv[i][3]
        prev_close = ohlcv[i - 1][4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs) / len(trs)


def calculate_ema_slope(symbol: str, period=EMA_PERIOD):
    """Оценка направления тренда по наклону EMA."""
    ohlcv = get_ohlcv(symbol, limit=period + 5)
    if not ohlcv or len(ohlcv) < period:
        return 0

    closes = [c[4] for c in ohlcv]
    k = 2 / (period + 1)

    ema = closes[0]
    ema_values = []
    for price in closes:
        ema = price * k + ema * (1 - k)
        ema_values.append(ema)

    slope = ema_values[-1] - ema_values[-5]
    return slope


def calculate_adx(symbol: str, period=ADX_PERIOD):
    """Простейшая реализация ADX для оценки силы тренда."""
    ohlcv = get_ohlcv(symbol, limit=period + 1)
    if not ohlcv or len(ohlcv) < period + 1:
        return 0

    plus_dm = []
    minus_dm = []
    tr_list = []

    for i in range(1, len(ohlcv)):
        high_diff = ohlcv[i][2] - ohlcv[i - 1][2]
        low_diff = ohlcv[i - 1][3] - ohlcv[i][3]
        plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
        minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)

        tr = max(
            ohlcv[i][2] - ohlcv[i][3],
            abs(ohlcv[i][2] - ohlcv[i - 1][4]),
            abs(ohlcv[i][3] - ohlcv[i - 1][4])
        )
        tr_list.append(tr)

    tr_sum = sum(tr_list[-period:])
    plus_di = (sum(plus_dm[-period:]) / tr_sum) * 100 if tr_sum != 0 else 0
    minus_di = (sum(minus_dm[-period:]) / tr_sum) * 100 if tr_sum != 0 else 0
    dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100

    return dx


def get_market_state(symbol="BTC/USDT"):
    """
    Определяет текущее состояние рынка:
    TREND_UP | TREND_DOWN | RANGE | VOLATILE
    Возвращает (state, метрики).
    """
    atr = calculate_atr(symbol)
    slope = calculate_ema_slope(symbol)
    adx = calculate_adx(symbol)

    if atr is None:
        signals_logger.warning(f"[MARKET_STATE] {symbol} | Недостаточно данных для анализа")
        return "UNKNOWN", {"atr": 0, "adx": 0, "slope": 0}

    # Получаем текущую цену для нормализации ATR
    try:
        ticker = binance.fetch_ticker(symbol)
        current_price = ticker.get('last', 0)
    except Exception:
        current_price = 0

    atr_percent = (atr / current_price * 100) if current_price else 0

    # --- Логика определения состояния ---
    state = "RANGE"
    if adx >= STRONG_TREND_ADX:
        if slope > 0:
            state = "TREND_UP"
        else:
            state = "TREND_DOWN"

    # Проверка волатильности
    if atr_percent > ATR_VOL_THRESHOLD * 100:
        state = "VOLATILE"

    signals_logger.info(
        f"[MARKET_STATE] {symbol} | State={state} | ATR={atr:.4f} ({atr_percent:.3f}%) "
        f"| ADX={adx:.2f} | Slope={slope:.4f}"
    )

    return state, {
        "atr": atr,
        "adx": adx,
        "slope": slope,
        "atr_percent": atr_percent,
        "price": current_price
    }
