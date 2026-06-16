from dataclasses import dataclass
import time


@dataclass
class LedgerEntry:
    user_id: int
    type: str
    amount: float
    balance_before: float
    balance_after: float
    description: str
    timestamp: int


def create_ledger_object(
    user_id: int,
    type: str,
    amount: float,
    balance_before: float,
    balance_after: float,
    description: str
) -> LedgerEntry:

    return LedgerEntry(
        user_id=user_id,
        type=type,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        description=description,
        timestamp=int(time.time())
    )


def validate_ledger(entry: LedgerEntry) -> bool:
    if entry.user_id is None:
        return False
    if entry.type == "":
        return False
    if entry.balance_after is None:
        return False
    return True