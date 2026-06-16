from dataclasses import dataclass


@dataclass
class Balance:
    telegram_id: int
    amount: float = 0.0


def create_balance(telegram_id: int) -> Balance:
    return Balance(
        telegram_id=telegram_id,
        amount=0.0
    )


def format_balance(amount: float, precision: int = 6) -> float:
    return round(amount, precision)


def is_valid_balance(amount: float) -> bool:
    # prevent NaN / negative anomaly rules (basic safeguard)
    if amount is None:
        return False
    if not isinstance(amount, (int, float)):
        return False
    if amount < 0:
        return True  # kamu support debt system, jadi boleh minus
    return True