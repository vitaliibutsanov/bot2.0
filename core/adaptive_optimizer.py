import os
import time
import logging
from core.history_analyzer import analyze_history

ANALYTICS_LOG = os.path.join("logs", "analytics.log")

# Начальные значения
RSI_BUY = 40
RSI_SELL = 60
TP_PERCENT = 0.011  # 1.1%
SL_PERCENT = 0.05   # 5%

# Ограничения адаптации
MIN_RSI = 25
MAX_RSI = 75
MIN_TP = 0.005  # 0.5%
MAX_TP = 0.03   # 3%
MIN_SL = 0.02   # 2%
MAX_SL = 0.1    # 10%

# Шаги адаптации
STEP_TP = 0.001
STEP_SL = 0.005
STEP_RSI = 1

def log_analytics(message: str):
    """Записывает сообщение в analytics.log"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(ANALYTICS_LOG, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} | {message}\n")

def adaptive_optimize():
    """
    Адаптивно изменяет RSI_BUY, RSI_SELL, TP_PERCENT, SL_PERCENT
    на основе winrate и среднего PnL из history_analyzer.
    """
    global RSI_BUY, RSI_SELL, TP_PERCENT, SL_PERCENT

    try:
        total, wins, winrate, avg_pnl, max_win, max_loss = analyze_history()
    except Exception as e:
        log_analytics(f"ANALYZE_ERROR | {e}")
        return

    if total < 10:  # Недостаточно данных
        log_analytics("NO DATA: Недостаточно истории для оптимизации.")
        return

    log_analytics(f"START OPTIMIZATION | Trades={total} | Wins={wins} | Winrate={winrate}% | AvgPnL={avg_pnl:.2f} | MaxWin={max_win:.2f} | MaxLoss={max_loss:.2f}")

    # --- Логика адаптации ---
    if winrate < 40 or avg_pnl < 0:  # низкий winrate или отрицательный PnL
        SL_PERCENT = min(SL_PERCENT + STEP_SL, MAX_SL)
        TP_PERCENT = max(TP_PERCENT - STEP_TP, MIN_TP)
        RSI_BUY = min(RSI_BUY + STEP_RSI, MAX_RSI)
        RSI_SELL = max(RSI_SELL - STEP_RSI, MIN_RSI)
        log_analytics(f"WINRATE LOW: TP={TP_PERCENT:.4f}, SL={SL_PERCENT:.4f}, RSI_BUY={RSI_BUY}, RSI_SELL={RSI_SELL}")

    elif winrate > 60 and avg_pnl > 0:  # высокий winrate и положительный PnL
        SL_PERCENT = max(SL_PERCENT - STEP_SL, MIN_SL)
        TP_PERCENT = min(TP_PERCENT + STEP_TP, MAX_TP)
        RSI_BUY = max(RSI_BUY - STEP_RSI, MIN_RSI)
        RSI_SELL = min(RSI_SELL + STEP_RSI, MAX_RSI)
        log_analytics(f"WINRATE HIGH: TP={TP_PERCENT:.4f}, SL={SL_PERCENT:.4f}, RSI_BUY={RSI_BUY}, RSI_SELL={RSI_SELL}")

    else:
        log_analytics("NO CHANGE: Параметры остаются без изменений")

    # --- Доп. метрика: если MaxLoss >> MaxWin ---
    if abs(max_loss) > abs(max_win) * 1.5:
        SL_PERCENT = min(SL_PERCENT + STEP_SL, MAX_SL)
        log_analytics(f"LOSS_ADJUST: Увеличен SL из-за больших просадок | SL={SL_PERCENT:.4f}")

    # --- Доп. метрика: если winrate стабилен, но PnL маленький ---
    if 45 <= winrate <= 55 and 0 < avg_pnl < 0.1:
        TP_PERCENT = min(TP_PERCENT + STEP_TP, MAX_TP)
        log_analytics(f"TP_BOOST: Увеличен TP для роста прибыли | TP={TP_PERCENT:.4f}")


def get_current_parameters():
    """Возвращает текущие значения параметров."""
    return {
        "RSI_BUY": RSI_BUY,
        "RSI_SELL": RSI_SELL,
        "TP_PERCENT": TP_PERCENT,
        "SL_PERCENT": SL_PERCENT
    }

def parameters_report():
    """Возвращает строку с параметрами для Telegram-бота."""
    params = get_current_parameters()
    return (f"🔧 Параметры стратегии:\n"
            f"• RSI Buy: {params['RSI_BUY']}\n"
            f"• RSI Sell: {params['RSI_SELL']}\n"
            f"• TP: {params['TP_PERCENT'] * 100:.2f}%\n"
            f"• SL: {params['SL_PERCENT'] * 100:.2f}%")
