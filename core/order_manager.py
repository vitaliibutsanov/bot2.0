import logging
from datetime import datetime
from config import binance, CHAT_ID
import json
import os
from core.portfolio import virtual_portfolio
from log_config import trades_logger
from core.risk_manager import risk_manager  # Новый модуль для риск-контроля
from utils.safe_send import safe_send_message  # Для отправки сообщений

OPEN_POSITIONS_FILE = "logs/open_positions.log"
MAX_SINGLE_TRADE = 0.01  # Максимальный объем для одной сделки (BTC)
MAX_SYMBOL_VOLUME = 0.02  # Максимальный суммарный объем по символу (BTC)


class FuturesManager:
    def __init__(self):
        self.active_positions = {}
        self._load_positions()
        self._ensure_portfolio_file()
        self.sync_open_positions()  # Синхронизация при старте

    def _ensure_portfolio_file(self):
        """Создает portfolio.json, если его нет."""
        try:
            os.makedirs("logs", exist_ok=True)
            portfolio_file = "logs/portfolio.json"
            if not os.path.exists(portfolio_file):
                virtual_portfolio._save_portfolio()
                logging.info("[INIT] Создан новый portfolio.json")
        except Exception as e:
            logging.error(f"PORTFOLIO_INIT_ERROR | {e}")

    def _save_positions(self):
        try:
            os.makedirs("logs", exist_ok=True)
            with open(OPEN_POSITIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.active_positions, f, default=str, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"OPEN_POSITIONS_SAVE_ERROR | {e}")

    def _load_positions(self):
        try:
            if os.path.exists(OPEN_POSITIONS_FILE):
                with open(OPEN_POSITIONS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for pid, pos in data.items():
                        if isinstance(pos.get("opened_at"), str):
                            try:
                                pos["opened_at"] = datetime.fromisoformat(pos["opened_at"])
                            except Exception:
                                pass
                    self.active_positions = data
                trades_logger.info(f"[DEBUG] Загружены позиции из лога: {len(self.active_positions)}")
        except Exception as e:
            logging.error(f"OPEN_POSITIONS_LOAD_ERROR | {e}")

    def sync_open_positions(self):
        """Синхронизирует открытые позиции с биржей и очищает неактуальные."""
        try:
            open_orders = binance.fetch_open_orders(symbol="BTC/USDT")  # Указали symbol для уменьшения warning

            os.makedirs("logs", exist_ok=True)
            open_debug_file = "logs/open_orders_debug.log"
            with open(open_debug_file, "w", encoding="utf-8") as dbg:
                dbg.write(json.dumps(open_orders, indent=2, ensure_ascii=False))

            trades_logger.info(f"[DEBUG] OPEN_ORDERS_RAW: {json.dumps(open_orders, indent=2, ensure_ascii=False)}")

            current_ids = set()
            count_before = len(self.active_positions)

            for order in open_orders:
                order_id = (
                    order.get("id")
                    or order.get("orderId")
                    or order.get("info", {}).get("id")
                    or order.get("info", {}).get("orderId")
                )

                if order_id is None:
                    logging.error(f"[SYNC_ERROR] Не удалось определить ID ордера: {order}")
                    continue

                order_id = str(order_id)
                current_ids.add(order_id)
                symbol = order.get("symbol") or order.get("info", {}).get("symbol")
                amount = order.get("amount") or order.get("info", {}).get("origQty")
                price = order.get("price") or self.get_current_price(symbol)
                side = order.get("side") or order.get("info", {}).get("side")

                if not symbol or not amount:
                    logging.error(f"[SYNC_ERROR] Некорректный ордер: {order}")
                    continue

                if order_id not in self.active_positions:
                    self.active_positions[order_id] = {
                        "symbol": symbol,
                        "side": side,
                        "amount": float(amount),
                        "entry_price": price,
                        "stop_loss": None,
                        "take_profit": None,
                        "opened_at": datetime.now().isoformat()
                    }
                    trades_logger.info(f"SYNC_POSITION | {symbol} | {side} | {amount} @ {price}")

            stale_ids = [pid for pid in self.active_positions if pid not in current_ids]
            for pid in stale_ids:
                trades_logger.info(f"SYNC_REMOVE | Ордер {pid} удалён (не найден на бирже)")
                del self.active_positions[pid]

            self._save_positions()
            count_after = len(self.active_positions)
            logging.info(f"[SYNC] Активные позиции: {count_after} (было {count_before})")
        except Exception as e:
            logging.error(f"SYNC_OPEN_POSITIONS_ERROR | {e}")

    def get_current_price(self, symbol):
        try:
            ticker = binance.fetch_ticker(symbol)
            return ticker.get("last") if ticker else None
        except Exception as e:
            logging.error(f"PRICE_ERROR | {symbol} | {e}")
            return None

    def get_balance(self, asset="USDT"):
        try:
            balance = binance.fetch_balance()
            return balance.get("total", {}).get(asset, 0)
        except Exception as e:
            logging.error(f"BALANCE_ERROR | {e}")
            return 0

    def get_recent_ohlcv(self, symbol, timeframe="1m", limit=2):
        """Получение последних свечей OHLCV."""
        try:
            return binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception as e:
            logging.error(f"OHLCV_ERROR | {symbol} | {e}")
            return []

    def create_oco_order(self, symbol, side, amount, take_profit, stop_loss, context=None):
        """Создает OCO ордер с проверкой маржи и автоматической корректировкой объёма."""
        try:
            current_price = self.get_current_price(symbol)
            if not current_price:
                raise ValueError("Не удалось получить текущую цену для OCO ордера.")

            usdt_balance = self.get_balance("USDT")
            required_margin = amount * current_price
            if usdt_balance < required_margin:
                logging.warning(
                    f"OCO_ORDER | Недостаточно средств: нужно {required_margin:.2f} USDT, "
                    f"доступно {usdt_balance:.2f} USDT."
                )
                amount = round((usdt_balance / current_price) * 0.9, 4)
                logging.warning(f"OCO_ORDER | Снижен объем сделки до {amount}.")
                if context:
                    import asyncio
                    asyncio.create_task(
                        safe_send_message(context.bot, CHAT_ID,
                                          f"⚠ Недостаточно маржи. Объем сделки снижен до {amount}.")
                    )

            if side == "BUY":
                if stop_loss >= current_price:
                    stop_loss = round(current_price * 0.98, 2)
                if take_profit <= current_price:
                    take_profit = round(current_price * 1.02, 2)
            else:
                if stop_loss <= current_price:
                    stop_loss = round(current_price * 1.02, 2)
                if take_profit >= current_price:
                    take_profit = round(current_price * 0.98, 2)

            opposite = "SELL" if side == "BUY" else "BUY"

            binance.create_order(symbol, "STOP_MARKET", opposite, amount, None, {"stopPrice": stop_loss})
            binance.create_order(symbol, "LIMIT", opposite, amount, take_profit)

            trades_logger.info(f"OCO_ORDER_SET | {symbol} | TP={take_profit} | SL={stop_loss}")
        except Exception as e:
            logging.error(f"OCO_ORDER_ERROR | {symbol} | {e}")
            if context:
                import asyncio
                asyncio.create_task(
                    safe_send_message(context.bot, CHAT_ID,
                                      f"⚠ Ошибка установки OCO ордера: {e}")
                )

    async def open_position(self, symbol, side, amount=None, leverage=5, stop_loss=None, take_profit=None, context=None):
        """Открытие позиции с фильтрами от суперпозиций."""
        balance = self.get_balance("USDT")
        ok, reason = risk_manager.check_trade_permission(balance)
        if not ok:
            return False, reason

        try:
            price = self.get_current_price(symbol)
            if amount is None:
                amount = risk_manager.calculate_position_size(balance, price)
                if amount is None:
                    return False, "Не удалось рассчитать размер сделки."

            # --- Фильтр 1: Проверка на аномально большой объем ---
            if amount > MAX_SINGLE_TRADE:
                logging.warning(f"TRADE_BLOCKED | Объем {amount} превышает лимит {MAX_SINGLE_TRADE} BTC.")
                return False, f"Объем сделки ({amount}) превышает допустимый лимит {MAX_SINGLE_TRADE} BTC."

            # --- Фильтр 2: Сумма ордеров по символу ---
            total_volume = sum(pos["amount"] for pos in self.active_positions.values() if pos["symbol"] == symbol)
            if total_volume + amount > MAX_SYMBOL_VOLUME:
                logging.warning(f"TRADE_BLOCKED | Общий объем по {symbol} превысит {MAX_SYMBOL_VOLUME} BTC.")
                return False, f"Суммарный объем по {symbol} превышает лимит {MAX_SYMBOL_VOLUME} BTC."

            if hasattr(binance, "set_leverage"):
                try:
                    binance.set_leverage(leverage, symbol)
                except Exception as e:
                    logging.warning(f"LEVERAGE_SKIP | {symbol} | {e}")

            order = binance.create_order(symbol=symbol, type="MARKET", side=side, amount=amount)
            entry_price = order.get("price", price)
            position_id = str(order.get("id", datetime.now().timestamp()))

            self.active_positions[position_id] = {
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "opened_at": datetime.now().isoformat()
            }
            self._save_positions()

            virtual_portfolio.apply_trade(0, "BUY")

            if stop_loss and take_profit:
                self.create_oco_order(symbol, side, amount, take_profit, stop_loss, context)

            trades_logger.info(f"FUTURES_OPEN | {symbol} | {side} | {amount} @ {entry_price}")
            return True, order
        except Exception as e:
            logging.error(f"FUTURES_ERROR | {symbol} | {str(e)}")
            return False, str(e)

    async def close_position(self, position_id):
        """Закрытие позиции."""
        try:
            pos = self.active_positions.get(position_id)
            if not pos:
                return False, "Позиция не найдена."

            current_price = self.get_current_price(pos["symbol"])
            side = "SELL" if pos["side"] == "BUY" else "BUY"

            available_balance = self.get_balance("USDT") / current_price
            amount_to_close = min(pos["amount"], round(available_balance * 0.99, 4))
            if amount_to_close <= 0:
                return False, "Недостаточно средств для закрытия позиции."

            binance.create_order(symbol=pos["symbol"], type="MARKET", side=side, amount=amount_to_close)
            trades_logger.info(f"FUTURES_CLOSE | {pos['symbol']} | {pos['side']} | {amount_to_close}")

            pnl_usdt = (current_price - pos["entry_price"]) * amount_to_close
            if pos["side"] == "SELL":
                pnl_usdt = -pnl_usdt
            virtual_portfolio.apply_trade(pnl_usdt, "SELL")

            risk_manager.record_trade(pnl_usdt)

            del self.active_positions[position_id]
            self._save_positions()
            return True, "Позиция закрыта."
        except Exception as e:
            return False, str(e)


futures_manager = FuturesManager()

_last_position_count = None  # Для отслеживания изменений количества позиций

async def auto_command():
    global _last_position_count
    try:
        current_count = len(futures_manager.active_positions)

        if _last_position_count == current_count:
            logging.info(f"[NO_CHANGE] Активных позиций: {current_count}")
            return None

        _last_position_count = current_count

        if current_count:
            return f"Активные позиции: {current_count}"
        else:
            return "Активных позиций нет."
    except Exception as e:
        return f"Ошибка авто-команды: {e}"
