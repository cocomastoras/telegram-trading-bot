from enum import Enum
import httpx

JUPITER_API_BASE_URL = "https://api.jup.ag/swap/v1"
SOL_NATIVE_ADDRESS = "So11111111111111111111111111111111111111112"

HEADERS = {
        "Content-Type": "application/json"
}


class SwapType(Enum):
    BUY_TOKEN = 1
    SELL_TOKEN = 2


async def get_jupiter_quote(swap_type: SwapType, mint_address: str, mint_amount: int, slippage_bps: int,
                            platform_fee_bps: int = 100, max_accounts: int = 50) -> dict:

    if swap_type == SwapType.BUY_TOKEN:
        input_mint = SOL_NATIVE_ADDRESS
        output_mint = mint_address
    else:
        input_mint = mint_address
        output_mint = SOL_NATIVE_ADDRESS

    params = {
        'inputMint': input_mint,
        'outputMint': output_mint,
        'amount': mint_amount,
        'slippageBps': slippage_bps,
        'maxAccounts': max_accounts,
        'onlyDirectRoutes': 'true'
    }

    if swap_type == SwapType.SELL_TOKEN:
        params.update(
            {
                'platformFeeBps': platform_fee_bps
            }
        )

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{JUPITER_API_BASE_URL}/quote",
            headers=HEADERS,
            params=params
        )

    response.raise_for_status()

    return response.json()


async def jupiter_swap(jupiter_quote: dict, wallet_address: str, swap_priority_fees: int,
                       fees_account_address: str = None) -> dict:

    payload = {
        'quoteResponse': jupiter_quote,
        'userPublicKey': wallet_address,
        'prioritizationFeeLamports': swap_priority_fees,
        'wrapAndUnwrapSol': True
    }

    if fees_account_address:
        payload.update(
            {
                'feeAccount': fees_account_address
            }
        )

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{JUPITER_API_BASE_URL}/swap",
            json=payload,
            headers=HEADERS
        )

    response.raise_for_status()

    return response.json()

