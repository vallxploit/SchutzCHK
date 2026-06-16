import time
import hashlib
import secrets


def generate_txid(user_id: int, action: str, amount: float):
    raw = f"{user_id}-{action}-{amount}-{time.time()}-{secrets.token_hex(6)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def short_txid(txid: str):
    return txid[:12]