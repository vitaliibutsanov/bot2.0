import ccxt
from core.config import BINANCE_API_KEY, BINANCE_API_SECRET

class BinanceAPI:
    def __init__(self):
        self.client = ccxt.binance({
            "apiKey": BINANCE_API_KEY,
            "secret": BINANCE_API_SECRET,
            "enableRateLimit": True
        })

    def get_balance(self):
        return self.client.fetch_balance()

    def get_ticker(self, symbol="BTC/USDT"):
        return self.client.fetch_ticker(symbol)
