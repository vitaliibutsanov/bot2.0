import os
import ccxt
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler
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

async def send_telegram(msg):
    """Отправка сообщения в Telegram"""
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=msg)

async def check_balance(update: Update = None):
    """Проверка баланса на Binance"""
    try:
        balance = binance.fetch_balance()['USDT']['free']
        msg = f"💰 Баланс: {balance:.2f} USDT"
        if update:
            await update.message.reply_text(msg)
        await send_telegram(msg)
    except Exception as e:
        error_msg = f"❌ Помилка: {str(e)}"
        if update:
            await update.message.reply_text(error_msg)
        await send_telegram(error_msg)

async def start(update: Update, context):
    """Обробник команди /start"""
    await update.message.reply_text(
        "🤖 Бот для Binance активовано!\n"
        "Доступні команди:\n"
        "/balance - Перевірити баланс\n"
        "/price BTC - Курс BTC"
    )

async def price(update: Update, context):
    """Курс криптовалюти"""
    coin = context.args[0].upper() if context.args else 'BTC'
    ticker = binance.fetch_ticker(f"{coin}/USDT")
    await update.message.reply_text(
        f"📊 {coin}: {ticker['last']:.2f} USDT\n"
        f"24h: {ticker['percentage']:.2f}%"
    )

def run_bot():
    """Запуск бота"""
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", check_balance))
    app.add_handler(CommandHandler("price", price))
    app.run_polling()

if __name__ == "__main__":
    # Асинхронний запуск
    asyncio.run(run_bot())