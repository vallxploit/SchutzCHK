import time
import requests

DB_URL = "https://api.paymentkita.com/v1/status"
MERCHANT_ID = "PKM51558944"
SECRET = "23NnxZUVp4T1KvWtEAmRda2f86WqQam3bitXvWjdaEM"

EXPIRED_CACHE = set()


def expire_invoice(ref_id: str):

    if ref_id in EXPIRED_CACHE:
        return {
            "status": "already_expired"
        }

    params = {
        "merchant_id": MERCHANT_ID,
        "secret": SECRET,
        "ref_id": ref_id
    }

    res = requests.get(DB_URL, params=params)
    data = res.json()

    if data.get("status") != "Success":
        return {
            "status": "error",
            "reason": "gateway error"
        }

    status = data["data"]["status"]
    expired_ts = data["data"]["expired_ts"]

    now = int(time.time())

    # kalau sudah lewat waktu
    if now > expired_ts and status == "Unpaid":
        EXPIRED_CACHE.add(ref_id)

        return {
            "status": "expired",
            "ref_id": ref_id
        }

    return {
        "status": "active",
        "ref_id": ref_id
    }