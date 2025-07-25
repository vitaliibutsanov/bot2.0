import logging
from time import time
from core.order_manager import futures_manager
from core.strategy import analyze_market_smart
from core.adaptive_strategy import get_adaptive_signal
from core.portfolio import virtual_portfolio
from core.risk_manager import risk_manager  # Подключаем новый risk_manager
from utils.safe_send import safe_send_message
from config import CHAT_ID, binance
from log_config import trades_logger, signals_logger

last_signal = None
last_signal_time = 0
MAX_POSITIONS = 10
last_positions_count = 0  # Храним количество позиций для отслеживания изменений

# === Настройки ===
TP_PERCENT = 0.011  # 1.1%
SL_PERCENT = 0.05   # 5%
ANOMALY_THRESHOLD = 0.015  # 1.5%
SIGNAL_CACHE_TIME = 60
verbose_signals = False


def is_anomalous_move(symbol: str, price: float):
    """Фильтр для защиты от резких скачков цены."""
    try:
        ohlcv = futures_manager.get_recent_ohlcv(symbol, limit=2)
        if ohlcv and len(ohlcv) > 1:
            last_candle = ohlcv[-1]
            candle_open = last_candle[1]
            if candle_open > 0 and abs(price - candle_open) / candle_open > ANOMALY_THRESHOLD:
                return True
    except Exception as e:
        logging.error(f"ANOMALY_CHECK_ERROR | {e}")
    return False


async def sync_open_positions(context=None):
    """Синхронизирует активные позиции с биржей и уведомляет о восстановлении."""
    global last_positions_count
    try:
        open_positions = binance.fetch_positions()
        restored = 0
        futures_manager.active_positions.clear()

        for pos in open_positions:
            contracts = float(pos.get('contracts', 0))
            if contracts > 0:
                symbol = pos['symbol']
                side = "BUY" if contracts > 0 else "SELL"
                entry_price = float(pos.get('entryPrice', 0))
                futures_manager.active_positions[str(
                    pos.get('id') or pos.get('orderId') or pos.get('info', {}).get('id'))] = {
                    'symbol': symbol,
                    'side': side,
                    'amount': contracts,
                    'entry_price': entry_price,
                    'stop_loss': None,
                    'take_profit': None,
                    'opened_at': None
                }
                restored += 1

        current_count = len(futures_manager.active_positions)
        if restored > 0:
            logging.info(f"[SYNC] Восстановлено {restored} открытых позиций.")
            if context:
                await safe_send_message(
                    context.bot, CHAT_ID,
                    f"♻ Восстановлено {restored} позиций после рестарта.\n"
                    f"Текущие активные позиции: {current_count}"
                )
        else:
            logging.info("[SYNC] Открытых позиций не найдено.")
            if context:
                await safe_send_message(context.bot, CHAT_ID, "♻ Открытых позиций не найдено.")

        last_positions_count = current_count
    except Exception as e:
        logging.error(f"[SYNC_ERROR] {e}")
        if context:
            await safe_send_message(context.bot, CHAT_ID, f"⚠ Ошибка синхронизации позиций: {e}")


async def notify_position_change(context):
    """Отправляет сообщение при изменении количества активных позиций."""
    global last_positions_count
    current_count = len(futures_manager.active_positions)
    if current_count != last_positions_count:
        diff = current_count - last_positions_count
        change = "увеличилось" if diff > 0 else "уменьшилось"
        await safe_send_message(
            context.bot, CHAT_ID,
            f"🔔 Количество активных позиций {change}: {current_count} (было {last_positions_count})"
        )
        last_positions_count = current_count


