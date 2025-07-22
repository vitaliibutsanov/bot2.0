import pandas as pd
import ta
from ta.volatility import BollingerBands
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
from config import binance
import logging
from log_config import signals_logger  # новый логгер

def get_technical_indicators(symbol: str, timeframe='1m', limit=50):
    """Возвращает базовые технические индикаторы: цена, RSI, Bollinger Bands, объем."""
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        if len(closes) < 20:
            raise ValueError("Недостаточно данных для индикаторов.")

        rsi = ta.momentum.rsi(pd.Series(closes), window=14).iloc[-1]
        bb = BollingerBands(pd.Series(closes), window=20, window_dev=2)
        bb_high, bb_low = bb.bollinger_hband().iloc[-1], bb.bollinger_lband().iloc[-1]

        return closes[-1], round(rsi, 2), round(bb_high, 2), round(bb_low, 2), round(volumes[-1], 3)
    except Exception as e:
        logging.error(f"TECHNICAL_INDICATORS_ERROR: {e}")
        return None, None, None, None, None

def analyze_market_smart(symbol='BTC/USDT', timeframe='1h', limit=50):
    """
    Расширенный анализ рынка:
    RSI + Bollinger Bands + EMA + ATR + перекос в стакане.
    Возвращает текстовый сигнал с уровнем доверия.
    """
    try:
        price, rsi, bb_upper, bb_lower, volume = get_technical_indicators(symbol)
        if price is None:
            return "❌ Не удалось получить индикаторы."

        # EMA
        closes = [c[4] for c in binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)]
        ema = EMAIndicator(pd.Series(closes), window=20).ema_indicator().iloc[-1]

        # ATR
        df = pd.DataFrame(binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=20),
                          columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range().iloc[-1]

        # ===== Позиция цены относительно BB =====
        price_position = "🔹 Цена между уровнями"
        if price <= bb_lower:
            price_position = "🟢 Цена у нижней границы BB"
        elif price >= bb_upper:
            price_position = "🔴 Цена у верхней границы BB"

        # ===== Анализ стакана =====
        orderbook = binance.fetch_order_book(symbol, limit=10)
        bid_volume = sum([b[1] for b in orderbook.get('bids', [])[:3]])
        ask_volume = sum([a[1] for a in orderbook.get('asks', [])[:3]])
        imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1)

        # ===== Расчет доверия =====
        confidence = 0
        rsi_buy_level = 40
        rsi_sell_level = 60

        if rsi < rsi_buy_level: confidence += 1
        if price <= bb_lower: confidence += 1
        if imbalance > 0.15: confidence += 1
        if price > ema: confidence += 1
        if atr > 0: confidence += 1

        # ===== Генерация сигнала =====
        signal = "❕ Нет условий для входа"
        if confidence >= 3 and rsi < rsi_buy_level:
            signal = "📈 СИГНАЛ: ПОКУПАТЬ"
        elif confidence >= 3 and rsi > rsi_sell_level:
            signal = "📉 СИГНАЛ: ПРОДАВАТЬ"
        else:
            # fallback стратегия EMA
            if rsi > 50 and price > ema:
                signal = "📈 СЛАБЫЙ СИГНАЛ: тренд вверх (EMA)"
            elif rsi < 50 and price < ema:
                signal = "📉 СЛАБЫЙ СИГНАЛ: тренд вниз (EMA)"

        # ===== Логируем =====
        logging.info(
            f"ANALYZE_SMART | {symbol} | Price={price:.2f} | RSI={rsi:.2f} | "
            f"BB=({bb_lower:.2f}/{bb_upper:.2f}) | EMA={ema:.2f} | ATR={atr:.2f} | "
            f"Bid={bid_volume:.2f} Ask={ask_volume:.2f} | Conf={confidence} | {signal}"
        )

        # Запись сигнала в отдельный лог
        signals_logger.info(
            f"{symbol} | Price={price:.2f} | RSI={rsi:.2f} | EMA={ema:.2f} | "
            f"ATR={atr:.2f} | Bid={bid_volume:.2f} Ask={ask_volume:.2f} | "
            f"Conf={confidence} | Signal={signal}"
        )

        # ===== Возвращаем отчет =====
        return (
            f"{signal}\n{price_position}\n"
            f"📉 RSI: {rsi:.2f}\n"
            f"📏 EMA: {ema:.2f}\n"
            f"⚡ ATR: {atr:.2f}\n"
            f"📊 Объём: {volume:.2f}\n"
            f"🌟 Доверие: {confidence}/5"
        )
    except Exception as e:
        logging.error(f"ANALYZE_SMART_ERROR: {e}")
        return f"❌ Ошибка анализа: {e}"
