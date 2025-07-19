import ccxt
import os
import time
import logging
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes
from dotenv import load_dotenv
import ta
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(
    filename='trades.log',
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

COMMANDS = []

def register_command(app, command, handler, description=""):
    app.add_handler(CommandHandler(command, handler))
    COMMANDS.append((command, description))

# ===== КОНФИГ =====
class TradingConfig:
    RISK_PER_TRADE = 0.02
    MAX_TRADES_PER_DAY = 5
    STOP_LOSS = 0.05
    TAKE_PROFIT = 0.10
    TRADING_ENABLED = False
    AUTO_TRADING = False
    LOSE_STREAK = 0
    PAUSE_UNTIL = None

config = TradingConfig()

# ===== ЗАГРУЗКА API КЛЮЧЕЙ =====
load_dotenv()
binance = ccxt.binanceusdm({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'options': {'adjustForTimeDifference': True}
})

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID'))

# ===== БАЛАНС =====
def get_binance_balance():
    try:
        balance = binance.fetch_balance()
        return {
            'USDT': balance['total']['USDT'],
            'BTC': balance['total']['BTC'],
            'ETH': balance['total']['ETH']
        }
    except Exception as e:
        logging.error(f"BALANCE_ERROR: {e}")
        return {'USDT': 0, 'BTC': 0, 'ETH': 0}

# ===== ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ =====
def get_technical_indicators(symbol='BTC/USDT', timeframe='1h', limit=100):
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        indicators = {
            'price': df['close'].iloc[-1],
            'rsi': RSIIndicator(df['close'], window=14).rsi().iloc[-1],
            'volume': df['volume'].iloc[-1]
        }

        bb = BollingerBands(df['close'], window=20)
        indicators['bb_upper'] = bb.bollinger_hband().iloc[-1]
        indicators['bb_lower'] = bb.bollinger_lband().iloc[-1]
        indicators['ema'] = EMAIndicator(df['close'], window=20).ema_indicator().iloc[-1]
        indicators['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range().iloc[-1]

        return indicators
    except Exception as e:
        logging.error(f"TECH_INDICATOR_ERROR | {symbol} | {str(e)}")
        return None

# ===== ГРАФИК =====
def plot_indicators(symbol='BTC/USDT', timeframe='1h', limit=100):
    try:
        data = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])

        plt.figure(figsize=(12, 6))
        plt.plot(df['close'], label='Price', color='blue')

        bb = BollingerBands(df['close'], window=20)
        plt.plot(bb.bollinger_hband(), label='Upper Band', linestyle='--', color='red')
        plt.plot(bb.bollinger_lband(), label='Lower Band', linestyle='--', color='green')

        plt.title(f"Symbol: {symbol} Price change")
        plt.legend()
        plt.grid(True)
        plt.savefig('chart.png', bbox_inches='tight', dpi=100)
        plt.close()
        return open('chart.png', 'rb')
    except Exception as e:
        logging.error(f"CHART_ERROR | {symbol} | {str(e)}")
        return None

