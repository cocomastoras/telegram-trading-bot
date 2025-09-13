import string
import random
from hsbot.persistence_layer import store
import logging
import math
from hsbot.services.sol_client import get_token_supply

leading_zeros_to_unicode = {
    0: '\u2080',
    1: '\u2081',
    2: '\u2082',
    3: '\u2083',
    4: '\u2084',
    5: '\u2085',
    6: '\u2086',
    7: '\u2087',
    8: '\u2088',
    9: '\u2089'
}


def parse_number(input_num) -> str:
    if input_num > 1000000000:
        return str(round(input_num / 1000000000, 2)) + "B"
    elif input_num > 1000000:
        return str(round(input_num / 1000000, 2)) + "M"
    elif input_num > 1000:
        return str(round(input_num / 1000, 2)) + "K"
    else:
        return str(input_num)


def compact_value_display(num: float):
    str_num = f"{num:.20f}".lstrip("0.")
    leading_zeros = len(f"{num:.20f}".split(".")[1]) - len(str_num)
    next_digits = str_num[:3]
    return f"0.0{leading_zeros_to_unicode[leading_zeros]}{str(next_digits)}"


def generate_referral_code(length=6) -> str | None:
    characters = string.ascii_uppercase + string.digits
    max_tries = 5

    for attempt in range(max_tries):
        random_code = ''.join(random.choice(characters) for _ in range(length))
        referral_code_exists = store.get('referral_codes_to_users', {}).get(random_code)
        if not referral_code_exists:
            logging.info(f"Generated referral code: {random_code}")
            return random_code
        logging.debug(f"Attempt {attempt + 1}: Referral code {random_code} already exists.")
    else:
        raise ValueError("Could not create referral code.")


class IterablePaginator:
    def __init__(self, page_size=20):
        self.page_size = page_size

    def get_max_page_num(self, iterable):
        return math.ceil(len(iterable) / self.page_size)

    def get_page_list(self, data, page):
        offset = (page - 1) * self.page_size
        end = offset + self.page_size
        return data[offset:end]


async def verify_address(address: str):
    verified = False
    try:
        supply_response = await get_token_supply(token_address=address)
        if supply_response is not None:
            verified = True
        else:
            logging.info(f"getTokenSupply failed for address {address},not a valid token, rejecting.")
    except Exception as e:
        logging.warning(f"Error while verifying address {address}: {e}")

    return verified
