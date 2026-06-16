import time
import secrets
import string

from database.connection import execute

def generate_txid():
    chars = string.ascii_uppercase + string.digits
    return "TX-" + ''.join(
        secrets.choice(chars)
        for _ in range(12)
    )

def create_ledger_entry(
    user_id: int,
    tx_type: str,
    amount: float,
    balance_before: float,
    balance_after: float,
    description: str = ""
):
    txid = generate_txid()

    execute("""
        INSERT INTO ledger (
            txid,
            user_id,
            type,
            amount,
            balance_before,
            balance_after,
            description,
            timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        txid,
        user_id,
        tx_type,
        amount,
        balance_before,
        balance_after,
        description,
        int(time.time())
    ])

    return txid
