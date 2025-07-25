import os 
import ccxt
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# ===== TELEGRAM =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", 0))

# ===== BINANCE FUTURES TESTNET =====
binance = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',  # ВАЖНО: фьючерсы
        'adjustForTimeDifference': True
    }
})

# Включаем sandbox-режим (testnet)
binance.set_sandbox_mode(True)

# Настройки автотрейда
AUTO_TRADING = True

# ===== Торговые параметры =====
TRADE_PERCENT = 0.01  # 1% от депозита на сделку
RISK_PER_TRADE = 0.02  # 2% риск на сделку (для стратегий с SL)

# ===== Индикаторы =====
ATR_THRESHOLD = 0.05  # Порог ATR для блокировки торговли (волатильность)
