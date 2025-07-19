import ccxt  # Исправлено ctxt на ccxt
import os
import time
import logging
import asyncio
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt  # Перенесено в основной блок импортов
from ta import momentum
import ta
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes
from dotenv import load_dotenv
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

# Настройка логирования торговых операций
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

class TradingConfig:
    """Настройки торговли"""
    RISK_PER_TRADE = 0.02  # 2% от депозита
    MAX_TRADES_PER_DAY = 5
    STOP_LOSS = 0.05  # 5%
    TAKE_PROFIT = 0.10  # 10%
    TRADING_ENABLED = False  # Флаг для ручного управления
    AUTO_TRADING = False  # Автоматическая торговля по сигналу
    LOSE_STREAK = 0           # Кол-во подряд убыточных сделок
    PAUSE_UNTIL = None        # Время окончания паузы

config = TradingConfig()

# Загрузка ключей из .env
load_dotenv()

# Инициализация Binance
binance = ccxt.binanceusdm({
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

def get_technical_indicators(symbol='BTC/USDT', timeframe='1h', limit=100):
    """Получение технических индикаторов (RSI, Bollinger Bands)"""
    try:
        # Получаем данные свечей
        ohlcv = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # Рассчитываем индикаторы
        rsi = RSIIndicator(df['close'], window=14).rsi().iloc[-1]
        bb = BollingerBands(df['close'], window=20)

        return {
            'rsi': round(rsi, 2),
            'bb_upper': round(bb.bollinger_hband().iloc[-1], 2),
            'bb_lower': round(bb.bollinger_lband().iloc[-1], 2),
            'price': df['close'].iloc[-1],
            'volume': df['volume'].iloc[-1]
        }

    except Exception as e:
        logging.error(f"TECH_INDICATOR_ERROR | {symbol} | {str(e)}")
        return None

def analyze_market(symbol='BTC/USDT', timeframe='1h', limit=100):
    """Продвинутая стратегия: RSI + стакан + объёмы + BollingerBands"""
    indicators = get_technical_indicators(symbol, timeframe, limit)
    if not indicators:
        return "❌ Не удалось получить индикаторы."

    price = indicators['price']
    rsi = indicators['rsi']
    bb_upper = indicators['bb_upper']
    bb_lower = indicators['bb_lower']
    volume = indicators['volume']

    try:
        orderbook = binance.fetch_order_book(symbol, limit=10)
        bids = orderbook['bids']
        asks = orderbook['asks']
        bid_volume = sum([b[1] for b in bids[:3]])  # ближние 3 уровня
        ask_volume = sum([a[1] for a in asks[:3]])
        total_bid = sum([b[1] for b in bids])
        total_ask = sum([a[1] for a in asks])
    except Exception as e:
        logging.error(f"ORDERBOOK_ERROR | {symbol} | {str(e)}")
        return "❌ Ошибка при получении стакана."

    imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1)
    position = "🔹 Цена между уровнями"
    if price <= bb_lower:
        position = "🟢 Цена у нижней границы BB"
    elif price >= bb_upper:
        position = "🔴 Цена у верхней границы BB"

    signal = "🤔 Сигнал не определён"

    if rsi < 35 and imbalance > 0.2 and price <= bb_lower and volume > 0:
        signal = "📈 СИГНАЛ: ПОКУПАТЬ (RSI < 35, спрос, BB нижняя)"
    elif rsi > 65 and imbalance < -0.2 and price >= bb_upper and volume > 0:
        signal = "📉 СИГНАЛ: ПРОДАВАТЬ (RSI > 65, предложение, BB верхняя)"
    else:
        signal = "⏸ Нет условий для входа — жду сигнала"

    log_msg = (
        f"ANALYZE | {symbol} | Price={price:.2f} | RSI={rsi} | "
        f"BB=({bb_lower:.2f}/{bb_upper:.2f}) | Pos={position} | "
        f"Bid={bid_volume:.2f} Ask={ask_volume:.2f} | Imb={imbalance:.2f} | {signal}"
    )
    logging.info(log_msg)

    return f"{signal}\n{position}\nRSI: {rsi:.2f}\nОбъём: {volume:.2f}"

def plot_indicators(symbol='BTC/USDT', timeframe='1h', limit=100):
    """Генерация графика цен с индикаторами"""
    try:
        data = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])

        plt.figure(figsize=(12, 6))
        plt.plot(df['close'], label='Price', color='blue')

        # Добавляем Bollinger Bands
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
    
