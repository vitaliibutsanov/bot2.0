import asyncio
import logging
from core.order_manager import futures_manager

# Настроим логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

async def test():
    symbol = "BTC/USDT"

    # Получаем баланс
    balance = futures_manager.get_balance("USDT")
    logging.info(f"Текущий баланс USDT: {balance}")

    # Получаем текущую цену
    price = futures_manager.get_current_price(symbol)
    logging.info(f"Текущая цена {symbol}: {price}")

    # Рассчитываем объём сделки
    amount = futures_manager.calculate_amount(symbol)
    logging.info(f"Рассчитанный объем сделки: {amount} BTC")

    # Проверка на минимальный лот
    if amount is None:
        logging.warning("⚠ Ошибка: невозможно рассчитать объем сделки (balance или price некорректны).")
    elif amount < 0.001:
        logging.warning(f"⚠ Рассчитанный объем ({amount} BTC) меньше минимального лота Binance (0.001 BTC).")
    else:
        logging.info("✅ Объем сделки соответствует минимальным требованиям Binance.")

    # Тестовое открытие позиции (если хочешь проверить на тестнете)
    # success, order = await futures_manager.open_position(symbol, "BUY")
    # logging.info(f"Результат открытия сделки: {success}, {order}")

if __name__ == "__main__":
    asyncio.run(test())
