import logging 
import time
import shutil
import os
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext, Application
from config import TELEGRAM_TOKEN, binance
from core.portfolio import get_portfolio_status
from core.strategy import analyze_market_smart
from core.order_manager import futures_manager
from utils.safe_send import safe_send_message

# Импортируем флаг автотрейдинга, risk_manager и адаптивный оптимизатор
from core import auto_trader
from core.risk_manager import risk_manager
from core.adaptive_optimizer import parameters_report
from core.history_analyzer import history_report_text
from core import risk_modes  # Импортируем risk_modes

logger = logging.getLogger(__name__)

# ====== Кэш для команды /analyze ======
last_analyze_time = 0
last_analyze_result = "❌ Данные анализа еще не получены."
ANALYZE_CACHE_TIME = 60  # 1 минута

# ====== Универсальный метод отправки ======
async def send_reply(update: Update, context: CallbackContext, text: str):
    """Отправка ответа в чат с безопасной обработкой ошибок."""
    try:
        logger.debug(f"COMMAND | {update.message.text}")
        await safe_send_message(context.bot, update.effective_chat.id, text)
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")


# ====== Команды бота ======
async def start_command(update: Update, context: CallbackContext):
    await send_reply(update, context, "🤖 Привет! Я торговый бот. Используй /help для списка команд.")


async def help_command(update: Update, context: CallbackContext):
    modes_info = "\n".join(
        [f"- {m}: {d['description']} (TP={d['trade_percent']*100:.1f}%, MaxPos={d['max_positions']})"
         for m, d in risk_modes.RISK_MODES.items()]
    )
    commands = (
        "/start - Запуск бота\n"
        "/help - Справка\n"
        "/balance - Проверить баланс\n"
        "/price <symbol> [quote] - Цена монеты\n"
        "/analyze - Умный анализ рынка\n"
        "/status - Проверка автотрейда\n"
        "/auto - Включить/выключить автотрейд\n"
        "/positions - Активные позиции\n"
        "/report - Отчет по портфелю\n"
        "/params - Текущие параметры стратегии\n"
        "/analytics - Статистика winrate и PnL\n"
        "/signals - Последние торговые сигналы\n"
        "/mode - Переключение авто/ручного режима риска\n"
        "/mode_safe - Установить защитный режим (SAFE)\n"
        "/mode_normal - Установить стандартный режим (NORMAL)\n"
        "/mode_aggressive - Установить агрессивный режим (AGGRESSIVE)\n"
        "/logs - Скачать все логи\n\n"
        "Доступные режимы риска:\n"
        f"{modes_info}"
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
    try:
        status = "ВКЛ" if auto_trader.AUTO_TRADING_ENABLED else "ВЫКЛ"
        balance = binance.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        positions_count = len(futures_manager.active_positions)
        risk_status = risk_modes.get_risk_mode()

        try:
            volatile, reason = risk_manager.is_market_volatile("BTC/USDT")
            vol_status = "ВЫСОКАЯ" if volatile else "Нормальная"
            vol_text = f"\nВолатильность: {vol_status}"
            if volatile and reason:
                vol_text += f" ({reason})"
        except Exception as e:
            logger.error(f"Ошибка проверки волатильности: {e}")
            vol_text = "\nВолатильность: ошибка проверки"

        text = (
            f"🔴 Автотрейдинг {status}\n"
            f"{risk_status}\n"
            f"Баланс: {usdt_balance:.2f} USDT\n"
            f"Активных позиций: {positions_count}"
            f"{vol_text}"
        )
        await send_reply(update, context, text)
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка получения статуса: {e}")


async def auto_command_handler(update: Update, context: CallbackContext):
    auto_trader.AUTO_TRADING_ENABLED = not auto_trader.AUTO_TRADING_ENABLED
    status = "включен" if auto_trader.AUTO_TRADING_ENABLED else "выключен"
    await send_reply(update, context, f"Автотрейдинг {status}.")


async def positions_command(update: Update, context: CallbackContext):
    if futures_manager.active_positions:
        text = f"📌 Активные позиции ({len(futures_manager.active_positions)}):\n"
        for pid, pos in futures_manager.active_positions.items():
            text += (
                f"- {pos['symbol']} | {pos['side']} | "
                f"Цена входа: {pos['entry_price']} | "
                f"Кол-во: {pos['amount']}\n"
            )
    else:
        text = "Нет активных позиций."
    await send_reply(update, context, text)


async def report_command(update: Update, context: CallbackContext):
    try:
        report_text = get_portfolio_status()
        await send_reply(update, context, report_text)
        logger.info(f"[REPORT] Отчёт отправлен: {report_text}")
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка отчета: {e}")


async def params_command(update: Update, context: CallbackContext):
    try:
        text = parameters_report()
        await send_reply(update, context, text)
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка получения параметров: {e}")


async def analytics_command(update: Update, context: CallbackContext):
    try:
        text = history_report_text()
        await send_reply(update, context, text)
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка получения аналитики: {e}")


async def signals_command(update: Update, context: CallbackContext):
    try:
        log_file = os.path.join("logs", "signals_history.log")
        if not os.path.exists(log_file):
            await send_reply(update, context, "⚠ История сигналов пуста.")
            return
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()[-10:]
        text = "📜 Последние сигналы:\n" + "".join(lines)
        await send_reply(update, context, text)
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка чтения сигналов: {e}")


# === Команды управления режимами риска ===
async def mode_command(update: Update, context: CallbackContext):
    text = risk_modes.toggle_auto_mode()
    await send_reply(update, context, text)


async def mode_safe_command(update: Update, context: CallbackContext):
    success, msg = risk_modes.set_risk_mode("SAFE")
    await send_reply(update, context, msg)


async def mode_normal_command(update: Update, context: CallbackContext):
    success, msg = risk_modes.set_risk_mode("NORMAL")
    await send_reply(update, context, msg)


async def mode_aggressive_command(update: Update, context: CallbackContext):
    success, msg = risk_modes.set_risk_mode("AGGRESSIVE")
    await send_reply(update, context, msg)


async def logs_command(update: Update, context: CallbackContext):
    try:
        zip_path = "logs_archive.zip"
        shutil.make_archive("logs_archive", 'zip', "logs")
        await update.message.reply_document(open(zip_path, "rb"))
        os.remove(zip_path)
    except Exception as e:
        await send_reply(update, context, f"⚠ Ошибка при подготовке логов: {e}")


def setup_telegram_bot():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("auto", auto_command_handler))
    app.add_handler(CommandHandler("positions", positions_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("params", params_command))
    app.add_handler(CommandHandler("analytics", analytics_command))
    app.add_handler(CommandHandler("signals", signals_command))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("mode_safe", mode_safe_command))
    app.add_handler(CommandHandler("mode_normal", mode_normal_command))
    app.add_handler(CommandHandler("mode_aggressive", mode_aggressive_command))
    app.add_handler(CommandHandler("logs", logs_command))
    return app
