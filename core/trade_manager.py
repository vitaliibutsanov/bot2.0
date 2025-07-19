from core.binance_api import BinanceAPI
from strategies.rsi_bb import analyze_rsi_bb
from utils.logger import log

class TradeManager:
    def __init__(self):
        self.api = BinanceAPI()

    def check_balance(self):
        balance = self.api.get_balance()
        log(f"Баланс: {balance}")
        return balance

    def analyze_market(self):
        ticker = self.api.get_ticker("BTC/USDT")
        signal = analyze_rsi_bb(ticker)
        log(f"Анализ сигнала: {signal}")
        return signal
