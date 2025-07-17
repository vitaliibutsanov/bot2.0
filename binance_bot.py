import os
import ccxt
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from dotenv import load_dotenv

# Загрузка ключей из .env
load_dotenv()

# Инициализация Binance
binance = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'options': {'adjustForTimeDifference': True}
})

# Инициализация Telegram бота
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID'))

def get_binance_balance():
    """Синхронное получение баланса с Binance"""
    balance = binance.fetch_balance()
    return {
        'USDT': balance['total']['USDT'],
        'BTC': balance['total']['BTC'],
        'ETH': balance['total']['ETH']
    }

async def check_balance(update: Update, context: CallbackContext):
    """Обработчик команды /balance"""
    try:
        balance = get_binance_balance()
        response = f"""
💰 Ваши балансы:
USDT: {balance['USDT']:.2f}
BTC: {balance['BTC']:.6f}
ETH: {balance['ETH']:.6f}
        """
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def start(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "🤖 Бот для Binance активирован!\n"
        "Доступные команды:\n"
        "/balance - Проверить баланс\n"
        "/price BTC - Курс BTC"
    )

async def price(update: Update, context: CallbackContext):
    """Курс криптовалюты"""
    try:
        coin = context.args[0].upper() if context.args else 'BTC'
        ticker = binance.fetch_ticker(f"{coin}/USDT")
        await update.message.reply_text(
            f"📊 {coin}: {ticker['last']:.2f} USDT\n"
            f"24h: {ticker['percentage']:.2f}%"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

def main():
    """Запуск бота"""
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", check_balance))
    app.add_handler(CommandHandler("price", price))
    
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()