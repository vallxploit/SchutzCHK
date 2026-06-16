import time
from database.connection import execute, fetch_one
from economy.constitution.constitution import can_deposit
from economy.balances.manager import add_balance, get_balance
from economy.ledger.create import create_ledger_entry

def is_already_claimed(ref_id: str):
    result = fetch_one("SELECT 1 FROM claimed_deposits WHERE ref_id = ?", [ref_id])
    return result is not None

def mark_as_claimed(ref_id: str, user_id: int, amount: float):
    execute("""
        INSERT INTO claimed_deposits (ref_id, user_id, amount, claimed_at) 
        VALUES (?, ?, ?, ?)
    """, [ref_id, user_id, amount, int(time.time())])

def verify_payment(ref_id: str, user_id: int, amount: float):
    if is_already_claimed(ref_id):
        return {"status": "already_claimed", "message": "Payment already redeemed"}
    
    ok, reason = can_deposit(amount)
    if not ok:
        return {"status": "rejected", "reason": reason}
    
    before = get_balance(user_id)
    new_balance = add_balance(user_id, amount)
    
    create_ledger_entry(
        user_id,
        "DEPOSIT",
        amount,
        before,
        new_balance,
        f"Deposit via {ref_id}"
    )
    
    mark_as_claimed(ref_id, user_id, amount)
    
    return {
        "status": "success",
        "new_balance": new_balance,
        "amount_added": amount
    }
