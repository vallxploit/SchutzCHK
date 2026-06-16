import time
from economy.constitution.constitution import can_transfer
from economy.balances.manager import get_balance, add_balance, remove_balance
from economy.ledger.create import create_ledger_entry
from economy.reserve.reserve import add_reserve

FEE_RATE = 0.01
MIN_TRANSFER = 0.1

def transfer(sender_id: int, receiver_id: int, amount: float):
    if amount <= 0:
        return {"status": "failed", "reason": "invalid amount"}

    if amount < MIN_TRANSFER:
        return {"status": "failed", "reason": "below minimum transfer"}

    sender_balance = get_balance(sender_id)
    receiver_balance = get_balance(receiver_id)

    ok, reason = can_transfer(sender_balance, amount)
    if not ok:
        return {"status": "failed", "reason": reason}

    fee = round(amount * FEE_RATE, 6)
    total_deduct = round(amount + fee, 6)

    if sender_balance < total_deduct:
        return {"status": "failed", "reason": "insufficient balance"}

    sender_before = sender_balance
    receiver_before = receiver_balance

    remove_balance(sender_id, total_deduct)
    add_balance(receiver_id, amount)

    sender_after = get_balance(sender_id)
    receiver_after = get_balance(receiver_id)

    tx_out = create_ledger_entry(
        sender_id,
        "TRANSFER_OUT",
        -amount,
        sender_before,
        sender_after,
        f"Transfer to {receiver_id}"
    )

    tx_in = create_ledger_entry(
        receiver_id,
        "TRANSFER_IN",
        amount,
        receiver_before,
        receiver_after,
        f"Transfer from {sender_id}"
    )

    tx_fee = create_ledger_entry(
        sender_id,
        "TRANSFER_FEE",
        -fee,
        sender_after,
        sender_after,
        "Network fee 1%"
    )

    # ✅ FEE MASUK RESERVE
    add_reserve(fee, f"transfer_fee_{sender_id}_{receiver_id}")

    return {
        "status": "success",
        "amount": amount,
        "fee": fee,
        "total_deducted": total_deduct,
        "tx": {
            "out": tx_out,
            "in": tx_in,
            "fee": tx_fee
        }
    }
