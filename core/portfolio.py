import logging
import os
import json
from datetime import datetime, timedelta
from core.risk_manager import risk_manager
from config import binance

PORTFOLIO_FILE = "logs/portfolio.json"


class VirtualPortfolio:
    def __init__(self, initial_balance=1000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.history = []  # [(datetime, pnl, type)]
        self.buy_count = 0
        self.sell_count = 0
        self._load_portfolio()

        if risk_manager.balance_start is None:
            risk_manager.balance_start = self.balance

    def _save_portfolio(self):
        """Сохраняет состояние портфеля в JSON."""
        try:
            os.makedirs("logs", exist_ok=True)
            data = {
                "initial_balance": self.initial_balance,
                "balance": self.balance,
                "buy_count": self.buy_count,
                "sell_count": self.sell_count,
                "history": [
                    {"time": t.isoformat(), "pnl": pnl, "type": t_type}
                    for t, pnl, t_type in self.history
                ],
            }
            with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"PORTFOLIO_SAVE_ERROR | {e}")

    def _load_portfolio(self):
        """Загружает портфель из файла или создаёт новый."""
        try:
            if os.path.exists(PORTFOLIO_FILE):
                with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.initial_balance = data.get("initial_balance", self.initial_balance)
                self.balance = data.get("balance", self.initial_balance)
                self.buy_count = data.get("buy_count", 0)
                self.sell_count = data.get("sell_count", 0)
                self.history = [
                    (datetime.fromisoformat(item["time"]), item["pnl"], item["type"])
                    for item in data.get("history", [])
                ]
            self._sync_with_binance_balance()
        except Exception as e:
            logging.error(f"PORTFOLIO_LOAD_ERROR | {e}")
            self._reset_portfolio()

    def _sync_with_binance_balance(self):
        """Синхронизация с балансом Binance."""
        try:
            real_balance = binance.fetch_balance().get("total", {}).get("USDT", self.balance)
            if abs(real_balance - self.balance) > self.balance * 0.1:
                logging.warning(f"[SYNC] Обновляем виртуальный баланс с {self.balance:.2f} на {real_balance:.2f}")
                self.balance = real_balance
                risk_manager.balance_start = self.balance
                self._save_portfolio()
        except Exception as e:
            logging.error(f"BINANCE_SYNC_ERROR | {e}")

    def _reset_portfolio(self):
        """Сброс портфеля."""
        self.balance = self.initial_balance
        self.history.clear()
        self.buy_count = 0
        self.sell_count = 0
        risk_manager.balance_start = self.balance
        self._save_portfolio()
        logging.warning("[RESET] Виртуальный портфель сброшен.")

    def apply_trade(self, pnl_usdt, trade_type="SELL"):
        """
        Добавляет сделку:
        - Для BUY PnL = 0 (только увеличиваем счётчик).
        - Для SELL PnL = прибыль/убыток, корректируем баланс.
        """
        if trade_type == "BUY":
            self.buy_count += 1
            pnl_usdt = 0
        elif trade_type == "SELL":
            self.sell_count += 1
            self.balance += pnl_usdt

        self.history.append((datetime.now(), pnl_usdt, trade_type))
        logging.info(f"VIRTUAL_PNL | {trade_type} | {pnl_usdt:.2f} USDT | Balance={self.balance:.2f} USDT")

        risk_manager.balance_start = self.balance
        self._save_portfolio()

    def calculate_report(self, days: int):
        """Считает PnL за N дней."""
        cutoff = datetime.now() - timedelta(days=days)
        pnl_sum = sum(p for (t, p, _) in self.history if t >= cutoff)
        percent = (pnl_sum / self.initial_balance) * 100 if self.initial_balance > 0 else 0
        return pnl_sum, percent

    def full_report(self):
        """Формирует отчёт по портфелю."""
        d, dp = self.calculate_report(1)
        w, wp = self.calculate_report(7)
        m, mp = self.calculate_report(30)
        return (
            f"📊 Виртуальный портфель:\n"
            f"Баланс: {self.balance:.2f} USDT\n"
            f"Сделок: {self.buy_count + self.sell_count} (BUY: {self.buy_count} | SELL: {self.sell_count})\n"
            f"24ч: {d:.2f} USDT ({dp:.2f}%)\n"
            f"7д: {w:.2f} USDT ({wp:.2f}%)\n"
            f"30д: {m:.2f} USDT ({mp:.2f}%)"
        )


virtual_portfolio = VirtualPortfolio(1000)


def get_portfolio_status():
    return virtual_portfolio.full_report()
