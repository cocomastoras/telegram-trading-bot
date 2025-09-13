from typing import List
import logging
import decimal
from hsbot.services.shyft import get_pools_by_token, get_dominant_pool_info_per_token
from hsbot.services.helius import get_token_metadata, get_tokens_metadata


async def fetch_single_token_info(token_address: str, allow_partial_svm_tokens=False) -> dict:
    """
        Returns a single token's information.

        :param token_address: The address of the token we want to get its information
        :param allow_partial_svm_tokens: Allow SVM tokens with no returned pools to be stored with basic metadata
        :return: dict
               - name
               - address
               - symbol
               - decimals
               - icon
               - supply
               - pair_address
               - pair_protocol
               - liquidity
               - price
               - fdv
        """

    try:
        # 'name', 'address', 'icon', 'supply', 'decimals', 'symbol'
        token_info = await get_token_metadata(token_address)
        pools_by_token = await get_pools_by_token(token_address)
    except Exception as e:
        logging.exception(f'Failed to fetch info for svm token {token_address}: {str(e)}')
        raise ValueError(e)

    pool_info_per_token = await get_dominant_pool_info_per_token(pools_by_token=pools_by_token)
    token_pool_info = pool_info_per_token[token_address]

    if not token_pool_info and not allow_partial_svm_tokens:
        raise ValueError(2)

    decimals = decimal.Decimal(token_info.get('decimals'))
    supply = decimal.Decimal(token_info.get('supply'))
    price: decimal.Decimal = token_pool_info.get('token_price', decimal.Decimal(0))

    fdv: decimal.Decimal = price * (supply / 10 ** decimals)

    token_info.update(
        {
            'pair_address': token_pool_info.get('pub_key'),
            'pair_protocol': token_pool_info.get('protocol'),
            'liquidity': token_pool_info.get('total_liquidity', 0),
            'fdv': fdv,
            'price': price
        }
    )

    return token_info


async def fetch_multi_token_info(token_addresses: List[str], allow_partial_svm_tokens=False) -> dict:
    """
        Returns multi token's information.

        :param token_addresses: A list of token addresses we want to get its informations
        :param allow_partial_svm_tokens: Allow SVM tokens with no returned pools to be stored with basic metadata
        :return: dict
               - name
               - address
               - symbol
               - decimals
               - icon
               - supply
               - pair_address
               - pair_protocol
               - liquidity
               - price
               - fdv
        """

    try:
        # 'name', 'address', 'icon', 'supply', 'decimals', 'symbol'
        tokens_info = await get_tokens_metadata(token_addresses)
        pools_by_token = await get_pools_by_token(token_addresses)
    except Exception as e:
        logging.exception(f'Failed to fetch info for svm tokens {token_addresses}: {str(e)}')
        raise ValueError(e)

    pool_info_per_token = await get_dominant_pool_info_per_token(pools_by_token=pools_by_token)

    for ta in token_addresses:
        token_pool_info = pool_info_per_token[ta]
        if not token_pool_info and not allow_partial_svm_tokens:
            raise ValueError(2)

        decimals = decimal.Decimal(tokens_info[ta].get('decimals'))
        supply = decimal.Decimal(tokens_info[ta].get('supply'))
        price: decimal.Decimal = token_pool_info.get('token_price', decimal.Decimal(0))
        fdv: decimal.Decimal = price * (supply / 10 ** decimals)

        tokens_info[ta].update(
            {
                'pair_address': token_pool_info.get('pub_key'),
                'pair_protocol': token_pool_info.get('protocol'),
                'liquidity': token_pool_info.get('total_liquidity', 0),
                'fdv': fdv,
                'price': price
            }
        )
    return tokens_info
