import logging
from core.order_manager import futures_manager
from core.strategy import analyze_market_smart
from core.binance_api import get_binance_balance
from core.portfolio import virtual_portfolio
from config import CHAT_ID, binance, RISK_PER_TRADE

logger = logging.getLogger(__name__)

async def auto_trade_cycle(context):
    """Оптимизированный цикл автотрейда."""
    try:
        symbol = "BTC/USDT"
        signal = analyze_market_smart(symbol)
        price = binance.fetch_ticker(symbol)['last']
        balance = get_binance_balance()

        amount = round((balance['USDT'] * RISK_PER_TRADE) / price, 6)
        message = f"🔍 Анализ: {symbol}\nЦена: {price}\nСигнал: {signal}"

        # ====== Открытие позиции ======
        if "ПОКУПАТЬ" in signal:
            success, order = await futures_manager.open_position(
                symbol=symbol, side='BUY', amount=amount
            )
            if success:
                message = f"📈 Открыта позиция BUY {amount} {symbol} @ {price}"
            else:
                message = f"⚠ Ошибка открытия позиции: {order}"

        # ====== Закрытие позиции ======
        elif "ПРОДАВАТЬ" in signal and futures_manager.active_positions:
            pid = next(iter(futures_manager.active_positions))
            success, msg = await futures_manager.close_position(pid)
            if success:
                profit = (price - futures_manager.active_positions[pid]['entry_price']) * futures_manager.active_positions[pid]['amount']
                virtual_portfolio.update_balance(profit)
                message = f"📉 Закрыта позиция {symbol} @ {price}\nПрибыль: {profit:.2f} USDT"
            else:
                message = f"⚠ Ошибка закрытия позиции: {msg}"

        # Отправляем результат в Telegram
        await context.bot.send_message(chat_id=CHAT_ID, text=message)

    except Exception as e:
        logger.error(f"Ошибка в auto_trade_cycle: {e}")
        await context.bot.send_message(chat_id=CHAT_ID, text=f"⚠ Ошибка автотрейда: {e}")