class FuturesManager:
    """Класс для работы с фьючерсами с TP/SL и защитой от серии убытков"""
    def __init__(self):
        self.active_positions = {}  # Открытые позиции
        self.loss_streak = 0        # Кол-во убыточных подряд
        self.max_loss_streak = 3    # Сколько минусов подряд до паузы
        self.cooldown_until = None  # Время окончания паузы (если активна)

    def is_paused(self):
        """Проверка, активна ли пауза"""
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return True
        return False

    async def open_position(self, symbol, side, amount, leverage=5, stop_loss=None, take_profit=None):
        """Открыть позицию на фьючерсах"""
        if self.is_paused():
            return False, f"Торговля приостановлена до {self.cooldown_until.strftime('%H:%M:%S')}."

        try:
            binance.set_leverage(leverage, symbol)
            order = binance.create_order(
                symbol=symbol,
                type='MARKET',
                side=side,
                amount=amount
            )

            entry_price = order['price'] if 'price' in order else binance.fetch_ticker(symbol)['last']
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

    async def check_positions(self):
        """Проверка TP/SL для активных позиций"""
        closed_positions = []
        for pid, pos in list(self.active_positions.items()):
            try:
                ticker = binance.fetch_ticker(pos['symbol'])
                price = ticker['last']
                side = pos['side']

                if pos['take_profit'] and ((side == 'BUY' and price >= pos['take_profit']) or (side == 'SELL' and price <= pos['take_profit'])):
                    await self.close_position(pid)
                    closed_positions.append(f"TP сработал по {pos['symbol']} @ {price:.2f}")
                    continue

                if pos['stop_loss'] and ((side == 'BUY' and price <= pos['stop_loss']) or (side == 'SELL' and price >= pos['stop_loss'])):
                    await self.close_position(pid)
                    self.loss_streak += 1
                    if self.loss_streak >= self.max_loss_streak:
                        self.cooldown_until = datetime.now() + timedelta(hours=6)
                        logging.warning(f"PAUSE | Торговля приостановлена на 6 часов из-за 3 убытков подряд.")
                    closed_positions.append(f"SL сработал по {pos['symbol']} @ {price:.2f}")
                    continue

            except Exception as e:
                logging.error(f"CHECK_POSITION_ERROR | {pid} | {str(e)}")

        return closed_positions

    async def close_position(self, position_id):
        """Закрыть позицию"""
        try:
            pos = self.active_positions.get(position_id)
            if not pos:
                return False, "Позиция не найдена."

            side = 'SELL' if pos['side'] == 'BUY' else 'BUY'
            binance.create_order(
                symbol=pos['symbol'],
                type='MARKET',
                side=side,
                amount=pos['amount']
            )

            logging.info(f"FUTURES_CLOSE | {pos['symbol']} | {pos['side']} | {pos['amount']}")
            del self.active_positions[position_id]
            return True, "Позиция закрыта."
        except Exception as e:
            return False, str(e)

class PositionManager:
    """Класс для управления торговыми позициями"""
    def __init__(self):
        self.active_positions = {}  # Словарь для хранения активных позиций

    async def open_position(self, symbol, amount, stop_loss=None, take_profit=None):
        """Открытие позиции"""
        if not config.TRADING_ENABLED:
            return False, "Торговля отключена"

        if len(self.active_positions) >= config.MAX_TRADES_PER_DAY:
            return False, "Достигнут лимит сделок"

        try:
            balance = binance.fetch_balance()['USDT']['free']
            position_size = min(amount, balance * config.RISK_PER_TRADE)

            order = binance.create_order(
                symbol=symbol,
                type='MARKET',
                side='buy',
                amount=position_size,
                params={'stopLoss': stop_loss} if stop_loss else {}
            )

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
               
def is_binance_alive():
    """Быстрый пинг Binance — True, если соединение есть"""
    try:
        binance.fetch_time()
        return True
    except Exception:
        return False

