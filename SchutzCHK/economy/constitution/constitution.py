import time

# =========================
# ECONOMIC CONSTITUTION
# SCHUTZ CHK RSM SYSTEM
# =========================

CONFIG = {
    "MIN_TRANSFER": 0.1,
    "TRANSFER_FEE_RATE": 0.01,
    "MIN_DEPOSIT": 0.001,
    "MAX_DAILY_TRANSFER": None,  # nanti bisa kamu isi limit
    "ALLOW_NEGATIVE": True,
    "ROOT_ID": 6929963557,  # isi telegram_id root kalau mau immutable access
}


# =========================
# USER TIER SYSTEM
# =========================

def get_user_tier(telegram_id: int, is_root: bool = False):
    if is_root or telegram_id == CONFIG["ROOT_ID"]:
        return "ROOT"

    return "USER"


# =========================
# RULE CHECKER
# =========================

def can_transfer(sender_balance: float, amount: float):
    if amount < CONFIG["MIN_TRANSFER"]:
        return False, "Below minimum transfer"

    total = amount + (amount * CONFIG["TRANSFER_FEE_RATE"])

    if sender_balance < total:
        return False, "Insufficient balance"

    return True, "OK"


def can_deposit(amount: float):
    if amount < CONFIG["MIN_DEPOSIT"]:
        return False, "Below minimum deposit"

    return True, "OK"


# =========================
# ACCOUNT STATE RULE
# =========================

def is_account_locked(balance: float):
    if CONFIG["ALLOW_NEGATIVE"]:
        return False

    return balance < 0


# =========================
# AUDIT HOOK (OPTIONAL)
# =========================

def log_rule_check(action: str, result: bool, reason: str = ""):
    return {
        "action": action,
        "allowed": result,
        "reason": reason,
        "timestamp": int(time.time())
    }