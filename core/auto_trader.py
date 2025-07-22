from core.adaptive_strategy import get_adaptive_signal, register_trade
from core.order_manager import futures_manager
from core.portfolio import virtual_portfolio
from config import CHAT_ID
import logging

async def auto_trade_cycle(context):
    symbol = "BTC/USDT"
    try:
        # Получаем сигнал (адаптивная стратегия)
        signal = get_adaptive_signal(symbol)
        message = None

        # ===== Открытие позиции =====
        if "ПОКУПАТЬ" in signal:
            amount = 0.01  # Тестовый объём
            price = futures_manager.get_current_price(symbol)
            success, order = await futures_manager.open_position(symbol, "BUY", amount)
            if success:
                register_trade()
                message = f"✅ Открыта позиция BUY {amount} {symbol} @ {price}"
            else:
                message = f"⚠ Ошибка открытия позиции: {order}"

        # ===== Закрытие позиции =====
        elif "ПРОДАВАТЬ" in signal and futures_manager.active_positions:
            pid = next(iter(futures_manager.active_positions))
            success, msg = await futures_manager.close_position(pid)
            price = futures_manager.get_current_price(symbol)
            if success:
                register_trade()
                profit = (price - futures_manager.active_positions[pid]['entry_price']) \
                         * futures_manager.active_positions[pid]['amount']
                virtual_portfolio.update_balance(profit)
                message = f"🔴 Закрыта позиция {symbol} @ {price}\nПрибыль: {profit:.2f} USDT"
            else:
                message = f"⚠ Ошибка закрытия позиции: {msg}"

        # Отправляем уведомление только при сделках
        if message:
            await context.bot.send_message(chat_id=CHAT_ID, text=message)

    except Exception as e:
        logging.error(f"Ошибка в auto_trade_cycle: {e}")
        await context.bot.send_message(chat_id=CHAT_ID, text=f"⚠ Ошибка автотрейда: {e}")
