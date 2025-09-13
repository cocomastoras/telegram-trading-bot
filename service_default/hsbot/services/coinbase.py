import decimal
import httpx


COINBASE_URL = "https://api.coinbase.com/v2"


async def get_sol_usd_price():
    url = f"{COINBASE_URL}/exchange-rates?currency=SOL"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url)

    payload = response.json().get("data", {})

    for target_currency, amount in payload.get("rates", {}).items():
        if target_currency == 'USD':
            return decimal.Decimal(amount)
