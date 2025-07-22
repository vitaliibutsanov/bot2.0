import logging
from datetime import datetime, timedelta

class VirtualPortfolio:
    def __init__(self, initial_balance=1000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.history = []

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

def get_portfolio_status():
    """
    Возвращает отчёт по виртуальному портфелю.
    Пока что заглушка, можно подключить реальный расчёт.
    """
    report = (
        "📊 Отчёт по виртуальному портфелю:\n"
        "Баланс: 1000.00 USDT\n"
        "24ч: 0.00 USDT (0.00%)\n"
        "7д: 0.00 USDT (0.00%)\n"
        "30д: 0.00 USDT (0.00%)"
    )
    return report
