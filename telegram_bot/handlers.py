import logging
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext, Application
from config import TELEGRAM_TOKEN, CHAT_ID, binance  # Исправленный импорт
from core.portfolio import get_portfolio_status
from core.strategy import analyze_market_smart
from core.order_manager import auto_command

logger = logging.getLogger(__name__)


# ====== Команды бота ======

async def start_command(update: Update, context: CallbackContext):
    await update.message.reply_text("🤖 Привет! Я торговый бот. Используй /help для списка команд.")


async def help_command(update: Update, context: CallbackContext):
    commands = (
        "/start - Запуск бота\n"
        "/help - Справка\n"
        "/balance - Проверить баланс\n"
        "/price <symbol> [quote] - Цена монеты\n"
        "/analyze - Умный анализ рынка\n"
        "/status - Проверка автотрейда\n"
        "/auto - Включить автотрейд\n"
        "/report - Отчет по портфелю"
    )
    await update.message.reply_text(commands)


async def balance_command(update: Update, context: CallbackContext):
    try:
        balance = binance.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        await update.message.reply_text(f"💰 Баланс: {usdt_balance} USDT")
    except Exception as e:
        await update.message.reply_text(f"⚠ Ошибка: {e}")


async def price_command(update: Update, context: CallbackContext):
    try:
        if len(context.args) == 0:
            symbol = "BTC/USDT"
        elif len(context.args) == 1:
            symbol = context.args[0].upper() + "/USDT"
        else:
            base = context.args[0].upper()
            quote = context.args[1].upper()
            symbol = f"{base}/{quote}"

        ticker = binance.fetch_ticker(symbol)
        price = ticker['last']
        await update.message.reply_text(f"📊 {symbol}: {price}")
    except Exception as e:
        await update.message.reply_text(f"⚠ Ошибка: {e}")


async def analyze_command(update: Update, context: CallbackContext):
    result = analyze_market_smart()
    await update.message.reply_text(result)


async def status_command(update: Update, context: CallbackContext):
    await update.message.reply_text("🔴 Автотрейдинг ВКЛ\nРиск: 2.0%\nБаланс: 0 USDT")



async def auto_command_handler(update: Update, context: CallbackContext):
    result = await auto_command()
    await update.message.reply_text(result)


async def report_command(update: Update, context: CallbackContext):
    report = get_portfolio_status()
    await update.message.reply_text(report)


# ========== Инициализация бота ==========
def setup_telegram_bot():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("auto", auto_command_handler))
    app.add_handler(CommandHandler("report", report_command))

    return app
