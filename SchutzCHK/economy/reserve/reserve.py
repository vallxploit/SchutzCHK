import time
from database.connection import execute

def add_reserve(amount: float, source: str):
    execute("""
        INSERT INTO reserve (amount, source, created_at)
        VALUES (?, ?, ?)
    """, [amount, source, int(time.time())])

def get_total_reserve():
    result = execute("SELECT SUM(amount) FROM reserve")
    if not result.rows or result.rows[0][0] is None:
        return 0.0
    return float(result.rows[0][0])

def get_reserve_value():
    """Alias untuk kompatibilitas"""
    return get_total_reserve()
