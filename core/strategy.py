import pandas as pd
import ta
from ta.volatility import BollingerBands
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
from config import binance
import logging

def get_technical_indicators(symbol: str, timeframe='1h', limit=100):
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe='1m', limit=50)
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

def analyze_market_smart(symbol='BTC/USDT', timeframe='1h', limit=100):
    try:
        price, rsi, bb_upper, bb_lower, volume = get_technical_indicators(symbol)
        if price is None:
            return "❌ Не удалось получить индикаторы."

        closes = [c[4] for c in binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=50)]
        ema = EMAIndicator(pd.Series(closes), window=20).ema_indicator().iloc[-1]

        df = pd.DataFrame(binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=20),
                          columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range().iloc[-1]

        price_position = "🔹 Цена между уровнями"
        if price <= bb_lower:
            price_position = "🟢 Цена у нижней границы BB"
        elif price >= bb_upper:
            price_position = "🔴 Цена у верхней границы BB"

        orderbook = binance.fetch_order_book(symbol, limit=10)
        bid_volume = sum([b[1] for b in orderbook['bids'][:3]])
        ask_volume = sum([a[1] for a in orderbook['asks'][:3]])
        imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1)

        confidence = 0
        if rsi < 35: confidence += 1
        if price <= bb_lower: confidence += 1
        if imbalance > 0.2: confidence += 1
        if price > ema: confidence += 1
        if atr > 0: confidence += 1

        signal = "❕ Нет условий для входа"
        if confidence >= 4 and rsi < 35:
            signal = "📈 СИГНАЛ: ПОКУПАТЬ"
        elif confidence >= 4 and rsi > 65:
            signal = "📉 СИГНАЛ: ПРОДАВАТЬ"

        logging.info(
            f"ANALYZE_SMART | {symbol} | Price={price:.2f} | RSI={rsi:.2f} | BB=({bb_lower:.2f}/{bb_upper:.2f}) | "
            f"EMA={ema:.2f} | ATR={atr:.2f} | Bid={bid_volume:.2f} Ask={ask_volume:.2f} | Conf={confidence} | {signal}"
        )

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
