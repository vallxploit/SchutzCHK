import requests

DB_URL = "https://api.paymentkita.com/v1/status"
MERCHANT_ID = "PKM51558944"
SECRET = "23NnxZUVp4T1KvWtEAmRda2f86WqQam3bitXvWjdaEM"

def check_status(ref_id: str):
    params = {
        "merchant_id": MERCHANT_ID,
        "secret": SECRET,
        "ref_id": ref_id
    }
    
    try:
        res = requests.get(DB_URL, params=params, timeout=10)
        data = res.json()
        
        if data.get("status") != "Success":
            return {
                "status": "error",
                "reason": "gateway error"
            }
        
        payment_status = data["data"]["status"]
        
        return {
            "status": payment_status.lower(),
            "ref_id": ref_id,
            "amount": float(data["data"]["total_bayar"]) / 10000,  # konversi ke RSM
            "paid": float(data["data"]["total_diterima"])
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
