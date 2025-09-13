import solders.solders
from solana.rpc.async_api import AsyncClient, Pubkey
from solana.rpc.commitment import Commitment
from solana.rpc.types import TokenAccountOpts
from itertools import islice
import logging
import asyncio
import os
import decimal


SOLANA_PUBLICNODE_TOKEN = os.environ.get("SOLANA_PUBLICNODE_TOKEN")
PUBLICNODE_RPC_URL = f"https://solana-rpc.publicnode.com/{SOLANA_PUBLICNODE_TOKEN}"


def iterate_in_batches(iterable, batch_size):
    iterator = iter(iterable)
    for batch in iter(lambda: list(islice(iterator, batch_size)), []):
        yield batch


class SolanaAsyncClientFactory:
    """
    Factory class to cache existing async solana web3 clients in order to reduce resource usage.
    """
    _instances = {}

    @staticmethod
    def get_client(network_rpc_url: str = PUBLICNODE_RPC_URL, commitment: str = "confirmed"):
        instance_key = f"{network_rpc_url}:{commitment}"
        if instance_key not in SolanaAsyncClientFactory._instances:
            _client = AsyncClient(network_rpc_url, Commitment(commitment))
            SolanaAsyncClientFactory._instances[instance_key] = _client

        return SolanaAsyncClientFactory._instances[instance_key]


async def get_native_balance(wallet_address):
    if isinstance(wallet_address, str):
        wallet_address = Pubkey.from_string(wallet_address)

    solana_client = SolanaAsyncClientFactory.get_client()
    result = await solana_client.get_balance(wallet_address)
    # logging.info(f"Wallet {wallet_address} has native balance: {result.value}")
    return decimal.Decimal(result.value / 10 ** 9)


async def get_multiple_accounts(accounts: list):
    solana_client = SolanaAsyncClientFactory.get_client()
    accounts = [account if isinstance(account, Pubkey) else Pubkey.from_string(account) for account in accounts]
    result = await solana_client.get_multiple_accounts_json_parsed(accounts)
    return result.value


async def get_accounts_in_concurrent_batches(account_list):
    async def fetch_accounts_batch(batch_id: int, accounts_batch: list):
        multiple_accounts_response = await get_multiple_accounts(accounts_batch)

        multiple_accounts_data = tuple(
            (
                account.data.parsed['info']['tokenAmount']['uiAmount'],
                int(account.data.parsed['info']['tokenAmount']['decimals']),
            ) if account is not None else None
            for account in multiple_accounts_response
        )
        return {
            "batch_id": batch_id,
            "accounts_batch_response": multiple_accounts_data
        }

    tasks = [
        fetch_accounts_batch(index, batch)
        for index, batch in enumerate(iterate_in_batches(account_list, batch_size=100))
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [account for result in results if isinstance(result, dict) for account in result["accounts_batch_response"]]


async def get_account_tokens_balances(account):
    solana_client = SolanaAsyncClientFactory.get_client()
    token_programs_ids = (
        Pubkey.from_string('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'),
        Pubkey.from_string('TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb')
    )

    if isinstance(account, str):
        account = Pubkey.from_string(account)

    async def fetch_accounts_tokens(program_id: str):
        return await solana_client.get_token_accounts_by_owner_json_parsed(
            owner=account,
            opts=TokenAccountOpts(program_id=program_id)
        )

    tasks = [fetch_accounts_tokens(_id) for _id in token_programs_ids]
    results = await asyncio.gather(*tasks)
    tokens = {}
    for result in results:
        for entry in result.value:
            account_info = entry.account.data.parsed['info']
            tokens[account_info['mint']] = {
                "balance": account_info['tokenAmount']['uiAmountString'],
                "balance_lossless": account_info['tokenAmount']['amount']
            }
    return tokens


async def get_token_supply(token_address: str) -> solders.solders.UiTokenAmount:
    solana_client = SolanaAsyncClientFactory.get_client()

    try:
        if isinstance(token_address, str):
            token_address = Pubkey.from_string(token_address)

        result = await solana_client.get_token_supply(token_address)
        # logging.info(f"Token {token_address} has supply: {result.value}")
        return result.value
    except Exception as e:
        logging.error(f"Failed to get supply for token {token_address}: {e}")