# ===== АНАЛИЗ РЫНКА =====
def analyze_market_smart(symbol='BTC/USDT', timeframe='1h', limit=100):
    """Расширенный анализ рынка: RSI, Bollinger, EMA, ATR, стакан."""
    indicators = get_technical_indicators(symbol, timeframe, limit)
    if not indicators:
        return "❌ Не удалось получить индикаторы."

    price = indicators['price']
    rsi = indicators['rsi']
    bb_upper = indicators['bb_upper']
    bb_lower = indicators['bb_lower']
    ema = indicators['ema']
    atr = indicators['atr']
    volume = indicators['volume']

    # Позиция цены
    price_position = "🔹 Цена между уровнями"
    if price <= bb_lower:
        price_position = "🟢 Цена у нижней границы BB"
    elif price >= bb_upper:
        price_position = "🔴 Цена у верхней границы BB"

    # Получение стакана
    try:
        orderbook = binance.fetch_order_book(symbol, limit=10)
        bids = orderbook['bids']
        asks = orderbook['asks']
        bid_volume = sum([b[1] for b in bids[:3]])
        ask_volume = sum([a[1] for a in asks[:3]])
    except Exception as e:
        logging.error(f"ORDERBOOK_ERROR | {symbol} | {str(e)}")
        return "❌ Ошибка при получении стакана."

    imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1)

    # Оценка доверия
    confidence = 0
    if rsi < 35: confidence += 1
    if price <= bb_lower: confidence += 1
    if imbalance > 0.2: confidence += 1
    if volume > 0: confidence += 1
    if price > ema: confidence += 1
    if atr > 0: confidence += 1

    signal = "❕ Нет условий для входа"
    if confidence >= 4 and rsi < 35:
        signal = "📈 СИГНАЛ: ПОКУПАТЬ"
    elif confidence >= 4 and rsi > 65:
        signal = "📉 СИГНАЛ: ПРОДАВАТЬ"

    log_msg = (
        f"ANALYZE_SMART | {symbol} | Price={price:.2f} | RSI={rsi:.2f} | "
        f"BB=({bb_lower:.2f}/{bb_upper:.2f}) | EMA={ema:.2f} | ATR={atr:.2f} | "
        f"Bid={bid_volume:.2f} Ask={ask_volume:.2f} | Imb={imbalance:.2f} | Conf={confidence} | {signal}"
    )
    logging.info(log_msg)

    return (
        f"{signal}\n{price_position}\n"
        f"📉 RSI: {rsi:.2f}\n"
        f"📏 EMA: {ema:.2f}\n"
        f"⚡ ATR: {atr:.2f}\n"
        f"📊 Объём: {volume:.2f}\n"
        f"🌟 Доверие: {confidence}/6"
    )

# ===== УПРАВЛЕНИЕ ФЬЮЧЕРСАМИ =====
class FuturesManager:
    def __init__(self):
        self.active_positions = {}
        self.loss_streak = 0
        self.max_loss_streak = 3
        self.cooldown_until = None

    def is_paused(self):
        return self.cooldown_until and datetime.now() < self.cooldown_until

    async def open_position(self, symbol, side, amount, leverage=5, stop_loss=None, take_profit=None):
        if self.is_paused():
            return False, f"Торговля на паузе до {self.cooldown_until.strftime('%H:%M:%S')}."
        try:
            binance.set_leverage(leverage, symbol)
            order = binance.create_order(symbol=symbol, type='MARKET', side=side, amount=amount)
            entry_price = order.get('price', binance.fetch_ticker(symbol)['last'])
            self.active_positions[order['id']] = {
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'opened_at': datetime.now()
            }
            logging.info(f"FUTURES_OPEN | {symbol} | {side} | {amount} @ {entry_price}")
            return True, order
        except Exception as e:
            logging.error(f"FUTURES_ERROR | {symbol} | {str(e)}")
            return False, str(e)

    async def close_position(self, position_id):
        try:
            pos = self.active_positions.get(position_id)
            if not pos:
                return False, "Позиция не найдена."
            side = 'SELL' if pos['side'] == 'BUY' else 'BUY'
            binance.create_order(symbol=pos['symbol'], type='MARKET', side=side, amount=pos['amount'])
            logging.info(f"FUTURES_CLOSE | {pos['symbol']} | {pos['side']} | {pos['amount']}")
            del self.active_positions[position_id]
            return True, "Позиция закрыта."
        except Exception as e:
            return False, str(e)

    async def check_positions(self):
        closed_positions = []
        for pid, pos in list(self.active_positions.items()):
            try:
                ticker = binance.fetch_ticker(pos['symbol'])
                price = ticker['last']
                side = pos['side']

                # Проверка TP
                if pos['take_profit'] and ((side == 'BUY' and price >= pos['take_profit']) or (side == 'SELL' and price <= pos['take_profit'])):
                    await self.close_position(pid)
                    closed_positions.append(f"TP сработал: {pos['symbol']} @ {price:.2f}")
                    continue

                # Проверка SL
                if pos['stop_loss'] and ((side == 'BUY' and price <= pos['stop_loss']) or (side == 'SELL' and price >= pos['stop_loss'])):
                    await self.close_position(pid)
                    self.loss_streak += 1
                    if self.loss_streak >= self.max_loss_streak:
                        self.cooldown_until = datetime.now() + timedelta(hours=6)
                        logging.warning("PAUSE | 3 убытка подряд. Пауза 6 часов.")
                    closed_positions.append(f"SL сработал: {pos['symbol']} @ {price:.2f}")
                    continue
            except Exception as e:
                logging.error(f"CHECK_POSITION_ERROR | {pid} | {str(e)}")
        return closed_positions

