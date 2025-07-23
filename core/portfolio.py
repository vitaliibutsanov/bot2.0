import logging
from datetime import datetime, timedelta

class VirtualPortfolio:
    def __init__(self, initial_balance=1000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.history = []  # [(datetime, pnl_usdt, type)]
        self.buy_count = 0
        self.sell_count = 0

    def apply_trade(self, pnl_usdt, trade_type="SELL"):
        """Добавляем сделку в историю (pnl_usdt может быть отрицательным)."""
        self.balance += pnl_usdt
        self.history.append((datetime.now(), pnl_usdt, trade_type))

        if trade_type == "BUY":
            self.buy_count += 1
        elif trade_type == "SELL":
            self.sell_count += 1

        logging.info(
            f"VIRTUAL_PNL | {trade_type} | {pnl_usdt:.2f} USDT | Balance={self.balance:.2f} USDT"
        )

    def calculate_report(self, days: int):
        cutoff = datetime.now() - timedelta(days=days)
        pnl_sum = sum(p for (t, p, _) in self.history if t >= cutoff)
        percent = (pnl_sum / self.initial_balance) * 100
        return pnl_sum, percent

    def full_report(self):
        d, dp = self.calculate_report(1)
        w, wp = self.calculate_report(7)
        m, mp = self.calculate_report(30)
        return (
            f"📊 Отчёт по виртуальному портфелю:\n"
            f"Баланс: {self.balance:.2f} USDT\n"
            f"Сделок: {self.buy_count + self.sell_count} "
            f"(BUY: {self.buy_count} | SELL: {self.sell_count})\n"
            f"24ч: {d:.2f} USDT ({dp:.2f}%)\n"
            f"7д: {w:.2f} USDT ({wp:.2f}%)\n"
            f"30д: {m:.2f} USDT ({mp:.2f}%)"
        )

virtual_portfolio = VirtualPortfolio(1000)

def get_portfolio_status():
    """Возвращает отчёт по виртуальному портфелю."""
    return virtual_portfolio.full_report()
