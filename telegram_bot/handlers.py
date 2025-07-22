import logging
import time
import shutil
import os
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext, Application
from config import TELEGRAM_TOKEN, binance
from core.portfolio import get_portfolio_status
from core.strategy import analyze_market_smart
from core.order_manager import auto_command
from utils.safe_send import safe_send_message

logger = logging.getLogger(__name__)

# ====== Кэш для команды /analyze ======
last_analyze_time = 0
last_analyze_result = "❌ Данные анализа еще не получены."
ANALYZE_CACHE_TIME = 60  # 1 минута

# ====== Универсальный метод отправки ======
async def send_reply(update: Update, context: CallbackContext, text: str):
    """Отправка ответа в чат с безопасной обработкой ошибок."""
    try:
        logger.info(f"COMMAND | {update.message.text}")
        await safe_send_message(context.bot, update.effective_chat.id, text)
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")

# ====== Команды бота ======
async def start_command(update: Update, context: CallbackContext):
    await send_reply(update, context, "🤖 Привет! Я торговый бот. Используй /help для списка команд.")

async def help_command(update: Update, context: CallbackContext):
    commands = (
        "/start - Запуск бота\n"
        "/help - Справка\n"
        "/balance - Проверить баланс\n"
        "/price <symbol> [quote] - Цена монеты\n"
        "/analyze - Умный анализ рынка\n"
        "/status - Проверка автотрейда\n"
        "/auto - Включить автотрейд\n"
        "/report - Отчет по портфелю\n"
        "/logs - Скачать все логи"
    )
    await send_reply(update, context, commands)

async def balance_command(update: Update, context: CallbackContext):
    try:
        balance = binance.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        await send_reply(update, context, f"💰 Баланс: {usdt_balance} USDT")
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка получения баланса: {e}")

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
        price = ticker.get('last', 'N/A')
        await send_reply(update, context, f"📊 {symbol}: {price}")
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка получения цены: {e}")

async def analyze_command(update: Update, context: CallbackContext):
    global last_analyze_time, last_analyze_result
    try:
        now = time.time()
        if now - last_analyze_time > ANALYZE_CACHE_TIME:
            last_analyze_result = analyze_market_smart()
            last_analyze_time = now
        await send_reply(update, context, last_analyze_result)
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка анализа: {e}")

async def status_command(update: Update, context: CallbackContext):
    await send_reply(update, context, "🔴 Автотрейдинг ВКЛ\nРиск: 2.0%\nБаланс: 0 USDT")

async def auto_command_handler(update: Update, context: CallbackContext):
    try:
        result = await auto_command()
        await send_reply(update, context, result)
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка авто-команды: {e}")

async def report_command(update: Update, context: CallbackContext):
    try:
        report = get_portfolio_status()
        await send_reply(update, context, report)
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка отчета: {e}")

async def logs_command(update: Update, context: CallbackContext):
    try:
        zip_path = "logs_archive.zip"
        shutil.make_archive("logs_archive", 'zip', "logs")
        await update.message.reply_document(open(zip_path, "rb"))
        os.remove(zip_path)
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка при подготовке логов: {e}")

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
    app.add_handler(CommandHandler("logs", logs_command))

    return app
