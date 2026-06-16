import time

from database.connection import execute


def get_balance(telegram_id: int):
    result = execute(
        "SELECT balance FROM balances WHERE telegram_id = ?",
        [telegram_id]
    )

    if not result.rows:
        return 0.0

    return float(result.rows[0][0])


def set_balance(telegram_id: int, amount: float):
    execute("""
        INSERT INTO balances (telegram_id, balance, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id)
        DO UPDATE SET balance = excluded.balance,
                      updated_at = excluded.updated_at
    """, [telegram_id, amount, int(time.time())])


def add_balance(telegram_id: int, amount: float):
    current = get_balance(telegram_id)
    new_balance = round(current + amount, 6)
    set_balance(telegram_id, new_balance)
    return new_balance


def remove_balance(telegram_id: int, amount: float):
    current = get_balance(telegram_id)
    new_balance = round(current - amount, 6)
    set_balance(telegram_id, new_balance)
    return new_balance


def is_negative(telegram_id: int):
    return get_balance(telegram_id) < 0