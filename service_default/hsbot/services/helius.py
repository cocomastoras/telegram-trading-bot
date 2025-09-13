import os
import httpx

project_id = os.environ.get('GCLOUD_PROJECT')

HELIUS_RPC_URL = "https://mainnet.helius-rpc.com"
HELIUS_API_KEY = os.environ.get('HELIUS_API_KEY')

HEADERS = {
    "Content-Type": "application/json"
}
HELIUS_PARAMS = {
    'api-key': HELIUS_API_KEY
}


async def fetch_token_data(token_address: str):
    payload = {
        "jsonrpc": "2.0",
        "id": token_address,
        "method": "getAsset",
        "params": {"id": token_address},
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            HELIUS_RPC_URL,
            json=payload,
            headers=HEADERS,
            params=HELIUS_PARAMS
        )

    response.raise_for_status()

    return response.json()


async def get_token_metadata(token_address: str):
    response_json = await fetch_token_data(token_address)

    if 'result' in response_json:
        result = response_json['result']
        token_info = result['token_info']
        token_metadata = result['content']['metadata']
        token_links = result['content']['links']
        symbol = token_metadata.get('symbol') or token_info.get('symbol')
        return {
            'name': token_metadata.get('name'),
            'address': token_address,
            'icon': token_links.get('image'),
            'supply': token_info.get('supply'),  # lossless supply as integer
            'decimals': token_info.get('decimals'),
            'symbol': symbol,
            'token_program_id': token_info.get('token_program')
        }
    else:
        if 'error' in response_json and 'message' in response_json['error']:
            error_message = (f"Couldn't parse Helius getAsset response for token {token_address}. "
                             f"| Parsed error: {response_json['error']['message']}")
        else:
            error_message = (f"Couldn't parse Helius getAsset response for token {token_address}."
                             f" JSON response: {response_json}")

        raise ValueError(error_message)


async def get_tokens_supply(token_addresses: str):
    payload = {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "getAssetBatch",
      "params": {
        "ids": token_addresses
      }
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            HELIUS_RPC_URL,
            json=payload,
            headers=HEADERS,
            params=HELIUS_PARAMS
        )

    response.raise_for_status()
    try:
        response_result = response.json()['result']
    except Exception as e:
        logger.warning(f"Could not get tokens supply from Helius response"
                       f"Response status: {response.status_code}. Response text: {response.text}"
                       f"Exception: {e}"
                       )
        raise e

    supplies = {}

    for entry in response_result:
        supplies[entry['id']] = entry['token_info']['supply']

    return supplies


async def get_tokens_metadata(token_addresses: str):
    payload = {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "getAssetBatch",
      "params": {
        "ids": token_addresses
      }
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            HELIUS_RPC_URL,
            json=payload,
            headers=HEADERS,
            params=HELIUS_PARAMS
        )

    response.raise_for_status()
    try:
        response_result = response.json()['result']
    except Exception as e:
        logger.warning(f"Could not get tokens supply from Helius response"
                       f"Response status: {response.status_code}. Response text: {response.text}"
                       f"Exception: {e}"
                       )
        raise e

    tokens_metadata = {}

    for entry in response_result:
        token_info = entry['token_info']
        token_metadata = entry['content']['metadata']
        token_links = entry['content']['links']
        symbol = token_metadata.get('symbol') or token_info.get('symbol')
        metadata = {
            'name': token_metadata.get('name'),
            'address': entry['id'],
            'icon': token_links.get('image'),
            'supply': token_info.get('supply'),  # lossless supply as integer
            'decimals': token_info.get('decimals'),
            'symbol': symbol,
            'token_program_id': token_info.get('token_program')
        }
        tokens_metadata[entry['id']] = metadata

    return tokens_metadata
