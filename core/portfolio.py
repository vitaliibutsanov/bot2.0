import logging
from datetime import datetime, timedelta
import os
import json
from core.risk_manager import risk_manager  # Связь с системой рисков
from config import binance  # Чтобы подтягивать актуальный баланс

PORTFOLIO_FILE = "logs/portfolio.json"


class VirtualPortfolio:
    def __init__(self, initial_balance=1000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.history = []  # [(datetime, pnl_usdt, type)]
        self.buy_count = 0
        self.sell_count = 0
        self._load_portfolio()
        # Инициализируем risk_manager стартовым балансом
        if risk_manager.balance_start is None:
            risk_manager.balance_start = self.balance

    def _save_portfolio(self):
        """Сохраняет текущее состояние портфеля в файл."""
        try:
            os.makedirs("logs", exist_ok=True)
            data = {
                "initial_balance": self.initial_balance,
                "balance": self.balance,
                "buy_count": self.buy_count,
                "sell_count": self.sell_count,
                "history": [
                    {"time": t.isoformat(), "pnl": pnl, "type": trade_type}
                    for (t, pnl, trade_type) in self.history
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
                    (
                        datetime.fromisoformat(item["time"]),
                        item["pnl"],
                        item["type"],
                    )
                    for item in data.get("history", [])
                ]
                logging.info(f"[DEBUG] Загружен виртуальный портфель. Баланс: {self.balance:.2f} USDT")

            # --- СИНХРОНИЗАЦИЯ С BINANCE ---
            self._sync_with_binance_balance()

        except Exception as e:
            logging.error(f"PORTFOLIO_LOAD_ERROR | {e}")
            self._reset_portfolio()

    def _sync_with_binance_balance(self):
        """Сравнивает баланс портфеля с балансом Binance и синхронизирует при большой разнице."""
        try:
            real_balance = binance.fetch_balance().get("total", {}).get("USDT", self.balance)
            if abs(real_balance - self.balance) > self.balance * 0.1:  # Разница более 10%
                logging.warning(
                    f"[SYNC] Баланс виртуального портфеля ({self.balance:.2f}) "
                    f"не совпадает с Binance ({real_balance:.2f}). Обновляем..."
                )
                self.balance = real_balance
                risk_manager.balance_start = self.balance
                self._save_portfolio()
        except Exception as e:
            logging.error(f"BINANCE_SYNC_ERROR | {e}")

    def _reset_portfolio(self):
        """Сбрасывает портфель до начального состояния."""
        self.balance = self.initial_balance
        self.history = []
        self.buy_count = 0
        self.sell_count = 0
        risk_manager.balance_start = self.balance
        self._save_portfolio()
        logging.warning("[RESET] Виртуальный портфель сброшен.")

    def apply_trade(self, pnl_usdt, trade_type="SELL"):
        """
        Добавляет сделку в историю.
        pnl_usdt — прибыль/убыток в USDT (может быть отрицательным).
        """
        self.balance += pnl_usdt
        self.history.append((datetime.now(), pnl_usdt, trade_type))

        if trade_type == "BUY":
            self.buy_count += 1
        elif trade_type == "SELL":
            self.sell_count += 1

        logging.info(
            f"VIRTUAL_PNL | {trade_type} | {pnl_usdt:.2f} USDT | Balance={self.balance:.2f} USDT"
        )

        # Обновляем баланс в risk_manager
        risk_manager.balance_start = self.balance

        self._save_portfolio()

    def calculate_report(self, days: int):
        """Возвращает PnL за последние N дней."""
        cutoff = datetime.now() - timedelta(days=days)
        pnl_sum = sum(p for (t, p, _) in self.history if t >= cutoff)
        percent = (pnl_sum / self.initial_balance) * 100 if self.initial_balance > 0 else 0
        return pnl_sum, percent

    def full_report(self):
        """Формирует текстовый отчёт по портфелю."""
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
    """Возвращает текущий отчёт по виртуальному портфелю."""
    return virtual_portfolio.full_report()