# ===== УПРАВЛЕНИЕ СПОТОМ =====
class PositionManager:
    def __init__(self):
        self.active_positions = {}

    async def open_position(self, symbol, amount, stop_loss=None, take_profit=None):
        if not config.TRADING_ENABLED:
            return False, "Торговля отключена"
        if len(self.active_positions) >= config.MAX_TRADES_PER_DAY:
            return False, "Достигнут лимит сделок"
        try:
            balance = binance.fetch_balance()['USDT']['free']
            position_size = min(amount, balance * config.RISK_PER_TRADE)
            order = binance.create_order(symbol=symbol, type='MARKET', side='buy', amount=position_size)
            self.active_positions[order['id']] = {
                'symbol': symbol,
                'amount': position_size,
                'entry_price': order['price'],
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'opened_at': datetime.now()
            }
            logging.info(f"OPEN_POSITION | {symbol} | {position_size}")
            return True, order
        except Exception as e:
            logging.error(f"POSITION_ERROR | {symbol} | {str(e)}")
            return False, str(e)

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======
def positions_summary():
    if not position_manager.active_positions:
        return "Нет открытых позиций"
    summary = []
    for pid, pos in position_manager.active_positions.items():
        summary.append(f"{pos['symbol']}: {pos['amount']:.6f} @ {pos['entry_price']:.2f}")
    return "\n".join(summary)

def is_binance_alive():
    try:
        binance.fetch_time()
        return True
    except Exception:
        return False

position_manager = PositionManager()
futures_manager = FuturesManager()

# ====== TELEGRAM КОМАНДЫ ======
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("🤖 Бот запущен!\nНапишите /help для списка команд.")

async def check_balance(update: Update, context: CallbackContext):
    try:
        balance = get_binance_balance()
        text = (f"💰 Баланс:\n"
                f"USDT: {balance['USDT']:.2f}\n"
                f"BTC: {balance['BTC']:.6f}\n"
                f"ETH: {balance['ETH']:.6f}")
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def price(update: Update, context: CallbackContext):
    try:
        coin = context.args[0].upper() if context.args else 'BTC'
        ticker = binance.fetch_ticker(f"{coin}/USDT")
        await update.message.reply_text(f"📊 {coin}: {ticker['last']:.2f} USDT")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def analyze(update: Update, context: CallbackContext):
    try:
        symbol = context.args[0].upper() + "/USDT" if context.args else "BTC/USDT"
        result = analyze_market_smart(symbol)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def trading_status(update: Update, context: CallbackContext):
    status = "🟢 АКТИВЕН" if config.TRADING_ENABLED else "🔴 ВЫКЛЮЧЕН"
    await update.message.reply_text(
        f"Статус: {status}\n"
        f"Риск: {config.RISK_PER_TRADE * 100:.1f}%\n"
        f"Сделки: {len(position_manager.active_positions)}/{config.MAX_TRADES_PER_DAY}"
    )

