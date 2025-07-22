import logging
from core.order_manager import futures_manager
from core.strategy import analyze_market_smart
from core.adaptive_strategy import get_adaptive_signal
from utils.safe_send import safe_send_message
from config import CHAT_ID
from log_config import trades_logger  # Лог сделок

last_signal = None

async def auto_trade_cycle(context):
    global last_signal
    symbol = "BTC/USDT"

    try:
        # Получаем сигнал
        try:
            signal = analyze_market_smart(symbol)
        except Exception as e:
            logging.error(f"ANALYZE_ERROR | {e}")
            return  # если анализ сломался, выходим

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

        # Пропускаем, если сигнал не изменился
        if signal == last_signal:
            logging.info(f"NO_CHANGE | Сигнал не изменился.")
            return

        # --- Открытие позиции ---
        if "ПОКУПАТЬ" in signal:
            try:
                success, order = await futures_manager.open_position(symbol, "BUY", 0.001)
                if success:
                    msg = f"✅ BUY {symbol} @ {price}"
                    trades_logger.info(f"OPEN BUY {symbol} @ {price}")
                    await safe_send_message(context.bot, CHAT_ID, msg)
                else:
                    logging.error(f"Ошибка открытия позиции: {order}")
            except Exception as e:
                logging.error(f"Ошибка открытия позиции: {e}")

        # --- Закрытие позиции ---
        elif "ПРОДАВАТЬ" in signal and futures_manager.active_positions:
            try:
                pid = next(iter(futures_manager.active_positions))
                success, msg = await futures_manager.close_position(pid)
                if success:
                    msg = f"✅ SELL {symbol} @ {price}"
                    trades_logger.info(f"CLOSE {symbol} @ {price}")
                    await safe_send_message(context.bot, CHAT_ID, msg)
                else:
                    logging.error(f"Ошибка закрытия позиции: {msg}")
            except Exception as e:
                logging.error(f"Ошибка закрытия позиции: {e}")

        last_signal = signal

    except Exception as e:
        logging.error(f"Ошибка в auto_trade_cycle: {e}")
        await safe_send_message(context.bot, CHAT_ID, f"⚠ Ошибка автотрейда: {e}")