def positions_summary():
    """Коротко о всех открытых позициях"""
    if not position_manager.active_positions:
        return "Нет открытых позиций"
    summary = []
    for pid, pos in position_manager.active_positions.items():
        sym   = pos['symbol']
        amt   = pos['amount']
        price = pos['entry_price']
        summary.append(f"{sym}: {amt:.6f} @ {price:.2f}")
    return "\n".join(summary)

position_manager = PositionManager()
futures_manager = FuturesManager()

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

# Команда /setkey: смена API ключей с валидацией и инструкцией
async def setkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed_users = [6107092031]  # ❗ УКАЖИ СВОЙ Telegram ID

    if user_id not in allowed_users:
        await update.message.reply_text("⛔ У тебя нет прав на эту команду.")
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "❗ Формат команды:\n/setkey <API_KEY> <API_SECRET>\n\n"
            "Пример:\n/setkey AbC123xYz AbC456qWe\n\n"
            "Оба значения обязательны. Не используй пробелы внутри ключей."
        )
        return

    api_key, api_secret = context.args

    # Простая валидация: длина и символы
    if not (10 <= len(api_key) <= 100) or not (10 <= len(api_secret) <= 100):
        await update.message.reply_text("❗ Похоже, один из ключей слишком короткий или длинный.")
        return

    if ' ' in api_key or ' ' in api_secret:
        await update.message.reply_text("❗ Ключи не должны содержать пробелы.")
        return

    # Обновление .env файла
    env_path = ".env"

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    def update_or_append(var, value, lines):
        found = False
        for i in range(len(lines)):
            if lines[i].startswith(f"{var}="):
                lines[i] = f"{var}={value}\n"
                found = True
        if not found:
            lines.append(f"{var}={value}\n")

    update_or_append("BINANCE_API_KEY", api_key, lines)
    update_or_append("BINANCE_API_SECRET", api_secret, lines)

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        load_dotenv(override=True)
        await update.message.reply_text("✅ Ключи успешно обновлены и применены.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при сохранении ключей: {e}")


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

async def trading_status(update: Update, context: CallbackContext):
    """Показать статус торговли"""
    status = "🟢 АКТИВЕН" if config.TRADING_ENABLED else "🔴 ВЫКЛЮЧЕН"
    await update.message.reply_text(
        f"Статус торговли: {status}\n"
        f"Риск на сделку: {config.RISK_PER_TRADE * 100}%\n"
        f"Лимит сделок: {len(position_manager.active_positions)}/{config.MAX_TRADES_PER_DAY}"
    )

async def set_risk(update: Update, context: CallbackContext):
    """Установка уровня риска"""
    try:
        risk = float(context.args[0]) / 100
        if 0.001 <= risk <= 0.1:  # 0.1% - 10%
            config.RISK_PER_TRADE = risk
            msg = f"🔐 Установлен риск: {risk * 100}%"
        else:
            msg = "❌ Риск должен быть между 0.1% и 10%"
        logging.info(f"CONFIG | RISK_SET | {risk * 100}%")
    except Exception:
        msg = "❌ Используйте: /risk 2.5 (для 2.5% риска)"
    
    await update.message.reply_text(msg)

async def show_log(update: Update, context: CallbackContext):
    """Команда /log — показывает последние строки из trades.log"""
    try:
        num_lines = int(context.args[0]) if context.args else 20
        with open("trades.log", "r", encoding="utf-8") as file:
            lines = file.readlines()[-num_lines:]
            if lines:
                output = "🧾 Последние события:\n" + "".join(lines)
                await update.message.reply_text(f"<pre>{output}</pre>", parse_mode="HTML")
            else:
                await update.message.reply_text("📭 Лог пока пуст.")
    except FileNotFoundError:
        await update.message.reply_text("❌ Лог-файл не найден.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при чтении лога: {e}")

async def trading_status_full(update: Update, context: CallbackContext):
    """Развёрнутый статус бота и соединения"""
    api_status   = "🟢 Онлайн" if is_binance_alive() else "🔴 Оффлайн"
    trade_status = "🟢 АКТИВЕН" if config.TRADING_ENABLED else "🔴 ВЫКЛЮЧЕН"
    open_pos     = positions_summary()
    balance      = get_binance_balance()

    msg = (
        f"📡 Binance API: {api_status}\n"
        f"📈 Статус торговли: {trade_status}\n"
        f"🔒 Риск на сделку: {config.RISK_PER_TRADE*100:.2f}%\n"
        f"🎯 Лимит сделок: {len(position_manager.active_positions)}/{config.MAX_TRADES_PER_DAY}\n"
        f"💰 Баланс: {balance['USDT']:.2f} USDT\n"
        f"🛒 Открытые позиции:\n{open_pos}"
    )
    await update.message.reply_text(msg)

