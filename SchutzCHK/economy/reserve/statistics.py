from database.connection import fetch_all
from economy.reserve.reserve import get_total_reserve

def get_reserve_statistics():
    # Ambil semua fee dari ledger
    rows = fetch_all("""
        SELECT amount FROM ledger 
        WHERE type = 'TRANSFER_FEE'
    """)
    
    total_fee = 0.0
    for row in rows:
        amount = row[0]
        # amount biasanya negatif (-0.01), jadi kita ambil absolutnya
        try:
            total_fee += abs(float(amount))
        except (ValueError, TypeError):
            continue
    
    reserve = get_total_reserve()
    
    # Hitung jumlah transaksi fee
    count_rows = fetch_all("SELECT COUNT(*) FROM ledger WHERE type = 'TRANSFER_FEE'")
    fee_count = count_rows[0][0] if count_rows else 0
    
    return {
        "total_reserve": reserve,
        "total_fees_collected": round(total_fee, 6),
        "fee_transactions": fee_count
    }
