import os
import time
import threading
from typing import Tuple, List

LOG_PATH = os.path.join("logs", "trading_history.log")
LOCK = threading.Lock()

_last_analysis_time = 0
ANALYSIS_INTERVAL = 30 * 60  # 30 минут


def log_trade(timestamp: float, symbol: str, side: str, price: float, amount: float, pnl: float):
    """
    Записывает одну сделку в trading_history.log
    Формат: timestamp,symbol,side,price,amount,pnl
    """
    line = f"{timestamp:.0f},{symbol},{side},{price:.8f},{amount:.8f},{pnl:.8f}\n"
    with LOCK:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)


def load_trades() -> List[List[str]]:
    """Загружает все сделки из лог-файла."""
    if not os.path.exists(LOG_PATH):
        return []
    with LOCK:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            return [line.strip().split(",") for line in f if line.strip()]


def analyze_history() -> Tuple[int, int, float, float, int, int, float, float]:
    """
    Анализирует историю торговли и возвращает:
    total_trades, win_count, winrate, avg_pnl, max_win_streak, max_loss_streak, max_pnl, min_pnl
    """
    trades = load_trades()
    if not trades:
        return 0, 0, 0.0, 0.0, 0, 0, 0.0, 0.0

    total = 0
    wins = 0
    pnl_sum = 0.0
    max_pnl = float("-inf")
    min_pnl = float("inf")
    max_win_streak = 0
    max_loss_streak = 0
    curr_win_streak = 0
    curr_loss_streak = 0

    for parts in trades:
        total += 1
        try:
            pnl = float(parts[5])
        except:
            continue

        pnl_sum += pnl
        max_pnl = max(max_pnl, pnl)
        min_pnl = min(min_pnl, pnl)

        if pnl > 0:
            wins += 1
            curr_win_streak += 1
            curr_loss_streak = 0
            max_win_streak = max(max_win_streak, curr_win_streak)
        elif pnl < 0:
            curr_loss_streak += 1
            curr_win_streak = 0
            max_loss_streak = max(max_loss_streak, curr_loss_streak)
        else:
            curr_win_streak = 0
            curr_loss_streak = 0

    winrate = wins / total * 100 if total else 0.0
    avg_pnl = pnl_sum / total if total else 0.0
    return total, wins, round(winrate, 2), round(avg_pnl, 6), max_win_streak, max_loss_streak, round(max_pnl, 6), round(min_pnl, 6)


def history_report_text() -> str:
    """
    Возвращает расширенный текстовый отчет.
    """
    total, wins, winrate, avg_pnl, max_win, max_loss, max_pnl, min_pnl = analyze_history()
    return (
        f"📘 Trading History Report:\n"
        f"• Сделок: {total}\n"
        f"• Выигрышей: {wins} ({winrate:.1f} %)\n"
        f"• Средний PnL: {avg_pnl:.6f}\n"
        f"• Max серия +: {max_win}\n"
        f"• Max серия –: {max_loss}\n"
        f"• Лучшая сделка: {max_pnl:.6f}\n"
        f"• Худшая сделка: {min_pnl:.6f}"
    )


def last_n_trades_report(n: int = 10) -> str:
    """
    Возвращает отчет о последних N сделках.
    """
    trades = load_trades()
    if not trades:
        return "История сделок пуста."

    last_trades = trades[-n:]
    report_lines = ["📜 Последние сделки:"]
    for t in last_trades:
        try:
            ts = time.strftime("%d-%m %H:%M", time.localtime(float(t[0])))
            report_lines.append(f"{ts} | {t[1]} | {t[2]} @ {t[3]} | PnL={float(t[5]):.4f}")
        except:
            continue
    return "\n".join(report_lines)


def periodic_analysis(trigger_func):
    """
    В отдельном потоке раз в ANALYSIS_INTERVAL вызывает trigger_func().
    """
    def runner():
        global _last_analysis_time
        while True:
            now = time.time()
            if now - _last_analysis_time >= ANALYSIS_INTERVAL:
                try:
                    trigger_func()
                except Exception as e:
                    print(f"[PERIODIC_ANALYSIS_ERROR] {e}")
                _last_analysis_time = now
            time.sleep(10)

    threading.Thread(target=runner, daemon=True).start()