async def analyze(update: Update, context: CallbackContext):
    """Команда /analyze — продвинутый анализ сигнала"""
    try:
        symbol = context.args[0].upper() + "/USDT" if context.args else "BTC/USDT"
        result = analyze_market_smart(symbol)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка в анализе: {str(e)}")

async def auto_trade_if_signal(symbol='BTC/USDT'):
    """Фоновая задача — проверка сигнала и открытие позиции"""
    if not config.TRADING_ENABLED:
        return

    signal_text = analyze_market(symbol)
    logging.info(f"AUTO_TRADE_CHECK | {symbol} | {signal_text}")

    # Примитивная проверка сигнала по ключевым словам
    if "ПОКУПАТЬ" in signal_text:
        try:
            result, detail = await position_manager.open_position(symbol, amount=1.0)
            msg = "✅ Открыта позиция: ПОКУПКА" if result else f"❌ Ошибка: {detail}"
        except Exception as e:
            msg = f"❌ Ошибка при покупке: {str(e)}"
        logging.info(f"AUTO_TRADE_BUY | {msg}")

    elif "ПРОДАВАТЬ" in signal_text:
        # Здесь пока не реализована продажа — можно позже расширить
        logging.info("AUTO_TRADE_SELL | ⚠ Пропущено — логика продажи не реализована.")

    else:
        logging.info("AUTO_TRADE_SKIP | Нет сигнала для входа.")

async def pause_trading(update: Update, context: CallbackContext):
    """Команда /pause — отключает торговлю"""
    config.TRADING_ENABLED = False
    logging.info("CONFIG | TRADING PAUSED")
    await update.message.reply_text("⛔ Торговля приостановлена.")

async def resume_trading(update: Update, context: CallbackContext):
    """Команда /resume — включает торговлю"""
    config.TRADING_ENABLED = True
    logging.info("CONFIG | TRADING RESUMED")
    await update.message.reply_text("🟢 Торговля активирована.")

