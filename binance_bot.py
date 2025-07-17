import ccxt  # Исправлено ctxt на ccxt
import os
import time
import logging
import asyncio
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt  # Перенесено в основной блок импортов

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
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

class TradingConfig:
    """Настройки торговли"""
    RISK_PER_TRADE = 0.02  # 2% от депозита
    MAX_TRADES_PER_DAY = 5
    STOP_LOSS = 0.05  # 5%
    TAKE_PROFIT = 0.10  # 10%
    TRADING_ENABLED = False  # Флаг для ручного управления

config = TradingConfig()

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

position_manager = PositionManager()

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

async def analyze(update: Update, context: CallbackContext):
    """Заглушка для команды /analyze"""
    await update.message.reply_text("🔍 Анализ пока не реализован. Ожидайте обновлений!")

def main():
    """Запуск бота"""
    print(">>> MAIN START")
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        # Основные команды
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("balance", check_balance))
        app.add_handler(CommandHandler("price", price))

        # Торговые команды
        app.add_handler(CommandHandler("status", trading_status))
        app.add_handler(CommandHandler("risk", set_risk))
        app.add_handler(CommandHandler("analyze", analyze))

        print("Бот запущен...")
        app.run_polling()

    except Exception as e:
        print("🛑 ОШИБКА ПРИ ЗАПУСКЕ БОТА:")
        print(str(e))
if __name__ == "__main__":
    main()
