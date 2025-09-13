import decimal
import logging
from typing import Dict, List
import httpx
import os
from enum import Enum
from datetime import datetime, timedelta, UTC
from .meteora_dlmm import get_meteora_dlmm_pair_address_price
from .sol_client import get_accounts_in_concurrent_batches


SHYFT_API_KEY = os.environ.get('SHYFT_API_KEY')
SHYFT_GRAPHQL_URL = "https://programs.shyft.to/v0/graphql"

SOL_NATIVE_ADDRESS = "So11111111111111111111111111111111111111112"

HEADERS = {
    "Content-Type": "application/json"
}
SHYFT_PARAMS = {
    'api_key': SHYFT_API_KEY
}


class Protocols(Enum):
    RAYDIUM_V4 = "Raydium_V4"
    RAYDIUM_CLMM = "Raydium_CLMM"
    WHIRLPOOL = "Whirlpool"
    METEORA_AMM = "Meteora_AMM"
    METEORA_DLMM = "Meteora_DLMM"


async def get_pools_by_token(tokens: str | List[str]) -> Dict[str, List[Dict]]:

    pool_last_updated_at = (datetime.now(tz=UTC) - timedelta(seconds=60 * 60 * 24)).isoformat()

    if isinstance(tokens, str):
        tokens = [tokens]

    query = """
        query MyCombinedQuery(
            $raydium_v4_where: Raydium_LiquidityPoolv4_bool_exp,
            $raydium_clmm_where: RAYDIUM_CLMM_PoolState_bool_exp, 
            $whirlpool_where: ORCA_WHIRLPOOLS_whirlpool_bool_exp,
            $meteora_amm_where: meteora_amm_pool_bool_exp,
            $meteora_dlmm_where: meteora_dlmm_LbPair_bool_exp
            ){
              raydium_v4_data: Raydium_LiquidityPoolv4(where: $raydium_v4_where) {
                base_mint: baseMint
                quote_mint: quoteMint
                base_vault: baseVault
                quote_vault: quoteVault
                pub_key: pubkey
              }
              raydium_clmm_data: RAYDIUM_CLMM_PoolState(where: $raydium_clmm_where) {
                base_mint: tokenMint0,
                quote_mint: tokenMint1,
                base_vault: tokenVault0,
                quote_vault: tokenVault1,
                sqrt_price: sqrtPriceX64,
                pub_key: pubkey
              }
              whirlpool_data: ORCA_WHIRLPOOLS_whirlpool(where: $whirlpool_where) {
                base_mint: tokenMintA
                quote_mint: tokenMintB
                base_vault: tokenVaultA
                quote_vault: tokenVaultB
                pub_key: pubkey
                sqrt_price: sqrtPrice
              }
              meteora_amm_data: meteora_amm_pool(where: $meteora_amm_where){
                base_mint: tokenAMint,
                quote_mint: tokenBMint,
                base_vault: aVaultLp,
                quote_vault: bVaultLp,
                pub_key: pubkey
              }
              meteora_dlmm_data: meteora_dlmm_LbPair(where: $meteora_dlmm_where){
                base_mint: tokenXMint,
                quote_mint: tokenYMint,
                base_vault: reserveX,
                quote_vault: reserveY,
                pub_key: pubkey
              }
            }
        """

    variables = {
        "raydium_v4_where": {
            "_or": [
                {
                    "_and": [
                        {"baseMint": {"_in": tokens}},
                        {"quoteMint": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                },
                {
                    "_and": [
                        {"quoteMint": {"_in": tokens}},
                        {"baseMint": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                }
            ],
            "_updatedAt": {"_gt": pool_last_updated_at}
        },
        "raydium_clmm_where": {
            "liquidity": {"_gt": "0"},
            "_or": [
                {
                    "_and": [
                        {"tokenMint0": {"_in": tokens}},
                        {"tokenMint1": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                },
                {
                    "_and": [
                        {"tokenMint1": {"_in": tokens}},
                        {"tokenMint0": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                }
            ],
            "_updatedAt": {"_gt": pool_last_updated_at}
        },
        "whirlpool_where": {
            "liquidity": {"_gt": "0"},
            "_or": [
                {
                    "_and": [
                        {"tokenMintA": {"_in": tokens}},
                        {"tokenMintB": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                },
                {
                    "_and": [
                        {"tokenMintB": {"_in": tokens}},
                        {"tokenMintA": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                }
            ],
            "_updatedAt": {"_gt": pool_last_updated_at}
        },
        "meteora_amm_where": {
            "_or": [
                {
                    "_and": [
                        {"tokenAMint": {"_in": tokens}},
                        {"tokenBMint": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                },
                {
                    "_and": [
                        {"tokenBMint": {"_in": tokens}},
                        {"tokenAMint": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                }
            ],
            "_updatedAt": {"_gt": pool_last_updated_at}
        },
        "meteora_dlmm_where": {
            "_or": [
                {
                    "_and": [
                        {"tokenXMint": {"_in": tokens}},
                        {"tokenYMint": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                },
                {
                    "_and": [
                        {"tokenYMint": {"_in": tokens}},
                        {"tokenXMint": {"_eq": SOL_NATIVE_ADDRESS}}
                    ]
                }
            ],
            "_updatedAt": {"_gt": pool_last_updated_at}
        }
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            SHYFT_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers=HEADERS,
            params=SHYFT_PARAMS
        )

    data = response.json()['data']

    pools_by_token = {
        token: []
        for token in tokens
    }

    # specific order to parse response to keep more dominant protocols
    # on top in order to save some iterations later on in finding
    # most dominant pool
    protocol_keys_map = (
        ('raydium_v4_data', Protocols.RAYDIUM_V4.value,),
        ('whirlpool_data', Protocols.WHIRLPOOL.value,),
        ('raydium_clmm_data', Protocols.RAYDIUM_CLMM.value,),
        ('meteora_dlmm_data', Protocols.METEORA_DLMM.value,),
        ('meteora_amm_data', Protocols.METEORA_AMM.value,)
    )

    for protocol_key_map in protocol_keys_map:
        pools = data[protocol_key_map[0]]
        protocol_key = protocol_key_map[1]

        for pool in pools:
            pool['protocol'] = protocol_key

            if pool['base_mint'] in tokens:
                pools_by_token[pool['base_mint']].append(pool)
            if pool['quote_mint'] in tokens:
                pools_by_token[pool['quote_mint']].append(pool)

    del variables
    del tokens
    del response
    del data

    return pools_by_token


async def get_dominant_pool_info_per_token(pools_by_token: Dict[str, List[Dict]]):
    accounts = []
    accounts_token_offsets = {}

    for token_address, pools in pools_by_token.items():
        accounts_token_offsets[token_address] = len(accounts)

        for pool in pools:
            accounts.extend(
                [
                    pool['base_vault'],
                    pool['quote_vault']
                ]
            )

    accounts_response = await get_accounts_in_concurrent_batches(account_list=accounts)

    assert len(accounts) == len(accounts_response)

    info = {
        token_address: {}
        for token_address in pools_by_token.keys()
    }

    for token_address, pools in pools_by_token.items():
        pool_max_native_amount = None

        account_token_offset = accounts_token_offsets[token_address]
        account_response = accounts_response[account_token_offset:account_token_offset + len(pools) * 2]

        for index, pool in enumerate(pools):
            if pool['base_mint'] == SOL_NATIVE_ADDRESS:
                native_token = pool['base_mint']
                token = pool['quote_mint']
                native_and_token_indexes = (index * 2, index * 2 + 1)
            else:
                native_token = pool['quote_mint']
                token = pool['base_mint']
                native_and_token_indexes = (index * 2 + 1, index * 2)

            # Skip the pool if either of the accounts is None;
            # it means the pool is uninitialized.
            if account_response[native_and_token_indexes[0]] is None or account_response[native_and_token_indexes[1]] is None:
                continue

            native_token_amount = account_response[native_and_token_indexes[0]][0]

            # if this is a pool with less native amount
            # than an already listed, then ignore quickly and discard
            if pool_max_native_amount is not None and native_token_amount <= pool_max_native_amount:
                continue

            token_amount = account_response[native_and_token_indexes[1]][0]
            token_decimals = account_response[native_and_token_indexes[1]][1]

            native_token_amount_decimal = decimal.Decimal(native_token_amount)
            token_amount_decimal = decimal.Decimal(token_amount)
            token_decimals_decimal = decimal.Decimal(token_decimals)

            if pool['protocol'] in (Protocols.RAYDIUM_V4.value, Protocols.METEORA_AMM.value,):
                token_price_decimal = (native_token_amount_decimal/token_amount_decimal) if token_amount_decimal else 0
                total_liquidity = native_token_amount_decimal * 2
            elif pool['protocol'] in (Protocols.RAYDIUM_CLMM.value, Protocols.WHIRLPOOL.value,):
                sqrt_price_decimal = decimal.Decimal(pool['sqrt_price'])
                token_price_decimal = (1/((sqrt_price_decimal / (2 ** 64)) ** 2)) * ((10 ** token_decimals_decimal) / 10 ** 9)
                total_liquidity = native_token_amount_decimal + token_amount_decimal * token_price_decimal
            elif pool['protocol'] == Protocols.METEORA_DLMM.value:
                token_price = await get_meteora_dlmm_pair_address_price(pair_address=pool['pub_key'])
                if token_price is None:
                    continue
                token_price_decimal = decimal.Decimal(token_price)
                total_liquidity = native_token_amount_decimal + token_amount_decimal * token_price_decimal
            else:
                logging.error(f"Protocol {pool['protocol']} not supported, ignoring")
                continue

            token_pool_info = {
                "token": token,
                "pub_key": pool['pub_key'],
                "protocol": pool['protocol'],
                "native_token_address": native_token,
                "native_token_amount": native_token_amount_decimal,
                "total_liquidity": total_liquidity,
                "token_price": token_price_decimal,
                "token_decimals": token_decimals
            }

            info[token_address] = token_pool_info

            # Keep track of the pool with the largest native token amount to discard easily other pools later on
            pool_max_native_amount = native_token_amount

    del accounts
    del accounts_token_offsets
    del accounts_response

    return info
