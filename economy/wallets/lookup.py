from database.connection import execute


def get_wallet_by_telegram_id(telegram_id: int):
    result = execute(
        """
        SELECT telegram_id, wallet_address, created_at
        FROM wallets
        WHERE telegram_id = ?
        """,
        [telegram_id]
    )

    if not result.rows:
        return None

    row = result.rows[0]

    return {
        "telegram_id": row[0],
        "wallet_address": row[1],
        "created_at": row[2]
    }


def get_telegram_id_by_wallet(wallet_address: str):
    result = execute(
        """
        SELECT telegram_id
        FROM wallets
        WHERE wallet_address = ?
        """,
        [wallet_address]
    )

    if not result.rows:
        return None

    return result.rows[0][0]


def wallet_exists(telegram_id: int) -> bool:
    result = execute(
        """
        SELECT 1
        FROM wallets
        WHERE telegram_id = ?
        """,
        [telegram_id]
    )

    return bool(result.rows)