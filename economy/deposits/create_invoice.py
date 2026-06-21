import requests
import secrets
import string
import time
from services.gold_price import get_rsm_rate  # <-- IMPORT INI

DB_URL = "https://api.paymentkita.com/v1/order"
MERCHANT_ID = "PKM51558944"
SECRET = "23NnxZUVp4T1KvWtEAmRda2f86WqQam3bitXvWjdaEM"

def generate_ref_id():
    chars = string.ascii_uppercase + string.digits
    rand = ''.join(secrets.choice(chars) for _ in range(8))
    return f"REICHS-{rand}"

def create_invoice(telegram_id: int, nominal: float):
    # Ambil harga RSM terkini (mengikuti emas)
    rsm_rate, _, _ = get_rsm_rate()  # rsm_rate dalam IDR
    
    # Konversi RSM ke IDR
    nominal_idr = int(nominal * rsm_rate)
    
    # Pastikan minimal 100 IDR (biar gak ditolak PaymentKita)
    if nominal_idr < 100:
        nominal_idr = 100
    
    ref_id = generate_ref_id()
    
    params = {
        "merchant_id": MERCHANT_ID,
        "secret": SECRET,
        "ref_id": ref_id,
        "nominal": nominal_idr,
        "metode": "QRISREALTIME"
    }
    
    try:
        res = requests.get(DB_URL, params=params, timeout=30)
        data = res.json()
        
        if data.get("status") != "Success":
            return {
                "status": "failed",
                "reason": f"API error: {data.get('error_msg', data)}"
            }
        
        d = data.get("data", {})
        
        return {
            "status": "pending",
            "ref_id": d.get("reff_id", ref_id),
            "pay_url": d["pay_url"],
            "qr_link": d["qr_link"],
            "amount": nominal,
            "amount_idr": nominal_idr,  # tambahin biar tau konversi
            "rsm_rate": rsm_rate,      # tambahin rate yang dipake
            "expire": d["expired_at"]
        }
    except Exception as e:
        return {
            "status": "failed",
            "reason": str(e)
        }