async def trading_status_full(update: Update, context: CallbackContext):
    balance = get_binance_balance()
    api_status = "🟢 Binance API" if is_binance_alive() else "🔴 Нет связи"
    msg = (
        f"{api_status}\n"
        f"Риск: {config.RISK_PER_TRADE*100:.1f}%\n"
        f"Баланс: {balance['USDT']:.2f} USDT\n"
        f"Позиции:\n{positions_summary()}"
    )
    await update.message.reply_text(msg)

async def set_risk(update: Update, context: CallbackContext):
    try:
        value = float(context.args[0]) / 100
        if 0.001 <= value <= 0.1:
            config.RISK_PER_TRADE = value
            await update.message.reply_text(f"Риск установлен: {value*100:.1f}%")
        else:
            await update.message.reply_text("❌ Риск должен быть 0.1% - 10%")
    except Exception:
        await update.message.reply_text("Используй: /risk 2.5 (для 2.5%)")

async def pause_trading(update: Update, context: CallbackContext):
    config.TRADING_ENABLED = False
    await update.message.reply_text("⏸ Торговля приостановлена.")

async def resume_trading(update: Update, context: CallbackContext):
    config.TRADING_ENABLED = True
    await update.message.reply_text("🟢 Торговля возобновлена.")

async def toggle_auto(update: Update, context: CallbackContext):
    config.AUTO_TRADING = not config.AUTO_TRADING
    state = "🟢 Авто-режим ВКЛ" if config.AUTO_TRADING else "🔴 Авто-режим ВЫКЛ"
    await update.message.reply_text(state)

async def show_help(update: Update, context: CallbackContext):
    cmds = [
        "/start — Запустить бота",
        "/balance — Баланс",
        "/price <COIN> — Курс монеты",
        "/analyze — Анализ сигнала",
        "/status — Краткий статус",
        "/trading_status — Расширенный статус",
        "/risk <X> — Установить риск (%)",
        "/pause — Пауза торговли",
        "/resume — Возобновить",
        "/auto — Автоторговля Вкл/Выкл",
        "/help — Показать команды"
    ]
    await update.message.reply_text("📖 Доступные команды:\n" + "\n".join(cmds))

# ====== ФОНОВЫЕ ЗАДАЧИ ======
async def signal_checker():
    while True:
        try:
            if config.TRADING_ENABLED and config.AUTO_TRADING:
                signal = analyze_market_smart()
                if "СИГНАЛ:" in signal:
                    await app.bot.send_message(chat_id=CHAT_ID, text=f"📡 Сигнал:\n{signal}")
        except Exception as e:
            logging.error(f"signal_checker: {e}")
        await asyncio.sleep(60)

async def positions_watcher():
    while True:
        try:
            closed = await futures_manager.check_positions()
            for msg in closed:
                await app.bot.send_message(chat_id=CHAT_ID, text=f"🔔 {msg}")
        except Exception as e:
            logging.error(f"positions_watcher: {e}")
        await asyncio.sleep(60)

# ====== MAIN ======
def main():
    global app
    print(">>> MAIN START")
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("balance", check_balance))
        app.add_handler(CommandHandler("price", price))
        app.add_handler(CommandHandler("analyze", analyze))
        app.add_handler(CommandHandler("status", trading_status))
        app.add_handler(CommandHandler("trading_status", trading_status_full))
        app.add_handler(CommandHandler("risk", set_risk))
        app.add_handler(CommandHandler("pause", pause_trading))
        app.add_handler(CommandHandler("resume", resume_trading))
        app.add_handler(CommandHandler("auto", toggle_auto))
        app.add_handler(CommandHandler("help", show_help))

        app.job_queue.run_repeating(lambda _: asyncio.create_task(signal_checker()), interval=60)
        app.job_queue.run_repeating(lambda _: asyncio.create_task(positions_watcher()), interval=60)

        print("Бот запущен...")
        app.run_polling()
    except Exception as e:
        logging.error(f"MAIN_ERROR: {e}", exc_info=True)
        print(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    main()
