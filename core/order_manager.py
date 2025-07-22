import logging
from datetime import datetime, timedelta
from config import binance


class FuturesManager:
    def __init__(self):
        self.active_positions = {}
        self.loss_streak = 0
        self.max_loss_streak = 3
        self.cooldown_until = None

    def is_paused(self):
        return self.cooldown_until and datetime.now() < self.cooldown_until

    def get_current_price(self, symbol):
        """Возвращает текущую цену символа или None при ошибке."""
        try:
            ticker = binance.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logging.error(f"PRICE_ERROR | {symbol} | {e}")
            return None

    async def open_position(self, symbol, side, amount, leverage=5, stop_loss=None, take_profit=None):
        """Открытие позиции с проверкой типа рынка (spot/futures)."""
        if self.is_paused():
            return False, f"Торговля на паузе до {self.cooldown_until.strftime('%H:%M:%S')}."
        try:
            # Проверяем поддержку установки плеча
            try:
                if hasattr(binance, "set_leverage"):
                    binance.set_leverage(leverage, symbol)
            except Exception as e:
                logging.warning(f"LEVERAGE_SKIP | {symbol} | {e}")

            order = binance.create_order(symbol=symbol, type='MARKET', side=side, amount=amount)
            entry_price = order.get('price', self.get_current_price(symbol))
            self.active_positions[order['id']] = {
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'opened_at': datetime.now()
            }
            logging.info(f"FUTURES_OPEN | {symbol} | {side} | {amount} @ {entry_price}")
            return True, order
        except Exception as e:
            logging.error(f"FUTURES_ERROR | {symbol} | {str(e)}")
            return False, str(e)

    async def close_position(self, position_id):
        try:
            pos = self.active_positions.get(position_id)
            if not pos:
                return False, "Позиция не найдена."
            side = 'SELL' if pos['side'] == 'BUY' else 'BUY'
            binance.create_order(symbol=pos['symbol'], type='MARKET', side=side, amount=pos['amount'])
            logging.info(f"FUTURES_CLOSE | {pos['symbol']} | {pos['side']} | {pos['amount']}")
            del self.active_positions[position_id]
            return True, "Позиция закрыта."
        except Exception as e:
            return False, str(e)

    async def check_positions(self):
        closed_positions = []
        for pid, pos in list(self.active_positions.items()):
            try:
                price = self.get_current_price(pos['symbol'])
                if price is None:
                    continue
                side = pos['side']
                if pos['take_profit'] and ((side == 'BUY' and price >= pos['take_profit']) or (side == 'SELL' and price <= pos['take_profit'])):
                    await self.close_position(pid)
                    closed_positions.append(f"TP сработал: {pos['symbol']} @ {price:.2f}")
                    continue
                if pos['stop_loss'] and ((side == 'BUY' and price <= pos['stop_loss']) or (side == 'SELL' and price >= pos['stop_loss'])):
                    await self.close_position(pid)
                    self.loss_streak += 1
                    if self.loss_streak >= self.max_loss_streak:
                        self.cooldown_until = datetime.now() + timedelta(hours=6)
                        logging.warning("PAUSE | 3 убытка подряд. Пауза 6 часов.")
                    closed_positions.append(f"SL сработал: {pos['symbol']} @ {price:.2f}")
            except Exception as e:
                logging.error(f"CHECK_POSITION_ERROR | {pid} | {str(e)}")
        return closed_positions


futures_manager = FuturesManager()


# ==== Заглушка auto_command ====
async def auto_command():
    """Проверка активных позиций и возврат статуса."""
    try:
        if futures_manager.active_positions:
            return f"Активные позиции: {len(futures_manager.active_positions)}"
        else:
            return "Активных позиций нет."
    except Exception as e:
        return f"Ошибка авто-команды: {e}"
