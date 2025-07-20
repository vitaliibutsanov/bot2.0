
import ccxt
import os
import logging
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, time as dtime
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from dotenv import load_dotenv
import ta
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

# ===== КОНФИГ =====
class TradingConfig:
    RISK_PER_TRADE = 0.02       # Риск на сделку (2%)
    MAX_TRADES_PER_DAY = 40     # Лимит сделок в день
    STOP_LOSS = 0.05            # Стоп-лосс (5%)
    TAKE_PROFIT = 0.10          # Тейк-профит (10%)
    TRADING_ENABLED = False     # Флаг торговли
    AUTO_TRADING = False        # Режим автоторговли
    LOSE_STREAK = 0             # Счётчик убыточных сделок
    PAUSE_UNTIL = None          # Пауза
config = TradingConfig()

# ===== ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ =====
class VirtualPortfolio:
    def __init__(self, initial_balance=1000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.history = []  # [(datetime, pnl_value)]

    def apply_trade(self, pnl_usdt):
        self.balance += pnl_usdt
        self.history.append((datetime.now(), pnl_usdt))
        logging.info(f"VIRTUAL_PNL | {pnl_usdt:.2f} USDT | Balance={self.balance:.2f} USDT")

    def calculate_report(self, days: int):
        cutoff = datetime.now() - timedelta(days=days)
        pnl_sum = sum(p for (t, p) in self.history if t >= cutoff)
        percent = (pnl_sum / self.initial_balance) * 100
        return pnl_sum, percent

    def full_report(self):
        d, dp = self.calculate_report(1)
        w, wp = self.calculate_report(7)
        m, mp = self.calculate_report(30)
        return (
            f"📊 Отчёт по виртуальному портфелю:\n"
            f"Баланс: {self.balance:.2f} USDT\n"
            f"24ч: {d:.2f} USDT ({dp:.2f}%)\n"
            f"7д: {w:.2f} USDT ({wp:.2f}%)\n"
            f"30д: {m:.2f} USDT ({mp:.2f}%)"
        )
virtual_portfolio = VirtualPortfolio(1000)

# ===== ЗАГРУЗКА API КЛЮЧЕЙ =====
load_dotenv()
binance = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'options': {'adjustForTimeDifference': True}
})
binance.set_sandbox_mode(True)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID'))

def get_binance_balance():
    try:
        balance = binance.fetch_balance()
        return {
            'USDT': round(balance.get('USDT', {}).get('free', 0), 2),
            'BTC': round(balance.get('BTC', {}).get('free', 0), 6),
            'ETH': round(balance.get('ETH', {}).get('free', 0), 6),
        }
    except Exception as e:
        logging.error(f"BALANCE_ERROR: {e}")
        return {'USDT': 0, 'BTC': 0, 'ETH': 0}

# ===== ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ =====
def get_technical_indicators(symbol: str, timeframe='1h', limit=100):
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe='1m', limit=50)
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        if len(closes) < 20:
            raise ValueError("Недостаточно данных для индикаторов.")

        rsi = ta.momentum.rsi(pd.Series(closes), window=14).iloc[-1]
        bb = BollingerBands(pd.Series(closes), window=20, window_dev=2)
        bb_high, bb_low = bb.bollinger_hband().iloc[-1], bb.bollinger_lband().iloc[-1]

        return closes[-1], round(rsi, 2), round(bb_high, 2), round(bb_low, 2), round(volumes[-1], 3)
    except Exception as e:
        logging.error(f"TECHNICAL_INDICATORS_ERROR: {e}")
        return None, None, None, None, None

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
                if pos['take_profit'] and ((side == 'BUY' and price >= pos['take_profit']) or (side == 'SELL' and price <= pos['take_profit'])):
                    await self.close_position(pid)
                    closed_positions.append(f"TP сработал: {pos['symbol']} @ {price:.2f}")
                    continue
                if pos['stop_loss'] and ((side == 'BUY' and price <= pos['stop_loss']) or (side == 'SELL' and price >= pos['stop_loss'])):
                    await self.close_position(pid)
                    self.loss_streak += 1
                    if self.loss_streak >= self.max_loss_streak:
                        self.cooldown_until = datetime.now() + timedelta(hours=6)
                        logging.warning("PAUSE | 3 убытка подряд. Пауза 6 часов.")
                    closed_positions.append(f"SL сработал: {pos['symbol']} @ {price:.2f}")
            except Exception as e:
                logging.error(f"CHECK_POSITION_ERROR | {pid} | {str(e)}")
        return closed_positions

