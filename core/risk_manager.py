import logging 
from datetime import datetime, timedelta
from config import TRADE_PERCENT
from core.strategy import get_technical_indicators  # Для проверки RSI
from ta.volatility import AverageTrueRange
import pandas as pd
from config import binance


class RiskManager:
    def __init__(self, 
                 max_loss_streak=5, 
                 max_drawdown=0.2, 
                 max_trade_percent=TRADE_PERCENT, 
                 min_rsi=25, 
                 max_rsi=75, 
                 max_atr_ratio=0.02,
                 atr_dynamic_mult=2.5):
        """
        max_loss_streak - максимум подряд убыточных сделок до паузы.
        max_drawdown - максимальная просадка баланса (0.2 = 20%).
        max_trade_percent - доля депозита на сделку (например, 0.05 = 5%).
        min_rsi, max_rsi - фильтры RSI.
        max_atr_ratio - ограничение ATR (относительная волатильность).
        atr_dynamic_mult - динамический множитель для фильтра волатильности.
        """
        self.loss_streak = 0
        self.max_loss_streak = max_loss_streak
        self.max_drawdown = max_drawdown
        self.max_trade_percent = max_trade_percent
        self.cooldown_until = None
        self.trade_history = []  # [(timestamp, pnl)]
        self.balance_start = None
        self.min_rsi = min_rsi
        self.max_rsi = max_rsi
        self.max_atr_ratio = max_atr_ratio
        self.atr_dynamic_mult = atr_dynamic_mult

    def is_market_volatile(self, symbol="BTC/USDT", timeframe='1h'):
        """
        Проверка: не слишком ли волатильный рынок по ATR.
        Возвращает (bool, message).
        """
        try:
            df = pd.DataFrame(
                binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=20),
                columns=['time', 'open', 'high', 'low', 'close', 'volume']
            )
            atr_series = AverageTrueRange(
                high=df['high'], low=df['low'], close=df['close'], window=14
            ).average_true_range()

            atr = atr_series.iloc[-1]
            price = df['close'].iloc[-1]
            atr_ratio = atr / price

            last_range = df['high'].iloc[-1] - df['low'].iloc[-1]
            if last_range > atr * self.atr_dynamic_mult:
                msg = (f"ATR={atr:.4f}, Range={last_range:.2f} — рынок экстремально волатилен.")
                logging.warning(f"VOLATILITY_BLOCK | {msg}")
                return True, msg

            if atr_ratio > self.max_atr_ratio:
                msg = f"ATR={atr_ratio:.3f} > {self.max_atr_ratio:.3f} (волатильный рынок)."
                logging.warning(f"VOLATILITY_WARN | {msg}")
                return True, msg

            return False, None
        except Exception as e:
            logging.error(f"ATR_CHECK_ERROR | {e}")
            return False, None

    def check_trade_permission(self, balance, symbol="BTC/USDT"):
        """Проверка: можно ли открывать сделки сейчас."""
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False, f"Торговля на паузе до {self.cooldown_until.strftime('%H:%M:%S')}."

        if self.balance_start and balance < self.balance_start * (1 - self.max_drawdown):
            self.cooldown_until = datetime.now() + timedelta(hours=12)
            logging.warning(f"Пауза: просадка депозита превысила {self.max_drawdown * 100:.0f}%.")
            return False, "Достигнут лимит просадки — пауза 12 часов."

        try:
            price, rsi, bb_high, bb_low, volume = get_technical_indicators(symbol)
            if price and rsi:
                # Проверка RSI
                if rsi < self.min_rsi or rsi > self.max_rsi:
                    return False, f"RSI={rsi:.2f} вне допустимого диапазона [{self.min_rsi}-{self.max_rsi}]."

                # Проверка ATR
                volatile, msg = self.is_market_volatile(symbol)
                if volatile:
                    return False, msg
        except Exception as e:
            logging.error(f"RISK_INDICATOR_CHECK_ERROR | {e}")

        return True, None

    def record_trade(self, pnl):
        """Сохраняем результат сделки (PNL)."""
        self.trade_history.append((datetime.now(), pnl))
        self.loss_streak = self.loss_streak + 1 if pnl < 0 else 0

        if self.loss_streak >= self.max_loss_streak:
            self.cooldown_until = datetime.now() + timedelta(hours=1)
            logging.warning(f"Серия убытков: торговля на паузе до {self.cooldown_until}.")

    def calculate_position_size(self, balance, price):
        """
        Рассчитывает безопасный размер сделки как % от доступного баланса.
        Минимальная сумма сделки — 10 USDT (пример).
        """
        if not price or balance <= 0:
            return None

        trade_usdt = balance * self.max_trade_percent
        if trade_usdt < 10:
            logging.warning(f"Баланс слишком мал для открытия сделки (нужно хотя бы 10 USDT).")
            return None

        return round(trade_usdt / price, 4)

    def reset(self):
        """Сброс риск-метрик."""
        self.loss_streak = 0
        self.cooldown_until = None
        self.trade_history.clear()
        self.balance_start = None
        logging.info("RISK_MANAGER | Метрики сброшены.")


risk_manager = RiskManager()
