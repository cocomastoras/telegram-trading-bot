from datetime import datetime
from enum import Enum
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class CallbackData(Enum):
    START_ROUTES = "0"
    EXPORT = "1"
    BUY = "2"
    SELL = "3"
    WALLET = "4"
    SETTINGS = "5"
    BUY_1 = "6"
    BUY_2 = "7"
    REFRESH_TOKEN = "8"
    START = "9"
    PRIORITY = "10"
    SLIPPAGE = "11"
    SLIPPAGE_TOKEN_INFO = "12"
    SELL_1 = "13"
    SELL_2 = "14"
    WITHDRAW_ALL = "15"
    WITHDRAW_X = "16"
    DELETE = "17"
    NOTHING = "18"
    INIT = "19"
    START_REFRESH = "20"
    SOON = "21"
    BACK = "22"
    BUY_FIRST = "23"
    BUY_SECOND = "24"
    BUY_CUSTOM = "25"
    SELL_BACK = "26"
    POSITIONS = "27"
    POSITIONS_BACK = "28"
    NEXT = "29"
    PREV = "30"
    SELL_REFRESH = "31"
    REFERRAL = "32"
    HELP = "33"
    POSITIONS_REFRESH = "34"


class PendingInputState(Enum):
    UPDATE_PRIORITY = "update_priority"
    UPDATE_SLIPPAGE = "update_slippage"
    UPDATE_BUY_RIGHT_PRESET = "update_buy_right_preset"
    UPDATE_BUY_LEFT_PRESET = "update_buy_left_preset"
    UPDATE_SELL_LEFT_PRESET = "update_sell_left_preset"
    UPDATE_SELL_RIGHT_PRESET = "update_sell_right_preset"
    WITHDRAW_ALL_RECIPIENT = "withdraw_all_recipient"
    WITHDRAW_X_RECIPIENT = "withdraw_x_recipient"
    WITHDRAW_X_AMOUNT = "withdraw_x_amount"
    BUY_CONTRACT_ADDRESS = "buy_contract_address"
    BUY_CUSTOM_AMOUNT = "buy_custom_amount"


# unique flavors of dialog flows
class Dialog(Enum):
    BUY_CUSTOM = "buy_custom"
    WITHDRAW_ALL = "withdraw_all"
    WITHDRAW_CUSTOM = "withdraw_custom"


def root_keyboard():
    return [
        [
            InlineKeyboardButton("Buy", callback_data=CallbackData.BUY.value),
            InlineKeyboardButton("Sell", callback_data=CallbackData.SELL.value),
        ],
        [
            InlineKeyboardButton("Positions", callback_data=CallbackData.POSITIONS.value),
        ],
        [
            InlineKeyboardButton("Referrals", callback_data=CallbackData.REFERRAL.value),
            InlineKeyboardButton("Daily Spin", callback_data=CallbackData.SOON.value),
        ],
        [
            InlineKeyboardButton("Wallet", callback_data=CallbackData.WALLET.value),
            InlineKeyboardButton("Settings", callback_data=CallbackData.SETTINGS.value),
            InlineKeyboardButton("Help", callback_data=CallbackData.HELP.value),
        ],
        [
            InlineKeyboardButton("Close", callback_data=CallbackData.DELETE.value),
            InlineKeyboardButton("Refresh", callback_data=CallbackData.START_REFRESH.value),
        ],
    ]


