def format_balance(amount: float, precision: int = 6) -> str:
    """
    Format balance ke string rapi
    """
    return f"{round(amount, precision):.{precision}f}"


def format_currency(amount: float) -> str:
    """
    Format tampilan uang dengan tanda
    """
    if amount < 0:
        return f"-{abs(round(amount, 6)):.6f}"
    return f"+{round(amount, 6):.6f}"


def format_ledger_entry(entry: dict) -> str:
    """
    Format ledger ke text readable (buat bot/UI)
    """
    return (
        f"[{entry.get('type')}] "
        f"Amount: {entry.get('amount')} | "
        f"Before: {entry.get('balance_before')} | "
        f"After: {entry.get('balance_after')}"
    )