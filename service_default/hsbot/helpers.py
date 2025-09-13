import decimal
from hsbot.services.coinbase import get_sol_usd_price
from hsbot.services.sol_client import get_account_tokens_balances, get_native_balance
from hsbot.sol import fetch_multi_token_info
from hsbot.persistence_layer import store


async def get_portfolio(wallet_address: str, sol_price: decimal.Decimal = None) -> dict:
    if sol_price is None:
        sol_price = await get_sol_usd_price()

    native_balance = await get_native_balance(wallet_address)
    native_balance_usd_worth = native_balance * sol_price

    portfolio = {
        "native_token": native_balance,
        "native_token_usd_worth": native_balance_usd_worth,
        "tokens": {},
        "sol_worth": native_balance,
        "usd_worth": native_balance_usd_worth
    }

    token_accounts = await get_account_tokens_balances(wallet_address)

    if token_accounts:
        tokens_info = await fetch_multi_token_info(token_addresses=list(token_accounts.keys()))
        for token_address in token_accounts.keys():
            token_balance = decimal.Decimal(token_accounts[token_address]['balance'])
            token_sol_worth = token_balance * tokens_info[token_address]['price']
            token_usd_worth = token_sol_worth * sol_price
            token_price_usd = tokens_info[token_address]['price'] * sol_price
            token_fdv_usd = tokens_info[token_address]['fdv'] * sol_price
            token_liquidity_usd = tokens_info[token_address]['liquidity'] * sol_price

            portfolio['tokens'][token_address] = {
                'name': tokens_info[token_address]['name'],
                'symbol': tokens_info[token_address]['symbol'],
                'supply': tokens_info[token_address]['supply'],
                'decimals': tokens_info[token_address]['decimals'],
                'pair_address': tokens_info[token_address]['pair_address'],
                'token_price_usd': token_price_usd,
                'fdv_usd': token_fdv_usd,
                'liquidity_usd': token_liquidity_usd,
                'token_balance': token_balance,
                'token_balance_sol': token_sol_worth,
                'token_balance_usd': token_usd_worth
                }
            portfolio['sol_worth'] += token_sol_worth
            portfolio['usd_worth'] += token_usd_worth

    return portfolio


async def get_positions(wallet_address: str, sol_price: decimal.Decimal = None):
    positions = []

    token_accounts = await get_account_tokens_balances(wallet_address)
    if token_accounts:
        if sol_price is None:
            sol_price = await get_sol_usd_price()

        tokens_info = await fetch_multi_token_info(token_addresses=list(token_accounts.keys()))
        for token_address in token_accounts.keys():
            token_balance = decimal.Decimal(token_accounts[token_address]['balance'])
            token_sol_worth = token_balance * tokens_info[token_address]['price']
            token_usd_worth = token_sol_worth * sol_price
            token_price_usd = tokens_info[token_address]['price'] * sol_price
            token_fdv_usd = tokens_info[token_address]['fdv'] * sol_price
            token_liquidity_usd = tokens_info[token_address]['liquidity'] * sol_price

            positions.append(
                {
                    'token_address': token_address,
                    'name': tokens_info[token_address]['name'],
                    'symbol': tokens_info[token_address]['symbol'],
                    'supply': tokens_info[token_address]['supply'],
                    'decimals': tokens_info[token_address]['decimals'],
                    'pair_address': tokens_info[token_address]['pair_address'],
                    'token_price_usd': token_price_usd,
                    'fdv_usd': token_fdv_usd,
                    'liquidity_usd': token_liquidity_usd,
                    'token_balance': token_balance,
                    'token_balance_sol': token_sol_worth,
                    'token_balance_usd': token_usd_worth
                }
            )

    if positions:
        positions.sort(key=lambda x: x['token_balance_usd'], reverse=True)

    return positions


def sync_tokens_history(user_id, tokens: list):
    stored_tokens = store['users'][user_id]['tokens_history']

    for token in tokens:
        if token not in stored_tokens:
            stored_tokens[token] = {
                'amount_purchased_lossless': 0,
                'amount_sold_lossless': 0,
            }
    store.save()