def generate_token_keyboard(settings_dic, sell_initial=False, parent=CallbackData.BACK.value):
    buy_buttons = [
        InlineKeyboardButton(f"{settings_dic['buy_1']} SOL", callback_data=CallbackData.BUY_FIRST.value),
        InlineKeyboardButton(f"{settings_dic['buy_2']} SOL", callback_data=CallbackData.BUY_SECOND.value),
        InlineKeyboardButton("BUY X SOL", callback_data=CallbackData.BUY_CUSTOM.value),
    ]

    if sell_initial:
        sell_buttons = [
            InlineKeyboardButton("Sell Initial", callback_data=CallbackData.NOTHING.value),
            InlineKeyboardButton("Sell 100%", callback_data=CallbackData.NOTHING.value),
            InlineKeyboardButton("Sell X %", callback_data=CallbackData.NOTHING.value),
        ]
    else:
        sell_buttons = [
            InlineKeyboardButton(f"{settings_dic['sell_1']} %", callback_data=CallbackData.NOTHING.value),
            InlineKeyboardButton(f"{settings_dic['sell_2']} %", callback_data=CallbackData.NOTHING.value),
            InlineKeyboardButton("SELL %", callback_data=CallbackData.NOTHING.value),
        ]

    slippage_buttons = [
        InlineKeyboardButton(f"{settings_dic['slippage']}% Slippage ✅", callback_data=CallbackData.NOTHING.value),
        InlineKeyboardButton("X Slippage", callback_data=CallbackData.SLIPPAGE_TOKEN_INFO.value),
    ]

    back_button = {
        CallbackData.BACK.value: InlineKeyboardButton("BACK", callback_data=CallbackData.BACK.value),
        CallbackData.SELL_BACK.value: InlineKeyboardButton("BACK", callback_data=CallbackData.SELL_BACK.value),
        CallbackData.POSITIONS_BACK.value: InlineKeyboardButton("BACK", callback_data=CallbackData.POSITIONS_BACK.value)
    }

    refresh_button = InlineKeyboardButton("REFRESH", callback_data=CallbackData.REFRESH_TOKEN.value)

    return InlineKeyboardMarkup([
        buy_buttons,
        sell_buttons,
        slippage_buttons,
        [
            back_button[parent],
            refresh_button
        ]
    ])


def portfolio_overview_reply_text(wallet_address, native_balance, native_balance_usd,
                                  portfolio_balance_sol, portfolio_balance_usd, welcome):
    _now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    _reply_text = (
        f"{'<b>Welcome to LALABA!</b> \n\n' if welcome else ''}"
        "Your Solana wallet address is: \n\n"
        f"<code>{wallet_address}</code> \n\n"
        f"Balance: {round(native_balance, 5)} SOL (USD ${round(native_balance_usd, 2)}) \n"
        f"Portfolio balance: {round(portfolio_balance_sol, 5)} SOL (USD ${round(portfolio_balance_usd, 2)}) \n\n"
        f"{'You currently don’t have any SOL in your wallet. Please deposit to start trading. \n\n' if native_balance == 0 else ''}"
        f"Last updated: {_now}"
    )

    return _reply_text


def init_reply(wallet_address, private_key):
    _now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    _reply_text = (
        "<b>Welcome to LALABA!</b> \n\n"
        "Your solana wallet address is: \n\n"
        f"<code>{wallet_address}</code> \n\n"
        f"Balance: 0 SOL (USD $0) \n"
        "You currently dont have any SOL in your wallet please deposit to start trading"
    )

    return _reply_text


def accept_terms_reply_text():
    _reply_text = (
        "<b>Welcome to LALABA Bot!</b>\n"
        "Accept terms and conditions. bla bla bla \n"
        "<a href='https://www.google.com' target='_blank'>Terms and Conditions</a>"
    )
    return _reply_text


def deny_access_reply_text():
    return "<b>ACCESS DENIED</b> \n"


def not_supported_command_reply_text():
    return "<b>Dunno bout that bro, check commands from the menu</b> \n"


def get_position_token_message_item(token_address: str, token_symbol: str, token_balance, token_balance_sol,
                                    token_balance_usd, profit, pnl, token_mcap, token_price_usd):

    _message = (f"<a href='https://t.me/SlashMvp_bot?start=positions_{token_address}'>{token_symbol}</a>\n"
                f"Balance: <b>{token_balance}</b> | <b>{token_balance_sol}</b> SOL | $ <b>{token_balance_usd}</b>\n"
                f"Profit: <b>{pnl}</b> | <b>{profit}</b> SOL\n"
                f"Mcap: <b>{token_mcap}</b> $ @ <b>${token_price_usd}</b>\n"
    )
    return _message


def get_sell_token_message_item(token_address: str,  token_symbol: str, token_balance_sol, token_balance_usd):

    _message = (f"<a href='https://t.me/SlashMvp_bot?start=sell_{token_address}'>{token_symbol}</a>"
                f" - {token_balance_sol} SOL / {token_balance_usd}$")
    return _message


