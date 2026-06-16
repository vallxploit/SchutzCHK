from dataclasses import dataclass
import time
import hashlib


@dataclass
class Wallet:
    telegram_id: int
    wallet_address: str
    created_at: int


def generate_wallet_address(telegram_id: int) -> str:
    raw = f"reich_{telegram_id}_{time.time()}"
    return "reich_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def create_wallet(telegram_id: int) -> Wallet:
    return Wallet(
        telegram_id=telegram_id,
        wallet_address=generate_wallet_address(telegram_id),
        created_at=int(time.time())
    )


def validate_wallet_address(address: str) -> bool:
    if not address.startswith("reich_"):
        return False
    if len(address) < 20:
        return False
    return True