async def auto_trade_cycle(context):
    global last_signal, last_signal_time
    symbol = "BTC/USDT"

    try:
        if not futures_manager.active_positions:
            await sync_open_positions(context)
        else:
            await notify_position_change(context)

        # === Анализ рынка ===
        try:
            signal = analyze_market_smart(symbol)
            if not signal or "❌" in signal:
                return
        except Exception as e:
            logging.error(f"ANALYZE_ERROR | {e}")
            return

        # === Fallback на адаптивную стратегию ===
        if "СИГНАЛ" not in signal and "СЛАБЫЙ" not in signal:
            try:
                signal = get_adaptive_signal(symbol)
            except Exception as e:
                logging.error(f"ADAPTIVE_SIGNAL_ERROR | {e}")
                return

        price = futures_manager.get_current_price(symbol)
        if price is None:
            return

        if is_anomalous_move(symbol, price):
            logging.warning(f"ANOMALY_MOVE | {symbol} | {price}")
            return

        # === Проверка доверия к сигналу ===
        confidence = 0
        try:
            conf_index = signal.find("Доверие:")
            if conf_index != -1:
                confidence = int(signal.split("Доверие:")[1].split("/")[0].strip())
        except Exception:
            confidence = 0

        # === Защита от спама сигналами ===
        now = time()
        if signal == last_signal and (now - last_signal_time < SIGNAL_CACHE_TIME):
            if verbose_signals:
                signals_logger.info("NO_CHANGE | Сигнал не изменился.")
            return
        last_signal = signal
        last_signal_time = now

        balance = futures_manager.get_balance("USDT")
        allowed, reason = risk_manager.check_trade_permission(balance)
        if not allowed:
            logging.warning(f"TRADE_BLOCKED | {reason}")
            return

        # === Логика открытия позиции ===
        if "ПОКУПАТЬ" in signal and confidence >= 2:
            if len(futures_manager.active_positions) < MAX_POSITIONS:
                tp_price = round(price * (1 + TP_PERCENT), 2)
                sl_price = round(price * (1 - SL_PERCENT), 2)

                # Проверка маржи перед открытием позиции
                required_margin = balance * risk_manager.max_trade_percent
                if balance < required_margin:
                    await safe_send_message(
                        context.bot, CHAT_ID,
                        f"⚠ Недостаточно средств для открытия позиции. Баланс: {balance:.2f} USDT"
                    )
                    logging.warning(f"TRADE_SKIPPED | Недостаточно маржи: {balance:.2f} < {required_margin:.2f}")
                    return

                try:
                    success, order = await futures_manager.open_position(
                        symbol, "BUY", amount=None,
                        stop_loss=sl_price, take_profit=tp_price
                    )
                    if success:
                        amt = order.get("amount", "?")
                        virtual_portfolio.apply_trade(0, "BUY")
                        msg = (f"✅ BUY {symbol} @ {price} | AMOUNT={amt} BTC | "
                               f"TP={tp_price} | SL={sl_price} | Active={len(futures_manager.active_positions)}")
                        trades_logger.info(
                            f"OPEN BUY {symbol} @ {price} | AMOUNT={amt} BTC | TP={tp_price} | SL={sl_price}"
                        )
                        await safe_send_message(context.bot, CHAT_ID, msg)
                        await notify_position_change(context)
                    else:
                        logging.error(f"Ошибка открытия позиции: {order}")
                except Exception as e:
                    logging.error(f"Ошибка открытия позиции: {e}")
            else:
                logging.info(f"MAX_POSITIONS | Лимит {MAX_POSITIONS} позиций.")

        # === Логика закрытия позиции ===
        elif "ПРОДАВАТЬ" in signal and futures_manager.active_positions:
            try:
                pid = next(iter(futures_manager.active_positions))
                position = futures_manager.active_positions[pid]
                entry_price = position['entry_price']
                amount = position['amount']

                success, msg = await futures_manager.close_position(pid)
                if success:
                    pnl = (price - entry_price) * amount
                    virtual_portfolio.apply_trade(pnl, "SELL")

                    msg = (f"✅ SELL {symbol} @ {price} | PnL={pnl:.2f} USDT | "
                           f"Balance={virtual_portfolio.balance:.2f} USDT | "
                           f"Active={len(futures_manager.active_positions)}")
                    trades_logger.info(f"CLOSE {symbol} @ {price} | PnL={pnl:.2f} USDT")
                    await safe_send_message(context.bot, CHAT_ID, msg)
                    await safe_send_message(context.bot, CHAT_ID, virtual_portfolio.full_report())
                    await notify_position_change(context)
                else:
                    logging.error(f"Ошибка закрытия позиции: {msg}")
            except Exception as e:
                logging.error(f"Ошибка закрытия позиции: {e}")

    except Exception as e:
        logging.error(f"Ошибка в auto_trade_cycle: {e}")
        await safe_send_message(context.bot, CHAT_ID, f"⚠ Ошибка автотрейда: {e}")
