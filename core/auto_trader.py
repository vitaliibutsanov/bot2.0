import logging
from core.order_manager import futures_manager
from core.strategy import analyze_market_smart
from core.adaptive_strategy import get_adaptive_signal
from core.portfolio import virtual_portfolio  # Для виртуального PnL
from utils.safe_send import safe_send_message
from config import CHAT_ID
from log_config import trades_logger  # Лог сделок

last_signal = None
MAX_POSITIONS = 10  # лимит одновременно открытых позиций по паре

async def auto_trade_cycle(context):
    global last_signal
    symbol = "BTC/USDT"

    try:
        # --- Получаем сигнал ---
        try:
            signal = analyze_market_smart(symbol)
        except Exception as e:
            logging.error(f"ANALYZE_ERROR | {e}")
            return

        if "СИГНАЛ" not in signal:
            try:
                signal = get_adaptive_signal(symbol)
            except Exception as e:
                logging.error(f"ADAPTIVE_SIGNAL_ERROR | {e}")
                return

        price = futures_manager.get_current_price(symbol)
        if price is None:
            logging.warning(f"PRICE_FETCH_FAIL | {symbol}")
            return

        # --- Проверка confidence ---
        confidence = 0
        try:
            conf_index = signal.find("Доверие:")
            if conf_index != -1:
                confidence = int(signal.split("Доверие:")[1].split("/")[0].strip())
        except:
            confidence = 0

        # --- Пропускаем повторный сигнал ---
        if signal == last_signal:
            logging.info("NO_CHANGE | Сигнал не изменился.")
            return

        # --- Логика открытия позиции ---
        if "ПОКУПАТЬ" in signal and confidence >= 2:
            if len(futures_manager.active_positions) < MAX_POSITIONS:
                tp_price = round(price * 1.015, 2)  # TP +1.5%
                sl_price = round(price * 0.993, 2)  # SL -0.7%
                try:
                    success, order = await futures_manager.open_position(
                        symbol, "BUY", amount=None,
                        stop_loss=sl_price, take_profit=tp_price
                    )
                    if success:
                        amt = order.get("amount", "?")
                        virtual_portfolio.apply_trade(0, "BUY")  # Учёт открытия сделки
                        msg = (f"✅ BUY {symbol} @ {price} | AMOUNT={amt} BTC | "
                               f"TP={tp_price} | SL={sl_price} | Active={len(futures_manager.active_positions)}")
                        trades_logger.info(f"OPEN BUY {symbol} @ {price} | AMOUNT={amt} BTC | TP={tp_price} | SL={sl_price}")
                        await safe_send_message(context.bot, CHAT_ID, msg)
                    else:
                        logging.error(f"Ошибка открытия позиции: {order}")
                except Exception as e:
                    logging.error(f"Ошибка открытия позиции: {e}")
            else:
                logging.info(f"MAX_POSITIONS | Превышен лимит {MAX_POSITIONS} позиций.")

        # --- Логика закрытия позиции ---
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
                           f"Balance={virtual_portfolio.balance:.2f} USDT")
                    trades_logger.info(f"CLOSE {symbol} @ {price} | PnL={pnl:.2f} USDT")
                    await safe_send_message(context.bot, CHAT_ID, msg)

                    await safe_send_message(context.bot, CHAT_ID, virtual_portfolio.full_report())
                else:
                    logging.error(f"Ошибка закрытия позиции: {msg}")
            except Exception as e:
                logging.error(f"Ошибка закрытия позиции: {e}")

        last_signal = signal

    except Exception as e:
        logging.error(f"Ошибка в auto_trade_cycle: {e}")
        await safe_send_message(context.bot, CHAT_ID, f"⚠ Ошибка автотрейда: {e}")
