import re


WALLET_PATTERN = r"^reich_[a-f0-9]{24}$"


def is_valid_wallet_format(wallet_address: str) -> bool:
    """
    Validate wallet format:
    - must start with 'reich_'
    - must follow sha256 truncated (24 hex chars)
    """
    if not isinstance(wallet_address, str):
        return False

    return bool(re.match(WALLET_PATTERN, wallet_address))


def sanitize_wallet(wallet_address: str) -> str:
    """
    Clean input wallet string
    """
    if not wallet_address:
        return ""

    return wallet_address.strip().lower()


def validate_wallet(wallet_address: str) -> bool:
    """
    Full validation pipeline
    """
    wallet_address = sanitize_wallet(wallet_address)
    return is_valid_wallet_format(wallet_address)