from database.connection import execute


def run_audit():

    # 1. total balance
    bal = execute(
        "SELECT SUM(balance) FROM balances"
    )
    total_balance = bal.rows[0][0] or 0

    # 2. total reserve
    res = execute(
        "SELECT SUM(amount) FROM reserve"
    )
    total_reserve = res.rows[0][0] or 0

    # 3. ledger check (opsional integrity check)
    led = execute(
        "SELECT SUM(amount) FROM ledger"
    )
    ledger_total = led.rows[0][0] or 0

    # 4. expected system total
    system_total = total_balance + total_reserve

    return {
        "balance_total": total_balance,
        "reserve_total": total_reserve,
        "ledger_net": ledger_total,
        "system_total": system_total,
        "status": "ok" if system_total >= 0 else "warning"
    }