futures_manager = FuturesManager()
# ===== АНАЛИЗ РЫНКА =====
def analyze_market_smart(symbol='BTC/USDT', timeframe='1h', limit=100):
    """Расширенный анализ: RSI, Bollinger, EMA, ATR, стакан."""
    try:
        price, rsi, bb_upper, bb_lower, volume = get_technical_indicators(symbol)
        if price is None:
            return "❌ Не удалось получить индикаторы."

        # EMA (20)
        closes = [c[4] for c in binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=50)]
        ema = EMAIndicator(pd.Series(closes), window=20).ema_indicator().iloc[-1]

        # ATR (14)
        df = pd.DataFrame(binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=20),
                          columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range().iloc[-1]

        # Позиция цены
        price_position = "🔹 Цена между уровнями"
        if price <= bb_lower:
            price_position = "🟢 Цена у нижней границы BB"
        elif price >= bb_upper:
            price_position = "🔴 Цена у верхней границы BB"

        # Стакан
        orderbook = binance.fetch_order_book(symbol, limit=10)
        bid_volume = sum([b[1] for b in orderbook['bids'][:3]])
        ask_volume = sum([a[1] for a in orderbook['asks'][:3]])
        imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1)

        # Сигнал
        confidence = 0
        if rsi < 35: confidence += 1
        if price <= bb_lower: confidence += 1
        if imbalance > 0.2: confidence += 1
        if price > ema: confidence += 1
        if atr > 0: confidence += 1

        signal = "❕ Нет условий для входа"
        if confidence >= 4 and rsi < 35:
            signal = "📈 СИГНАЛ: ПОКУПАТЬ"
        elif confidence >= 4 and rsi > 65:
            signal = "📉 СИГНАЛ: ПРОДАВАТЬ"

        logging.info(
            f"ANALYZE_SMART | {symbol} | Price={price:.2f} | RSI={rsi:.2f} | BB=({bb_lower:.2f}/{bb_upper:.2f}) | "
            f"EMA={ema:.2f} | ATR={atr:.2f} | Bid={bid_volume:.2f} Ask={ask_volume:.2f} | Conf={confidence} | {signal}"
        )

        return (
            f"{signal}\n{price_position}\n"
            f"📉 RSI: {rsi:.2f}\n"
            f"📏 EMA: {ema:.2f}\n"
            f"⚡ ATR: {atr:.2f}\n"
            f"📊 Объём: {volume:.2f}\n"
            f"🌟 Доверие: {confidence}/5"
        )
    except Exception as e:
        logging.error(f"ANALYZE_SMART_ERROR: {e}")
        return f"❌ Ошибка анализа: {e}"


# ====== TELEGRAM КОМАНДЫ ======
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("🤖 Бот запущен!\nНапишите /help для списка команд.")

async def check_balance(update: Update, context: CallbackContext):
    balance = get_binance_balance()
    await update.message.reply_text(
        f"💰 Баланс:\nUSDT: {balance['USDT']}\nBTC: {balance['BTC']}\nETH: {balance['ETH']}"
    )

async def price(update: Update, context: CallbackContext):
    coin = context.args[0].upper() if context.args else 'BTC'
    ticker = binance.fetch_ticker(f"{coin}/USDT")
    await update.message.reply_text(f"📊 {coin}: {ticker['last']:.2f} USDT")