def pagination_keyboard(page, max_page, refresh_callback: CallbackData):
    _reply_keyboard = [[
        InlineKeyboardButton("PREV", callback_data=CallbackData.PREV.value),
        InlineKeyboardButton(f"CURRENT {page}", callback_data=CallbackData.NOTHING.value),
        InlineKeyboardButton("NEXT", callback_data=CallbackData.NEXT.value)
    ]] if max_page > 1 else []

    _reply_keyboard.append([
        InlineKeyboardButton("REFRESH", callback_data=refresh_callback),
        InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)
    ])
    return _reply_keyboard


def token_info_reply_text(name, symbol, contract_address, pair_address, token_price_usd, mcap,
                          liquidity, native_balance, wallet_has_token_balance, token_balance, token_balance_usd,
                          sol_quote_amount, token_quote_amount, price_impact_percentage):
    _now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    _reply_text = (
        f"<b>{name} ({symbol})</b> \n"
        f"<code>{str(contract_address)}</code> \n"
        f"<a href='https://dexscreener.com/solana/{pair_address} 'target='_blank'>Dexscreener</a> | "
        f"<a href='https://solscan.io/token/{contract_address} 'target='_blank'>Explorer</a> \n\n"
        f"Price: <b>${token_price_usd}</b> - "
        f"MC: <b>${mcap}</b> - "
        f"LIQ: <b>${liquidity}</b> \n\n"
        f"{'Token balance: <b>{token_balance} ({token_balance_usd}$)</b> \n'.format(token_balance=token_balance, token_balance_usd=token_balance_usd) if wallet_has_token_balance else ''}"
        f"Balance: <b>{native_balance} SOL</b>  \n"
        f"<b>{sol_quote_amount}SOL = {token_quote_amount}{symbol}</b>\n"
        f"Price impact: <b>{price_impact_percentage}%</b>  \n\n"
        f"Last updated: {_now}"
    )

    return _reply_text


def wallet_reply_text(wallet_address, balance_sol):
    _reply_text = (
            f"<b>Your Wallet:  </b> \n \n "
            f"Address: <code>{wallet_address}</code> \n "
            f"Balance: <b>{balance_sol}</b> SOL"
    )

    return _reply_text


def wallet_keyboard():
    return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("WITHDRAW ALL SOL", callback_data=CallbackData.WITHDRAW_ALL.value),
                InlineKeyboardButton("WITHDRAW X SOL", callback_data=CallbackData.WITHDRAW_X.value)
            ],
            [
                InlineKeyboardButton("EXPORT PRIVATE KEY", callback_data=CallbackData.EXPORT.value),
            ],
            [InlineKeyboardButton("BACK", callback_data=CallbackData.BACK.value)]
        ])


def settings_keyboard(buy_left_preset, buy_right_preset, sell_left_preset, sell_right_preset, priority_fee, slippage):
    return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"---BUY BUTTONS CONFIGS---", callback_data=CallbackData.NOTHING.value)],
            [
                InlineKeyboardButton(f"Left: {buy_left_preset} SOL", callback_data=CallbackData.BUY_1.value),
                InlineKeyboardButton(f"Right: {buy_right_preset} SOL", callback_data=CallbackData.BUY_2.value)
            ],
            [InlineKeyboardButton(f"---SELL BUTTONS CONFIGS---", callback_data=CallbackData.NOTHING.value)],
            [
                InlineKeyboardButton(f"Left: {sell_left_preset}%", callback_data=CallbackData.SELL_1.value),
                InlineKeyboardButton(f"Right: {sell_right_preset}%", callback_data=CallbackData.SELL_2.value)
            ],
            [InlineKeyboardButton(f"---UPDATE PRIORITY FEE---", callback_data=CallbackData.NOTHING.value)],
            [InlineKeyboardButton(f"Priority fee: {priority_fee} SOL", callback_data=CallbackData.PRIORITY.value)],
            [InlineKeyboardButton(f"---SLIPPAGE CONFIG---", callback_data=CallbackData.NOTHING.value)],
            [
                InlineKeyboardButton(f"{slippage}%", callback_data=CallbackData.SLIPPAGE.value),
            ],
            [InlineKeyboardButton(f"BACK", callback_data=CallbackData.BACK.value)],
        ])