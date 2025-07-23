import logging
from datetime import datetime, timedelta
from config import binance, TRADE_PERCENT  # TRADE_PERCENT добавлен в config.py

class FuturesManager:
    def __init__(self):
        self.active_positions = {}
        self.loss_streak = 0
        self.max_loss_streak = 20  # Лимит убыточных сделок увеличен
        self.cooldown_until = None
        self.default_percent = TRADE_PERCENT  # Процент из config.py

    def is_paused(self):
        return self.cooldown_until and datetime.now() < self.cooldown_until

    def get_current_price(self, symbol):
        """Возвращает текущую цену символа или None при ошибке."""
        try:
            ticker = binance.fetch_ticker(symbol)
            price = ticker.get('last')
            logging.info(f"[DEBUG] Current price for {symbol} = {price}")
            return price
        except Exception as e:
            logging.error(f"PRICE_ERROR | {symbol} | {e}")
            return None

    def get_balance(self, asset="USDT"):
        """Получить баланс для указанного актива."""
        try:
            balance = binance.fetch_balance()
            total_balance = balance.get('total', {}).get(asset, 0)
            logging.info(f"[DEBUG] Balance for {asset} = {total_balance}")
            return total_balance
        except Exception as e:
            logging.error(f"BALANCE_ERROR | {e}")
            return 0

    def calculate_amount(self, symbol, percent=None):
        """Расчёт размера сделки в монетах от процента депозита."""
        if percent is None:
            percent = self.default_percent

        balance = self.get_balance("USDT")
        price = self.get_current_price(symbol)
        logging.info(f"[DEBUG] Calculating amount: balance={balance}, price={price}, percent={percent}")

        if price is None or balance <= 0:
            logging.warning("[DEBUG] calculate_amount вернул None (баланс или цена некорректны)")
            return None

        trade_usdt = balance * percent
        if trade_usdt < 10:
            trade_usdt = 10

        trade_amount = round(trade_usdt / price, 4)
        logging.info(f"[DEBUG] Trade amount = {trade_amount} BTC (на {trade_usdt} USDT)")
        return trade_amount

    async def open_position(self, symbol, side, amount=None, leverage=5, stop_loss=None, take_profit=None):
        """Открытие позиции с динамическим расчетом размера."""
        if self.is_paused():
            return False, f"Торговля на паузе до {self.cooldown_until.strftime('%H:%M:%S')}."
        try:
            if amount is None:
                amount = self.calculate_amount(symbol)
                if amount is None:
                    return False, "Не удалось рассчитать размер сделки."

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
                        logging.warning(f"PAUSE | {self.max_loss_streak} убытков подряд. Пауза 6 часов.")
                    closed_positions.append(f"SL сработал: {pos['symbol']} @ {price:.2f}")
            except Exception as e:
                logging.error(f"CHECK_POSITION_ERROR | {pid} | {str(e)}")
        return closed_positions

futures_manager = FuturesManager()

# ==== Заглушка auto_command ====
async def auto_command():
    try:
        if futures_manager.active_positions:
            return f"Активные позиции: {len(futures_manager.active_positions)}"
        else:
            return "Активных позиций нет."
    except Exception as e:
        return f"Ошибка авто-команды: {e}"
