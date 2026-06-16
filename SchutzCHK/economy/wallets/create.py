import time
import secrets
import string

from database.connection import execute


def generate_hash(length=24):
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def create_wallet(telegram_id: int):

    result = execute(
        "SELECT wallet_address FROM wallets WHERE telegram_id = ?",
        [telegram_id]
    )

    if result.rows:
        return {
            "status": "exists",
            "wallet": result.rows[0][0]
        }

    wallet_address = f"reich_{generate_hash(24)}"

    execute(
        "INSERT INTO wallets (telegram_id, wallet_address, created_at) VALUES (?, ?, ?)",
        [telegram_id, wallet_address, int(time.time())]
    )

    return {
        "status": "created",
        "wallet": wallet_address
    }