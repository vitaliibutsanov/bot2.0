import os
from core.trade_manager import TradeManager

def main():
    manager = TradeManager()
    print("Баланс:", manager.check_balance())
    signal = manager.analyze_market()
    print("Сигнал анализа:", signal)

if __name__ == "__main__":
    main()
