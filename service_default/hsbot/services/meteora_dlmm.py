import httpx
import threading
import time

API_URL = "https://dlmm-api.meteora.ag/"

HEADERS = {
    "Content-Type": "application/json"
}


class RateLimiter:
    def __init__(self, rate_limit: int, period: float):
        self.rate_limit = rate_limit
        self.period = period
        self.lock = threading.Lock()
        self.tokens = rate_limit
        self.last_check = time.time()

    def acquire(self):
        """Wait until a request can be made within rate limits."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_check

            # Refill tokens based on elapsed time
            if elapsed >= self.period:
                self.tokens = self.rate_limit
                self.last_check = now

            # If no tokens are available, wait for next slot
            if self.tokens == 0:
                sleep_time = self.period - elapsed
                if sleep_time > 0:
                    logger.info(f"Rate limiting request, sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
                self.tokens = self.rate_limit
                self.last_check = time.time()

            # Consume a token
            self.tokens -= 1


rate_limiter = RateLimiter(rate_limit=5, period=1)


async def get_meteora_dlmm_pair_address_price(pair_address: str):
    rate_limiter.acquire()

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{API_URL}pair/{pair_address}",
            headers=HEADERS
        )

    response.raise_for_status()

    res = response.json()

    if 'current_price' in res:
        return res['current_price']
