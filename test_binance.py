import os
import ccxt
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

binance = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_API_SECRET
})

try:
    balance = binance.fetch_balance()
    print("Баланс:", balance)
except Exception as e:
    print("Ошибка:", e)

print("Проверим цену BTC/USDT:")
ticker = binance.fetch_ticker('BTC/USDT')
print(ticker)