def get_technical_indicators(symbol: str, timeframe: str, limit: int):
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        indicators = {}

        # Текущие значения
        indicators['price'] = df['close'].iloc[-1]
        indicators['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi().iloc[-1]

        bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        indicators['bb_upper'] = bb.bollinger_hband().iloc[-1]
        indicators['bb_lower'] = bb.bollinger_lband().iloc[-1]

        indicators['volume'] = df['volume'].iloc[-1]

        # 🔄 Новое: EMA и ATR
        indicators['ema'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator().iloc[-1]
        indicators['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range().iloc[-1]

        return indicators

    except Exception as e:
        logging.error(f"❌ INDICATOR_ERROR | {symbol} | {str(e)}")
        return None

def analyze_market_smart(symbol='BTC/USDT', timeframe='1h', limit=100):
    """📊 Расширенный анализ рынка с системой фильтров и доверием к сигналу"""
    indicators = get_technical_indicators(symbol, timeframe, limit)
    if not indicators:
        return "❌ Не удалось получить индикаторы."

    price = indicators['price']
    rsi = indicators['rsi']
    bb_upper = indicators['bb_upper']
    bb_lower = indicators['bb_lower']
    ema = indicators.get('ema', None)
    atr = indicators.get('atr', None)
    volume = indicators['volume']

    # Преобразуем данные в текст (если None → N/A)
    ema_text = f"{ema:.2f}" if ema is not None else "N/A"
    atr_text = f"{atr:.2f}" if atr is not None else "N/A"
    volume_text = f"{volume:.2f}" if volume is not None else "N/A"

    try:
        orderbook = binance.fetch_order_book(symbol, limit=10)
        bids = orderbook['bids']
        asks = orderbook['asks']
        bid_volume = sum([b[1] for b in bids[:3]])
        ask_volume = sum([a[1] for a in asks[:3]])
    except Exception as e:
        logging.error(f"ORDERBOOK_ERROR | {symbol} | {str(e)}")
        return f"❌ Ошибка при получении стакана."

    imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1)
    price_position = "🔹 Цена между уровнями"
    if price <= bb_lower:
        price_position = "🟢 Цена у нижней границы BB"
    elif price >= bb_upper:
        price_position = "🔴 Цена у верхней границы BB"

    # ↓↓↓ Логика оценки доверия к сигналу ↓↓↓
    signal = "❕ Нет условий для входа"
    confidence = 0  # уровень доверия к сигналу

    if rsi < 35:
        confidence += 1
    if price <= bb_lower:
        confidence += 1
    if imbalance > 0.2:
        confidence += 1
    if volume > 0:
        confidence += 1
    if ema is not None and price > ema:
        confidence += 1
    if atr is not None and atr > 0:
        confidence += 1

    if confidence >= 4 and rsi < 35:
        signal = "📈 СИГНАЛ: ПОКУПАТЬ"
    elif confidence >= 4 and rsi > 65:
        signal = "📉 СИГНАЛ: ПРОДАВАТЬ"

    log_msg = (
        f"🧠 ANALYZE_SMART | {symbol} | Price={price:.2f} | RSI={rsi:.2f} | "
        f"BB=({bb_lower:.2f}/{bb_upper:.2f}) | EMA={ema_text} | ATR={atr_text} | "
        f"Bid={bid_volume:.2f} Ask={ask_volume:.2f} | Imb={imbalance:.2f} | Confidence={confidence} | {signal}"
    )
    logging.info(log_msg)

    return (
        f"{signal}\n"
        f"{price_position}\n"
        f"📉 RSI: {rsi:.2f}\n"
        f"📏 EMA: {ema_text}\n"
        f"⚡ ATR: {atr_text}\n"
        f"📊 Объём: {volume_text}\n"
        f"🌟 Доверие к сигналу: {confidence}/6"
    )

async def open_long(update: Update, context: CallbackContext):
    """Открытие LONG позиции на фьючерсах"""
    try:
        if len(context.args) < 1:
            await update.message.reply_text("❗ Использование: /long <AMOUNT> [LEVERAGE]")
            return

        amount = float(context.args[0])
        leverage = int(context.args[1]) if len(context.args) > 1 else 5

        success, result = await futures_manager.open_position(
            symbol="BTC/USDT", side="BUY", amount=amount, leverage=leverage
        )
        if success:
            await update.message.reply_text(f"✅ LONG открыт: {result}")
        else:
            await update.message.reply_text(f"❌ Ошибка: {result}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def open_short(update: Update, context: CallbackContext):
    """Открытие SHORT позиции на фьючерсах"""
    try:
        if len(context.args) < 1:
            await update.message.reply_text("❗ Использование: /short <AMOUNT> [LEVERAGE]")
            return

        amount = float(context.args[0])
        leverage = int(context.args[1]) if len(context.args) > 1 else 5

        success, result = await futures_manager.open_position(
            symbol="BTC/USDT", side="SELL", amount=amount, leverage=leverage
        )
        if success:
            await update.message.reply_text(f"✅ SHORT открыт: {result}")
        else:
            await update.message.reply_text(f"❌ Ошибка: {result}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def show_positions(update: Update, context: CallbackContext):
    """Показать открытые фьючерсные позиции"""
    if not futures_manager.active_positions:
        await update.message.reply_text("📭 Открытых позиций нет.")
        return

    text = "📌 *Открытые позиции:*\n"
    for pid, pos in futures_manager.active_positions.items():
        text += f"- {pos['symbol']} | {pos['side']} | {pos['amount']} @ {pos['entry_price']}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def set_tp_sl(update: Update, context: CallbackContext):
    """Установить TP и SL для всех открытых позиций"""
    try:
        if len(context.args) < 2:
            await update.message.reply_text("❗ Использование: /tp_sl <TP%> <SL%>\nНапример: /tp_sl 5 2")
            return

        tp_percent = float(context.args[0]) / 100
        sl_percent = float(context.args[1]) / 100

        if not futures_manager.active_positions:
            await update.message.reply_text("📭 Нет активных позиций для установки TP/SL.")
            return

        for pid, pos in futures_manager.active_positions.items():
            entry_price = pos['entry_price']
            if pos['side'] == "BUY":
                pos['take_profit'] = entry_price * (1 + tp_percent)
                pos['stop_loss'] = entry_price * (1 - sl_percent)
            else:
                pos['take_profit'] = entry_price * (1 - tp_percent)
                pos['stop_loss'] = entry_price * (1 + sl_percent)

        await update.message.reply_text(
            f"✅ TP = {tp_percent*100:.1f}%, SL = {sl_percent*100:.1f}% установлены для всех позиций."
        )
        logging.info(f"TP_SL_SET | TP={tp_percent} | SL={sl_percent}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def toggle_auto(update: Update, context: CallbackContext):
    """Переключить авто-режим торговли"""
    config.AUTO_TRADING = not getattr(config, "AUTO_TRADING", False)
    state = "🟢 Авто-режим включён" if config.AUTO_TRADING else "🔴 Авто-режим выключен"
    await update.message.reply_text(state)
    logging.info(f"AUTO_TRADING | {state}")

from datetime import datetime, timedelta

from datetime import datetime, timedelta

async def update_trade_result(profit: float, app):
    """
    Обновляет состояние бота после сделки.
    :param profit: прибыль (если отрицательная — убыток).
    :param app: объект Telegram приложения.
    """
    if profit < 0:
        config.LOSE_STREAK += 1
        logging.info(f"LOSE STREAK: {config.LOSE_STREAK}")
        if config.LOSE_STREAK >= 3:
            config.TRADING_ENABLED = False
            config.PAUSE_UNTIL = datetime.utcnow() + timedelta(hours=6)
            await app.bot.send_message(
                chat_id=CHAT_ID,
                text="⏸ Торговля остановлена на 6 часов (3 убыточные сделки подряд)."
            )
    else:
        config.LOSE_STREAK = 0

# Асинхронная проверка сигналов
async def signal_checker():
    while True:
        try:
            if config.TRADING_ENABLED or getattr(config, "AUTO_TRADING", False):
                result = analyze_market_smart()
                if "СИГНАЛ:" in result:
                    logging.info(f"AUTO_SIGNAL | {result}")
                    await app.bot.send_message(chat_id=CHAT_ID, text=f"📡 Обнаружен сигнал:\n\n{result}")

                    # Автоторговля
                    if getattr(config, "AUTO_TRADING", False):
                        side = "BUY" if "ПОКУПАТЬ" in result else "SELL"
                        usdt_balance = binance.fetch_balance()['USDT']['free']
                        amount = usdt_balance * config.RISK_PER_TRADE
                        success, response = await futures_manager.open_position(
                            symbol="BTC/USDT", side=side, amount=amount
                        )
                        if success:
                            await app.bot.send_message(chat_id=CHAT_ID, text=f"🤖 Автоматически открыт {side} на {amount:.2f} USDT.")
                        else:
                            await app.bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Ошибка при открытии позиции: {response}")
        except Exception as e:
            logging.error(f"signal_checker ERROR: {e}")
            await app.bot.send_message(chat_id=CHAT_ID, text=f"❌ Ошибка в signal_checker: {e}")

        await asyncio.sleep(60)  # Проверка сигнала каждую минуту


# Проверка закрытых позиций
async def positions_watcher():
    while True:
        try:
            closed = await futures_manager.check_positions()
            if closed:
                for msg in closed:
                    await app.bot.send_message(chat_id=CHAT_ID, text=f"🔔 {msg}")
        except Exception as e:
            logging.error(f"positions_watcher ERROR: {e}")
        await asyncio.sleep(60)

async def trading_status_full(update: Update, context: CallbackContext):
    """Показывает расширенный статус с последними сигналами"""
    try:
        balance = binance.fetch_balance()
        usdt = balance['USDT']['free']
        btc = balance['BTC']['free']

        # Получаем последние 3 записи из лога сигналов
        recent_signals = []
        try:
            with open('trades.log', 'r', encoding='utf-8') as log_file:
                lines = log_file.readlines()
                recent_signals = lines[-3:] if len(lines) >= 3 else lines
        except FileNotFoundError:
            recent_signals = ["Лог-файл отсутствует."]

        status_lines = [
            "📊 *РАСШИРЕННЫЙ СТАТУС*",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            f"🤖 *Авто-режим:* {'🟢 Включён' if config.AUTO_TRADING else '🔴 Выключен'}",
            f"🔐 *Риск на сделку:* {config.RISK_PER_TRADE * 100:.1f}%",
            f"⚡ *Сделок подряд в минус:* {config.LOSE_STREAK}/3",
            f"⏳ *Пауза до:* {config.PAUSE_UNTIL.strftime('%Y-%m-%d %H:%M:%S') if config.PAUSE_UNTIL else '—'}",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            f"💰 *Баланс USDT:* {usdt:.2f}",
            f"💰 *Баланс BTC:* {btc:.6f}",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            "📈 *Последние сигналы:*",
        ] + [f"• {line.strip()}" for line in recent_signals]

        await update.message.reply_text("\n".join(status_lines), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"STATUS_FULL_ERROR: {str(e)}")
        await update.message.reply_text(f"❌ Ошибка при получении расширенного статуса: {str(e)}")

# Команда /help
async def show_help(update: Update, context: CallbackContext):
    """
    Показывает список доступных команд с описанием.
    """
    help_text = "📖 <b>Доступные команды:</b>\n\n"

    # Группы команд
    main_commands = []
    trading_commands = []
    system_commands = []

    for cmd, desc in COMMANDS:
        if cmd in ["start", "balance", "price", "setkey"]:
            main_commands.append(f"/{cmd} — {desc}")
        elif cmd in ["analyze", "risk", "pause", "resume", "auto", "trading_status", "status"]:
            trading_commands.append(f"/{cmd} — {desc}")
        else:
            system_commands.append(f"/{cmd} — {desc}")

    if main_commands:
        help_text += "🔹 <b>Основные:</b>\n" + "\n".join(main_commands) + "\n\n"
    if trading_commands:
        help_text += "💹 <b>Торговля:</b>\n" + "\n".join(trading_commands) + "\n\n"
    if system_commands:
        help_text += "⚙ <b>Системные:</b>\n" + "\n".join(system_commands)

    await update.message.reply_text(help_text, parse_mode="HTML")

def main():
    """Запуск бота"""
    global app
    print(">>> MAIN START")

    if not TELEGRAM_TOKEN:
        raise ValueError("❌ TELEGRAM_TOKEN не найден! Проверь .env")

    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        # Регистрация команд через register_command
        register_command(app, "start", start, "Запустить бота")
        register_command(app, "balance", check_balance, "Проверить баланс")
        register_command(app, "price", price, "Курс BTC")
        register_command(app, "setkey", setkey, "Установить API ключ")
        register_command(app, "log", show_log, "Показать логи")
        register_command(app, "status", trading_status, "Краткий статус")
        register_command(app, "trading_status", trading_status_full, "Полный статус торговли")
        register_command(app, "help", show_help, "Список команд")
        register_command(app, "risk", set_risk, "Изменить риск (%)")
        register_command(app, "analyze", analyze, "Анализ рынка")
        register_command(app, "pause", pause_trading, "Пауза торговли")
        register_command(app, "resume", resume_trading, "Возобновить торговлю")
        register_command(app, "auto", toggle_auto, "Включить/выключить автоторговлю")
        register_command(app, "long", open_long, "Открыть LONG позицию")
        register_command(app, "short", open_short, "Открыть SHORT позицию")
        register_command(app, "positions", show_positions, "Показать открытые позиции")
        register_command(app, "tp_sl", set_tp_sl, "Установить TP/SL")

        # Запуск фоновых задач через JobQueue
        app.job_queue.run_repeating(lambda _: asyncio.create_task(signal_checker()), interval=60)
        app.job_queue.run_repeating(lambda _: asyncio.create_task(positions_watcher()), interval=60)

        print("Бот запущен...")
        app.run_polling()

    except Exception as e:
        logging.error(f"MAIN_ERROR: {e}", exc_info=True)
        print(f"❌ ОШИБКА ПРИ ЗАПУСКЕ БОТА: {e}")


if __name__ == "__main__":
    while True:
        try:
            print("🚀 Запуск бота...")
            main()
        except Exception as e:
            logging.error(f"BOT_CRASH | {e}", exc_info=True)
            print(f"❌ Бот упал: {e}")
            print("🔄 Перезапуск через 5 секунд...")
            time.sleep(5)
