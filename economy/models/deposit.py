from dataclasses import dataclass
import time


@dataclass
class Deposit:
    telegram_id: int
    ref_id: str
    amount: float
    status: str  # pending | success | failed
    created_at: int
    paid_at: int = None


def create_deposit(telegram_id: int, ref_id: str, amount: float) -> Deposit:
    return Deposit(
        telegram_id=telegram_id,
        ref_id=ref_id,
        amount=amount,
        status="pending",
        created_at=int(time.time()),
        paid_at=None
    )


def mark_success(deposit: Deposit):
    deposit.status = "success"
    deposit.paid_at = int(time.time())
    return deposit


def mark_failed(deposit: Deposit):
    deposit.status = "failed"
    return deposit


def is_valid_deposit(amount: float) -> bool:
    if amount <= 0:
        return False
    return True