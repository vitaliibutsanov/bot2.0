import logging

# === Профили рисков ===
RISK_MODES = {
    "SAFE": {
        "trade_percent": 0.005,  # 0.5% депозита
        "max_positions": 3,
        "description": "Защитный режим: минимальный риск, сделки реже."
    },
    "NORMAL": {
        "trade_percent": 0.01,  # 1% депозита
        "max_positions": 5,
        "description": "Стандартный режим: сбалансированный риск."
    },
    "AGGRESSIVE": {
        "trade_percent": 0.02,  # 2% депозита
        "max_positions": 10,
        "description": "Агрессивный режим: повышенный риск, больше сделок."
    }
}

# === Текущий режим ===
current_mode = "NORMAL"
AUTO_MODE = True  # Автопереключение включено по умолчанию


def set_risk_mode(mode: str):
    """Устанавливает новый режим риска."""
    global current_mode
    mode = mode.upper()
    if mode in RISK_MODES:
        current_mode = mode
        logging.info(f"[RISK_MODE] Установлен режим: {mode}")
        return True, f"Режим риска изменён на {mode}: {RISK_MODES[mode]['description']}"
    else:
        return False, f"⚠ Неизвестный режим: {mode}. Доступные: {', '.join(RISK_MODES.keys())}"


def get_risk_mode():
    """Возвращает описание текущего режима риска."""
    auto_text = "AUTO" if AUTO_MODE else "MANUAL"
    mode_data = RISK_MODES.get(current_mode, RISK_MODES["NORMAL"])
    return (f"Текущий режим: {current_mode} ({auto_text}) | "
            f"{mode_data['description']} "
            f"(TP={mode_data['trade_percent']*100:.1f}%, MaxPos={mode_data['max_positions']})")


def get_trade_percent():
    """Возвращает процент депозита для сделки в текущем режиме."""
    return RISK_MODES[current_mode]["trade_percent"]


def get_max_positions():
    """Возвращает максимальное число позиций для текущего режима."""
    return RISK_MODES[current_mode]["max_positions"]


def toggle_auto_mode():
    """Переключает авторежим."""
    global AUTO_MODE
    AUTO_MODE = not AUTO_MODE
    status = "включен" if AUTO_MODE else "выключен"
    logging.info(f"[RISK_MODE] Автоматический режим {status} | Текущий: {current_mode}")
    return f"Автоматический режим {status}. {get_risk_mode()}"


def auto_adjust_mode(market_state: str):
    """
    Автоматически выбирает режим на основе состояния рынка.
    Работает только если AUTO_MODE=True.
    """
    global current_mode
    if not AUTO_MODE:
        return current_mode  # Если ручной режим — ничего не делаем

    prev_mode = current_mode

    if market_state == "RANGE":
        current_mode = "AGGRESSIVE"
    elif market_state == "VOLATILE":
        current_mode = "SAFE"
    elif market_state in ("TREND_UP", "TREND_DOWN"):
        current_mode = "NORMAL"
    else:
        logging.warning(f"[AUTO_MODE] Неизвестное состояние рынка: {market_state}")
        return current_mode

    if current_mode != prev_mode:
        logging.info(f"[AUTO_MODE] Режим изменён: {prev_mode} → {current_mode} (рынок: {market_state})")
    return current_mode
