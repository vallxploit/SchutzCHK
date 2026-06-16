from dataclasses import dataclass
import time


@dataclass
class Reserve:
    total: float = 0.0
    updated_at: int = 0


def create_reserve(initial: float = 0.0) -> Reserve:
    return Reserve(
        total=initial,
        updated_at=int(time.time())
    )


def add_to_reserve(reserve: Reserve, amount: float):
    if amount < 0:
        return reserve

    reserve.total += amount
    reserve.updated_at = int(time.time())
    return reserve


def remove_from_reserve(reserve: Reserve, amount: float):
    if amount <= 0:
        return reserve

    if reserve.total < amount:
        return reserve  # prevent negative reserve

    reserve.total -= amount
    reserve.updated_at = int(time.time())
    return reserve


def get_reserve_value(reserve: Reserve) -> float:
    return round(reserve.total, 6)