async def report(update: Update, context: CallbackContext):
    await update.message.reply_text(virtual_portfolio.full_report())

async def trading_status(update: Update, context: CallbackContext):
    balance = get_binance_balance()
    auto_mode = "🟢 Автотрейдинг ВКЛ" if config.AUTO_TRADING else "🔴 Автотрейдинг ВЫКЛ"
    await update.message.reply_text(
        f"{auto_mode}\nРиск: {config.RISK_PER_TRADE * 100:.1f}%\nБаланс: {balance['USDT']:.2f} USDT"
    )

async def toggle_auto(update: Update, context: CallbackContext):
    config.AUTO_TRADING = not config.AUTO_TRADING
    if config.AUTO_TRADING:
        await update.message.reply_text("▶ Автотрейдинг запущен.")
        asyncio.create_task(auto_trade_cycle())
    else:
        await update.message.reply_text("⏹ Автотрейдинг остановлен.")

async def show_help(update: Update, context: CallbackContext):
    cmds = [
        "/start — Запуск бота",
        "/balance — Баланс",
        "/price <COIN> — Курс",
        "/analyze — Анализ рынка",
        "/status — Статус торговли",
        "/auto — Автоторговля Вкл/Выкл",
        "/report — Отчёт",
        "/help — Команды"
    ]
    await update.message.reply_text("📖 Доступные команды:\n" + "\n".join(cmds))


# ====== АВТОТРЕЙДИНГ ======
async def auto_trade_cycle():
    symbol = "BTC/USDT"
    position_opened = False
    entry_price = 0
    entry_amount = 0

    while config.AUTO_TRADING:
        try:
            signal = analyze_market_smart(symbol)
            price = binance.fetch_ticker(symbol)['last']
            balance = get_binance_balance()
            amount = round((balance['USDT'] * config.RISK_PER_TRADE) / price, 6)

            if "ПОКУПАТЬ" in signal and not position_opened:
                success, order = await futures_manager.open_position(
                    symbol, "BUY", amount, leverage=5,
                    stop_loss=price * (1 - config.STOP_LOSS),
                    take_profit=price * (1 + config.TAKE_PROFIT)
                )
                if success:
                    position_opened = True
                    entry_price = price
                    entry_amount = amount
                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text=(f"📈 LONG {symbol}\nЦена: {price:.2f} USDT\nОбъём: {amount} BTC")
                    )

            elif "ПРОДАВАТЬ" in signal and position_opened:
                pid = next(iter(futures_manager.active_positions))
                success, result = await futures_manager.close_position(pid)
                if success:
                    position_opened = False
                    exit_price = binance.fetch_ticker(symbol)['last']
                    pnl_usdt = (exit_price - entry_price) * entry_amount
                    virtual_portfolio.apply_trade(pnl_usdt)
                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text=(f"{'✅' if pnl_usdt >= 0 else '❌'} Сделка закрыта:\n"
                              f"{symbol}\nPnL: {pnl_usdt:.2f} USDT\n"
                              f"Баланс: {virtual_portfolio.balance:.2f} USDT")
                    )

        except Exception as e:
            logging.error(f"AUTO_TRADE_ERROR: {e}")
        await asyncio.sleep(60)


# ===== ЕЖЕДНЕВНЫЙ ОТЧЕТ =====
async def daily_report(context: CallbackContext):
    await context.bot.send_message(chat_id=CHAT_ID, text=virtual_portfolio.full_report())


# ====== MAIN ======
def main():
    global app
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", check_balance))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("analyze", lambda u, c: u.message.reply_text(analyze_market_smart())))
    app.add_handler(CommandHandler("status", trading_status))
    app.add_handler(CommandHandler("auto", toggle_auto))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("help", show_help))

    app.job_queue.run_daily(daily_report, time=dtime(hour=20, minute=0))
    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
