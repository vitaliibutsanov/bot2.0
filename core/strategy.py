import time
import pandas as pd
import ta
from ta.volatility import BollingerBands, AverageTrueRange
from ta.trend import EMAIndicator
from config import binance, ATR_THRESHOLD
from log_config import signals_logger
from core.market_state import get_market_state
from core.signals_logger import log_signal  # Новый импорт

_last_signal = None
_last_signal_time = 0
SIGNAL_CACHE_TIME = 60
ATR_DYNAMIC_MULT = 2.5


def get_technical_indicators(symbol: str, timeframe='1m', limit=50):
    """Возвращает технические индикаторы: цена, RSI, Bollinger Bands, объём."""
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        if len(closes) < 20:
            return None, None, None, None, None

        rsi = ta.momentum.rsi(pd.Series(closes), window=14).iloc[-1]
        bb = BollingerBands(pd.Series(closes), window=20, window_dev=2)
        return closes[-1], round(rsi, 2), round(bb.bollinger_hband().iloc[-1], 2), round(bb.bollinger_lband().iloc[-1], 2), round(volumes[-1], 3)
    except Exception as e:
        signals_logger.error(f"TECHNICAL_INDICATORS_ERROR | {e}")
        return None, None, None, None, None


def get_signal_strength(confidence: int, adx: float, atr_percent: float) -> int:
    """Возвращает силу сигнала (0-100)."""
    strength = confidence * 10
    if adx > 25:
        strength += 20
    elif adx > 15:
        strength += 10

    if atr_percent < 1:
        strength += 10
    elif atr_percent > 3:
        strength -= 10

    return max(0, min(100, strength))


def analyze_market_smart(symbol='BTC/USDT', timeframe='1h', limit=50):
    global _last_signal, _last_signal_time
    try:
        price, rsi, bb_upper, bb_lower, volume = get_technical_indicators(symbol)
        if price is None:
            return "❌ Не удалось получить индикаторы."

        closes = [c[4] for c in binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)]
        ema = EMAIndicator(pd.Series(closes), window=20).ema_indicator().iloc[-1]

        df = pd.DataFrame(binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=20),
                          columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        atr_series = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14)
        atr = atr_series.average_true_range().iloc[-1]
        last_high, last_low = df['high'].iloc[-1], df['low'].iloc[-1]
        current_range = last_high - last_low

        signals_logger.info(f"ATR_CHECK | ATR={atr:.2f} | Range={current_range:.2f} | TH={ATR_THRESHOLD}")
        if current_range > atr * ATR_DYNAMIC_MULT:
            warning_msg = f"⚠ Рынок слишком волатильный (ATR={atr:.2f}, Range={current_range:.2f}) — осторожно."
            signals_logger.warning(f"TRADE_CAUTION | {warning_msg}")
            return warning_msg

        price_position = "🔹 Цена между уровнями BB"
        if price <= bb_lower:
            price_position = "🟢 Цена у нижней границы BB"
        elif price >= bb_upper:
            price_position = "🔴 Цена у верхней границы BB"

        try:
            orderbook = binance.fetch_order_book(symbol, limit=10)
            bid_volume = sum([b[1] for b in orderbook.get('bids', [])[:3]])
            ask_volume = sum([a[1] for a in orderbook.get('asks', [])[:3]])
            imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1)
        except Exception:
            bid_volume, ask_volume, imbalance = 0, 0, 0

        market_state, metrics = get_market_state(symbol)
        adx = metrics.get("adx", 0)
        slope = metrics.get("slope", 0)
        atr_percent = metrics.get("atr_percent", 0)

        confidence = 0
        rsi_buy_level, rsi_sell_level = 40, 60
        if rsi < rsi_buy_level: confidence += 1
        if price <= bb_lower: confidence += 1
        if imbalance > 0.15: confidence += 1
        if price > ema: confidence += 1
        if adx >= 20: confidence += 1

        confidence_note = ""
        if market_state in ("TREND_UP", "TREND_DOWN"):
            confidence += 1
            confidence_note = "Усилено из-за тренда."
        elif market_state == "RANGE":
            confidence += 1
            confidence_note = "Усилено для диапазона."
        elif market_state == "VOLATILE":
            confidence = max(confidence - 1, 0)
            confidence_note = "Снижено из-за волатильности."

        signal = "❕ Нет условий для входа"
        if confidence >= 3 and rsi < rsi_buy_level:
            signal = "📈 СИГНАЛ: ПОКУПАТЬ"
        elif confidence >= 3 and rsi > rsi_sell_level:
            signal = "📉 СИГНАЛ: ПРОДАВАТЬ"
        else:
            if rsi > 50 and price > ema:
                signal = "📈 СЛАБЫЙ СИГНАЛ: тренд вверх (EMA)"
            elif rsi < 50 and price < ema:
                signal = "📉 СЛАБЫЙ СИГНАЛ: тренд вниз (EMA)"

        signal += f" | Рынок: {market_state}"
        strength = get_signal_strength(confidence, adx, atr_percent)

        now = time.time()
        if signal == _last_signal and (now - _last_signal_time < SIGNAL_CACHE_TIME):
            return signal
        _last_signal = signal
        _last_signal_time = now

        # Логируем сигнал в историю
        log_signal(symbol, signal, price, rsi, ema, atr, strength)

        signals_logger.info(
            f"ANALYZE_SMART | {symbol} | Price={price:.2f} | RSI={rsi:.2f} | BB=({bb_lower:.2f}/{bb_upper:.2f}) | "
            f"EMA={ema:.2f} | ATR={atr:.2f} ({atr_percent:.3f}%) | ADX={adx:.2f} | Slope={slope:.4f} | "
            f"Conf={confidence} | Strength={strength}/100 | {signal}"
        )

        return (
            f"{signal}\n{price_position}\n"
            f"📉 RSI: {rsi:.2f}\n"
            f"📏 EMA: {ema:.2f}\n"
            f"⚡ ATR: {atr:.2f} ({atr_percent:.3f}%) (Range={current_range:.2f})\n"
            f"📊 Объём: {volume:.2f} | Дисбаланс: {imbalance:.3f}\n"
            f"🌟 Доверие: {confidence}/6\n"
            f"🔥 Сила сигнала: {strength}/100\n"
            f"ADX: {adx:.2f} | EMA-слайп: {slope:.4f}\n"
            f"ℹ {confidence_note}"
        )

    except Exception as e:
        signals_logger.error(f"ANALYZE_SMART_ERROR | {e}")
        return f"❌ Ошибка анализа: {e}"
