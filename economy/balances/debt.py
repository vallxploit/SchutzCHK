from dataclasses import dataclass
import time


MAX_DEBT = -8.0  # batas minimum saldo (bisa kamu adjust)


@dataclass
class DebtAccount:
    telegram_id: int
    debt_amount: float = 0.0
    frozen: bool = False
    updated_at: int = 0


def apply_debt(balance: float, amount: float) -> float:
    """
    Apply negative balance safely
    """
    return balance - amount


def check_debt_limit(new_balance: float) -> bool:
    """
    Return False if user exceed debt limit
    """
    return new_balance >= MAX_DEBT


def freeze_account(account: DebtAccount):
    account.frozen = True
    account.updated_at = int(time.time())
    return account


def unfreeze_account(account: DebtAccount):
    account.frozen = False
    account.updated_at = int(time.time())
    return account


def update_debt(account: DebtAccount, new_balance: float):
    account.debt_amount = new_balance
    account.updated_at = int(time.time())
    return account