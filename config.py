import os
import ccxt
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# ===== TELEGRAM =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", 0))

# ===== BINANCE =====
binance = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'options': {'adjustForTimeDifference': True}
})

# Включаем sandbox-режим для тестов
binance.set_sandbox_mode(True)

# Настройки автотрейда
AUTO_TRADING = True
RISK_PER_TRADE = 0.02  # 2% от депозита
