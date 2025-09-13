import logging
import decimal
from telegram import Bot, Update, BotCommand
from telegram.error import BadRequest
from solders.keypair import Keypair
import os
import re
import traceback

from hsbot.services.coinbase import get_sol_usd_price
from hsbot.services.sol_client import get_native_balance
from hsbot.services.jupiter import get_jupiter_quote
from hsbot.services.tasks import create_delete_message_task
from hsbot.ui_layout import *
from hsbot.helpers import get_portfolio, sync_tokens_history, get_positions
from hsbot.utils import parse_number, compact_value_display, generate_referral_code, IterablePaginator, verify_address
from hsbot.persistence_layer import store

user_to_message_id_to_settings = {}


paginator = IterablePaginator(page_size=1)

bot = Bot(os.getenv("BOT_TOKEN"))

logger = logging.getLogger()


COMMANDS = [
    BotCommand("/start", description="Start"),
    BotCommand("/buy", description="Buy"),
    BotCommand("/sell", description="Sell"),
    BotCommand("/wallet", description="Wallet"),
    BotCommand("/positions", description="Positions"),
    BotCommand("/settings", description="Settings")
]


async def configure_bot(webhook_url: str):
    await bot.set_my_commands(COMMANDS)
    await bot.set_webhook(webhook_url)


def construct_token_list_content(user_id, tokens_page, message_type):
    messages = []
    for token in tokens_page:
        token_price_usd = token['token_price_usd']
        token_mcap = parse_number(token['fdv_usd'])
        token_balance = token['token_balance']
        token_balance_sol = token['token_balance_sol']
        token_balance_usd = token['token_balance_usd']

        if message_type == "positions":
            token_history = store['users'][user_id]['tokens_history'][token['token_address']]

            token_amount_purchased = decimal.Decimal(token_history['amount_purchased_lossless']) / 10 ** 9
            token_amount_sold = decimal.Decimal(token_history['amount_sold_lossless']) / 10 ** 9
            profit = token_amount_sold - token_amount_purchased + token_balance_sol

            pnl = "Unknown"
            if token_amount_purchased > 0:
                pnl = profit / token_amount_purchased * 100
                pnl = f"{round(pnl, 2)}%"

            if token_price_usd < 0.001:
                token_price_usd = compact_value_display(token_price_usd)
            else:
                token_price_usd = round(token_price_usd, 3)

            token_message_item = get_position_token_message_item(
                token_address=token['token_address'],
                token_symbol=token['symbol'],
                token_balance=token_balance,
                token_balance_sol=round(token_balance_sol, 5),
                token_balance_usd=round(token_balance_usd, 2),
                profit=round(profit, 3),
                pnl=pnl,
                token_mcap=token_mcap,
                token_price_usd=token_price_usd,
            )
            messages.append(token_message_item)
        else:
            token_message_item = get_sell_token_message_item(
                token_address=token['token_address'],
                token_symbol=token['symbol'],
                token_balance_sol=round(token_balance_sol, 5),
                token_balance_usd=round(token_balance_usd, 2)
            )
            messages.append(token_message_item)

    return "\n".join(messages)


async def positions(update: Update):
    fresh = False

    if update.message:
        user_id = str(update.message.from_user.id)
        message_id = str(update.message.message_id)
        reply_method = update.message.reply_text
        fresh = True
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        message_id = str(update.callback_query.message.message_id)
        callback_data = update.callback_query.data
        if callback_data == CallbackData.POSITIONS.value:
            fresh = True
            reply_method = update.callback_query.message.reply_text
        elif callback_data == CallbackData.POSITIONS_REFRESH.value:
            fresh = True
            reply_method = update.callback_query.edit_message_text
        elif callback_data == CallbackData.POSITIONS_BACK.value:
            reply_method = update.callback_query.edit_message_text
        else:
            raise NotImplementedError()
    else:
        raise NotImplementedError()

    logger.info(f"User {user_id} chose Positions.")
    public_key = store.get('users', {})[user_id]['wallet']['public_key']

    if message_id not in store['users'][user_id]['messages'] or fresh:
        current_page = 1
        wallet_positions = await get_positions(wallet_address=public_key)
    else:
        current_page = store['users'][user_id]['messages'][message_id].get('current_page', 1)
        wallet_positions = store['users'][user_id]['messages'][message_id].get('wallet_positions', [])
        if not wallet_positions:
            wallet_positions = await get_positions(wallet_address=public_key)

    if len(wallet_positions) == 0:
        await reply_method(
            "No positions found",
            parse_mode="HTML",
        )
        return

    tokens_page = paginator.get_page_list(wallet_positions, page=current_page)
    max_page = paginator.get_max_page_num(wallet_positions)

    reply_keyboard = pagination_keyboard(current_page, max_page, CallbackData.POSITIONS_REFRESH.value)
    tokens_page_content = construct_token_list_content(user_id, tokens_page, message_type="positions")

    _message = await reply_method(
        f"{tokens_page_content}"
        f"\n\n <b>Page {current_page}/{max_page}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard),
        disable_web_page_preview=True,
    )
    message_id = str(_message.message_id)

    store['users'][user_id]['messages'][message_id] = {
        'type': 'positions',
        'current_page': current_page,
        'wallet_positions': wallet_positions
    }
    store.save()


async def sell(update: Update):
    fresh = False

    if update.message:
        user_id = str(update.message.from_user.id)
        message_id = str(update.message.message_id)
        reply_method = update.message.reply_text
        fresh = True
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        message_id = str(update.callback_query.message.message_id)
        callback_data = update.callback_query.data
        if callback_data == CallbackData.SELL.value:
            fresh = True
            reply_method = update.callback_query.message.reply_text
        elif callback_data == CallbackData.SELL_REFRESH.value:
            fresh = True
            reply_method = update.callback_query.edit_message_text
        elif callback_data == CallbackData.SELL_BACK.value:
            reply_method = update.callback_query.edit_message_text
        else:
            raise NotImplementedError()
    else:
        raise NotImplementedError()

    logger.info(f"User {user_id} chose SELL.")
    public_key = store.get('users', {})[user_id]['wallet']['public_key']

    if message_id not in store['users'][user_id]['messages'] or fresh:
        current_page = 1
        wallet_positions = await get_positions(wallet_address=public_key)
    else:
        current_page = store['users'][user_id]['messages'][message_id].get('current_page', 1)
        wallet_positions = store['users'][user_id]['messages'][message_id].get('wallet_positions', [])
        if not wallet_positions:
            wallet_positions = await get_positions(wallet_address=public_key)

    if len(wallet_positions) == 0:
        await reply_method(
            "No tokens found",
            parse_mode="HTML",
        )
        return

    tokens_page = paginator.get_page_list(wallet_positions, page=current_page)
    max_page = paginator.get_max_page_num(wallet_positions)

    reply_keyboard = pagination_keyboard(current_page, max_page, CallbackData.SELL_REFRESH.value)
    tokens_page_content = construct_token_list_content(user_id, tokens_page, message_type="sell")

    _message = await reply_method(
        f"{len(wallet_positions)} tokens found \n\n"
        f"{tokens_page_content}"
        f"\n\n <b>Page {current_page}/{max_page}</b>",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )
    message_id = str(_message.message_id)

    store['users'][user_id]['messages'][message_id] = {
        'type': 'sell',
        'current_page': current_page,
        'wallet_positions': wallet_positions
    }
    store.save()


async def token_info(update):
    fresh = False

    if update.message:
        user_id = str(update.message.from_user.id)
        text_parts = update.message.text.split(" ", 1)
        if len(text_parts) > 1:
            message_type, contract_address = text_parts[1].split("_", 1)
        else:
            message_type = None
            contract_address = update.message.text
        reply_method = update.message.reply_text
        fresh = True
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        message_id = str(update.callback_query.message.message_id)
        stored_message = store['users'][user_id]['messages'][message_id]
        contract_address = stored_message['current_token']
        message_type = stored_message['type']
        reply_method = update.callback_query.edit_message_text
        callback_data = update.callback_query.data
        if callback_data == CallbackData.REFRESH_TOKEN.value:
            fresh = True
    else:
        raise NotImplementedError()

    logger.info(f"CA: {contract_address}")

    contract_address_is_valid = await verify_address(contract_address)

    if not contract_address_is_valid:
        await bot.send_animation(
            chat_id=update.message.chat_id,
            animation="https://media1.tenor.com/m/X2eGI8VUp5gAAAAd/%CE%B2%CE%B9%CE%B5%CF%8A%CF%81%CE%AF%CE%BD%CE%B9%CE%B1-vieirinha.gif"
        )
        return

    public_key = store.get('users', {})[user_id]['wallet']['public_key']
    user_settings = store['users'][user_id]['settings']
    sol_quote_amount = user_settings['buy_1']
    user_slippage = user_settings['slippage']

    if 'portfolio' not in store['users'][user_id] or fresh:
        sol_price = await get_sol_usd_price()
        portfolio = await get_portfolio(public_key, sol_price)
        sync_tokens_history(user_id=user_id, tokens=portfolio['tokens'].keys())
        store['users'][user_id]['portfolio'] = portfolio
        store.save()
    else:
        portfolio = store['users'][user_id]['portfolio']

    rsp = await get_jupiter_quote(
        swap_type=1, mint_address=contract_address,
        mint_amount=int(sol_quote_amount * 10 ** 9),
        slippage_bps=int(user_slippage * 10)
    )

    wallet_has_token_balance = (
            contract_address in portfolio['tokens']
            and portfolio['tokens'][contract_address]['token_balance'] > 0
    )

    native_balance = round(portfolio['native_token'], 5)
    token_balance = parse_number(portfolio['tokens'][contract_address]['token_balance'])
    token_balance_usd = parse_number(round(portfolio['tokens'][contract_address]['token_balance_usd'], 2))
    token_price_usd = round(portfolio['tokens'][contract_address]['token_price_usd'], 5)
    mcap = parse_number(round(portfolio['tokens'][contract_address]['fdv_usd'], 3))
    lqiquidity = parse_number(round(portfolio['tokens'][contract_address]['liquidity_usd'], 3))
    name = portfolio['tokens'][contract_address]['name']
    symbol = portfolio['tokens'][contract_address]['symbol']
    pair_address = portfolio['tokens'][contract_address]['pair_address']
    decimals = portfolio['tokens'][contract_address]['decimals']
    token_quote_amount = round(int(rsp['outAmount']) / 10 ** decimals, 2)
    price_impact_percentage = round(float(rsp['priceImpactPct']) * 100, 2)

    if message_type == 'positions':
        parent = CallbackData.POSITIONS_BACK.value
    elif message_type == 'sell':
        parent = CallbackData.SELL_BACK.value
    else:
        parent = CallbackData.BACK.value

    if wallet_has_token_balance:
        token_history = store['users'][user_id]['tokens_history'].get(contract_address, {})
        sell_initial = token_history.get('amount_sold_lossless', 0) == 0
        keyboard = generate_token_keyboard(user_settings, sell_initial=sell_initial, parent=parent)
    else:
        keyboard = generate_token_keyboard(user_settings, sell_initial=False, parent=parent)

    message = await reply_method(
        text=token_info_reply_text(
           name=name,
           symbol=symbol,
           contract_address=contract_address,
           pair_address=pair_address,
           token_price_usd=token_price_usd,
           mcap=mcap,
           liquidity=lqiquidity,
           native_balance=native_balance,
           wallet_has_token_balance=wallet_has_token_balance,
           token_balance=token_balance,
           token_balance_usd=token_balance_usd,
           sol_quote_amount=sol_quote_amount,
           token_quote_amount=token_quote_amount,
           price_impact_percentage=price_impact_percentage
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard
    )
    store['users'][user_id]['messages'][str(message.message_id)] = {
        'type': message_type,
        'current_token': contract_address
    }
    store.save()


def initialize_user(user_id):
    if user_id not in store.get('users', {}):
        if user_id in store.get('allowed_users', {}):
            wallet_address_pk = store['allowed_users'][user_id]
            wallet_address = Keypair.from_base58_string(wallet_address_pk).pubkey()
        else:
            wallet_address_pk = Keypair()
            wallet_address = Keypair.from_base58_string(wallet_address_pk).pubkey()

        user_referral_code = generate_referral_code()
        store['users'].update(
            {
                user_id: {
                    'wallet': {
                        'public_key': wallet_address,
                        'private_key': wallet_address_pk,
                    },
                    'tokens_history': {},
                    'settings': store.get('default_settings'),
                    'accepted_terms': True,
                    'referral_code': user_referral_code,
                    'messages': {},
                    'awaiting_input': None,
                    'dialogs': {}
                }
            }
        )

        store['referral_codes_to_users'].update(
            {
                user_referral_code: {
                    'user_id': user_id,
                    'referred_users': []
                }
            }
        )

        store.save()


async def start(update: Update):
    fresh = False

    if update.message:
        user_id = str(update.message.from_user.id)
        reply_method = update.message.reply_text
        fresh = True
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        callback_data = update.callback_query.data
        reply_method = update.callback_query.edit_message_text
        if callback_data in (CallbackData.START.value, CallbackData.START_REFRESH.value,):
            fresh = True
    else:
        raise NotImplementedError()

    # incoming from fresh start for a user, meaning:
    # first run for a user
    # explicit command from menu
    # link redirect to bot, either for onboarding or from internal formed link
    if update.message:
        text_parts = update.message.text.split(" ", 1)

        if len(text_parts) > 1:
            key, value = text_parts[1].split("_", 1)
            logging.info(f"{key} {value}")
            if key == 'positions':
                await token_info(update)
                return
            elif key == 'sell':
                await token_info(update)
                return
            elif key == 'referral':
                if value in store['referral_codes_to_users']:
                    referred_users = store['referral_codes_to_users'][value]['referred_users']
                    if user_id not in referred_users:
                        store['referral_codes_to_users'][value]['referred_users'].append(user_id)
                        store.save()
            else:
                logging.error(f"{key} not supported, aborting")
                return

    store['users'][user_id]['awaiting_input'] = None
    store['users'][user_id]['dialogs'] = {}
    store.save()
    public_key = store.get('users', {})[user_id]['wallet']['public_key']

    if 'portfolio' not in store['users'][user_id] or fresh:
        sol_price = await get_sol_usd_price()
        portfolio = await get_portfolio(public_key, sol_price)
        sync_tokens_history(user_id=user_id, tokens=portfolio['tokens'].keys())
        store['users'][user_id]['portfolio'] = portfolio
        store.save()
    else:
        portfolio = store['users'][user_id]['portfolio']

    await reply_method(
        text=portfolio_overview_reply_text(
            wallet_address=public_key,
            native_balance=portfolio['native_token'],
            native_balance_usd=portfolio['native_token_usd_worth'],
            portfolio_balance_sol=portfolio['sol_worth'],
            portfolio_balance_usd=portfolio['usd_worth'],
            welcome=fresh
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(root_keyboard()),
    )


async def coming_soon(update: Update):
    message = await update.callback_query.message.reply_text(
        "&#128284",
        parse_mode="HTML"
    )
    user_id = str(message.from_user.id)
    chat_id = str(message.chat.id)
    message_id = str(message.message_id)

    await create_delete_message_task(user_id=user_id, chat_id=chat_id, message_id=message_id, delay=3)


async def delete_message(user_id, chat_id, message_id):
    if user_id in store['users'] and message_id in store['users'][user_id]['messages']:
        del store['users'][user_id]['messages'][message_id]
        store.save()
    await bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))


async def delete(update: Update):

    if update.message:
        user_id = str(update.message.from_user.id)
        chat_id = str(update.message.chat.id)
        message_id = str(update.message.message_id)
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        chat_id = str(update.callback_query.message.chat.id)
        message_id = str(update.callback_query.message.message_id)
    else:
        raise NotImplementedError()

    if user_id in store['users'] and message_id in store['users'][user_id]['messages']:
        del store['users'][user_id]['messages'][message_id]
        store.save()
    await bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))


async def init(update: Update):
    user_id = str(update.callback_query.from_user.id)
    initialize_user(user_id)
    user_wallet = store['users'][user_id]['wallet']
    _message = await update.callback_query.edit_message_text(
        text=init_reply(
            wallet_address=user_wallet['public_key'],
            private_key=user_wallet['private_key']
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("START TRADING", callback_data=CallbackData.START.value),
            ]
        ])
    )


async def export(update: Update):
    user_id = str(update.callback_query.from_user.id)

    delete_after = 30

    user_wallet = store.get('users', {})[user_id]['wallet']
    keypair = user_wallet['private_key']
    logger.info('private key is %s:', keypair)
    message = await update.callback_query.message.reply_text(
        f"<b>Your Private Key:</b>\n\n<code>{keypair}</code> \n\n<b>"
        f"This message will be deleted after {delete_after} seconds</b>",
        parse_mode="HTML"
    )

    chat_id = str(message.chat.id)
    message_id = str(message.message_id)

    await create_delete_message_task(user_id=user_id, chat_id=chat_id, message_id=message_id, delay=delete_after)


async def wallet(update: Update):
    if update.message:
        user_id = str(update.message.from_user.id)
        reply_method = update.message.reply_text
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        reply_method = update.callback_query.edit_message_text
    else:
        raise NotImplementedError()

    logger.info(f"User {user_id} chose WALLET.")
    public_key = store.get('users', {})[user_id]['wallet']['public_key']
    native_balance = await get_native_balance(public_key)
    await reply_method(
        text=wallet_reply_text(
            wallet_address=public_key,
            balance_sol=round(native_balance, 9)
        ),
        parse_mode="HTML",
        reply_markup=wallet_keyboard()
    )


async def settings(update: Update):
    if update.message:
        user_id = str(update.message.from_user.id)
        reply_method = update.message.reply_text
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        reply_method = update.callback_query.edit_message_text
    else:
        raise NotImplementedError()

    logger.info(f"User {user_id} chose SETTINGS.")
    settings_dic = store['users'][user_id]['settings']

    await reply_method(
        text=f"<b>WALLET SETTINGS</b>",
        parse_mode="HTML",
        reply_markup=settings_keyboard(
            buy_left_preset=settings_dic['buy_1'],
            buy_right_preset=settings_dic['buy_2'],
            sell_left_preset=settings_dic['sell_1'],
            sell_right_preset=settings_dic['sell_2'],
            priority_fee=settings_dic['priority_fee'],
            slippage=settings_dic['slippage']
        )
    )


async def update_priority(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    store['users'][user_id]['awaiting_input'] = PendingInputState.UPDATE_PRIORITY.value
    store.save()
    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    await query.message.reply_text(
        text=f"Reply with your new setting for the priority fee in SOL. Example: 0.01",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )


async def update_slippage(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    store['users'][user_id]['awaiting_input'] = PendingInputState.UPDATE_SLIPPAGE.value
    store.save()
    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    await query.message.reply_text(
        text=f"Reply with your new setting for the slippage %. Example: 20",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )


async def update_buy_left_preset(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    store['users'][user_id]['awaiting_input'] = PendingInputState.UPDATE_BUY_LEFT_PRESET.value
    store.save()
    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    await query.message.reply_text(
        text=f"Reply with your new setting for the left Buy Button in SOL. Example: 0.5",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )


async def update_buy_right_preset(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    store['users'][user_id]['awaiting_input'] = PendingInputState.UPDATE_BUY_RIGHT_PRESET.value
    store.save()
    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    await query.message.reply_text(
        text=f"Reply with your new setting for the right Buy Button in SOL. Example: 0.5",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )


async def update_sell_left_preset(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    store['users'][user_id]['awaiting_input'] = PendingInputState.UPDATE_SELL_LEFT_PRESET.value
    store.save()
    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    await query.message.reply_text(
        text=f"Reply with your new setting for the left Sell Button in %. Example: 50",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )


async def update_sell_right_preset(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    store['users'][user_id]['awaiting_input'] = PendingInputState.UPDATE_SELL_RIGHT_PRESET.value
    store.save()
    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    await query.message.reply_text(
        text=f"Reply with your new setting for the right Sell Button in %. Example: 100",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )


async def withdraw_all(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    store['users'][user_id]['awaiting_input'] = PendingInputState.WITHDRAW_ALL_RECIPIENT.value

    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    message = await query.message.reply_text(
        text=f"Reply with the address you want to withdraw to",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )
    store['users'][user_id]['dialogs'][Dialog.WITHDRAW_ALL.value] = {
        'prompt': {
            'user_id': user_id,
            'chat_id': message.chat_id,
            'message_id': message.message_id
        }
    }
    store.save()


async def withdraw_x(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    store['users'][user_id]['awaiting_input'] = PendingInputState.WITHDRAW_X_RECIPIENT.value

    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    message = await query.message.reply_text(
        text=f"Reply with the address you want to withdraw to",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )
    store['users'][user_id]['dialogs'][Dialog.WITHDRAW_CUSTOM.value] = {
        'prompt': {
            'user_id': user_id,
            'chat_id': message.chat_id,
            'message_id': message.message_id
        }
    }
    store.save()


async def buy(update: Update):
    if update.message:
        user_id = str(update.message.from_user.id)
        reply_method = update.message.reply_text
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        reply_method = update.callback_query.message.reply_text
    else:
        raise NotImplementedError()

    logger.info(f"User {user_id} chose BUY.")
    store['users'][user_id]['awaiting_input'] = PendingInputState.BUY_CONTRACT_ADDRESS.value

    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    message = await reply_method(
        "Please paste the CA",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )
    store['users'][user_id]['dialogs'][Dialog.BUY_CUSTOM.value] = {
        'prompt': {
            'chat_id': message.chat_id,
            'message_id': message.message_id
        }
    }
    store.save()


async def buy_preset(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    message_id = str(query.message.message_id)
    callback_data = query.data
    if callback_data == CallbackData.BUY_FIRST.value:
        option = "left"
        buy_preset_amount = store['users'][user_id]['settings']['buy_1']
    elif callback_data == CallbackData.BUY_SECOND.value:
        option = "right"
        buy_preset_amount = store['users'][user_id]['settings']['buy_2']
    else:
        raise NotImplementedError()

    current_token = store['users'][user_id]['messages'][message_id]['current_token']
    logger.info(f"User {user_id} chose buy {option} preset on token {current_token}")
    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    await query.message.reply_text(
        text=f"You bought {buy_preset_amount} SOL of {current_token}.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )


async def buy_custom(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    message_id = str(query.message.message_id)
    current_token = store['users'][user_id]['messages'][message_id]['current_token']
    store['users'][user_id]['awaiting_input'] = PendingInputState.BUY_CUSTOM_AMOUNT.value

    reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
    message = await query.message.reply_text(
        text=f"<b>Type the custom amount in SOL that you want to buy (example: 0.1) of Token: {current_token} </b> \n ",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )
    store['users'][user_id]['dialogs'][Dialog.BUY_CUSTOM.value] = {
        "token": current_token,
        'prompt': {
            'chat_id': message.chat_id,
            'message_id': message.message_id
        }
    }
    store.save()


async def text_input(update: Update):
    user_id = str(update.message.from_user.id)
    user_awaiting_input_state = store['users'][user_id]['awaiting_input']

    if user_awaiting_input_state is None:
        await token_info(update)
    elif user_awaiting_input_state == PendingInputState.BUY_CONTRACT_ADDRESS.value:

        prompt = store['users'][user_id]['dialogs'].get(Dialog.BUY_CUSTOM.value, {}).get('prompt')
        if prompt:
            await bot.delete_message(chat_id=prompt['chat_id'], message_id=prompt['message_id'])

        await token_info(update)
        store['users'][user_id]['awaiting_input'] = None
        store['users'][user_id]['dialogs'][Dialog.BUY_CUSTOM.value] = None
        store.save()

    elif user_awaiting_input_state == PendingInputState.BUY_CUSTOM_AMOUNT.value:
        contract_address = store['users'][user_id]['dialogs'][Dialog.BUY_CUSTOM.value]['token']
        amount = float(update.message.text)

        prompt = store['users'][user_id]['dialogs'][Dialog.BUY_CUSTOM.value]['prompt']
        await bot.delete_message(chat_id=prompt['chat_id'], message_id=prompt['message_id'])

        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        await update.message.reply_text(
            text=f"You bought {amount} SOL of {contract_address}.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['awaiting_input'] = None
        store['users'][user_id]['dialogs'][Dialog.BUY_CUSTOM.value] = None
        store.save()
    elif user_awaiting_input_state == PendingInputState.WITHDRAW_ALL_RECIPIENT.value:
        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        recipient = update.message.text

        prompt = store['users'][user_id]['dialogs'][Dialog.WITHDRAW_ALL.value]['prompt']
        await bot.delete_message(chat_id=prompt['chat_id'], message_id=prompt['message_id'])

        await update.message.reply_text(
            f"<b>Balance sent to {recipient}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['awaiting_input'] = None
        store['users'][user_id]['dialogs'][Dialog.WITHDRAW_ALL.value] = None
        store.save()
    elif user_awaiting_input_state == PendingInputState.UPDATE_BUY_LEFT_PRESET.value:
        amount = float(update.message.text)
        store['users'][user_id]['settings']['buy_1'] = amount
        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        await update.message.reply_text(
            f"<b>Left buy updated to {str(amount)}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['awaiting_input'] = None
        store.save()
    elif user_awaiting_input_state == PendingInputState.UPDATE_BUY_RIGHT_PRESET.value:
        amount = float(update.message.text)
        store['users'][user_id]['settings']['buy_2'] = amount
        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        await update.message.reply_text(
            f"<b>Right buy updated to {str(amount)}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['awaiting_input'] = None
        store.save()
    elif user_awaiting_input_state == PendingInputState.UPDATE_PRIORITY.value:
        amount = float(update.message.text)
        store['users'][user_id]['settings']['priority_fee'] = amount
        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        await update.message.reply_text(
            f"<b>Priority fee updated to {str(amount)}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['awaiting_input'] = None
        store.save()
    elif user_awaiting_input_state == PendingInputState.UPDATE_SLIPPAGE.value:
        amount = float(update.message.text)
        store['users'][user_id]['settings']['slippage'] = amount
        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        await update.message.reply_text(
            f"<b>Slippage updated to {str(amount)}%</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['awaiting_input'] = None
        store.save()
    elif user_awaiting_input_state == PendingInputState.UPDATE_SELL_LEFT_PRESET.value:
        amount = float(update.message.text)
        store['users'][user_id]['settings']['sell_1'] = amount
        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        await update.message.reply_text(
            f"<b>Left sell updated to {str(amount)}%</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['awaiting_input'] = None
        store.save()
    elif user_awaiting_input_state == PendingInputState.UPDATE_SELL_RIGHT_PRESET.value:
        amount = float(update.message.text)
        store['users'][user_id]['settings']['sell_2'] = amount
        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        await update.message.reply_text(
            f"<b>Right sell updated to {str(amount)}%</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['awaiting_input'] = None
        store.save()
    elif user_awaiting_input_state == PendingInputState.WITHDRAW_X_RECIPIENT.value:
        recipient = update.message.text

        prompt = store['users'][user_id]['dialogs'][Dialog.WITHDRAW_CUSTOM.value]['prompt']
        await bot.delete_message(chat_id=prompt['chat_id'], message_id=prompt['message_id'])

        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        message = await update.message.reply_text(
            f"<b>Reply with the amount you want to send to: {recipient}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['dialogs'][Dialog.WITHDRAW_CUSTOM.value] = {
            'recipient': recipient,
            "prompt": {
                "chat_id": message.chat.id,
                "message_id": message.message_id
            }
        }
        store['users'][user_id]['awaiting_input'] = PendingInputState.WITHDRAW_X_AMOUNT.value
        store.save()
    elif user_awaiting_input_state == PendingInputState.WITHDRAW_X_AMOUNT.value:
        amount = float(update.message.text)
        recipient = store['users'][user_id]['dialogs'][Dialog.WITHDRAW_CUSTOM.value]['recipient']

        prompt = store['users'][user_id]['dialogs'][Dialog.WITHDRAW_CUSTOM.value]['prompt']
        await bot.delete_message(chat_id=prompt['chat_id'], message_id=prompt['message_id'])

        reply_keyboard = [[InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)]]
        await update.message.reply_text(
            f"<b>Withdrew {str(amount)} SOL to {recipient}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
        store['users'][user_id]['awaiting_input'] = None
        store['users'][user_id]['dialogs'][Dialog.WITHDRAW_CUSTOM.value] = None
        store.save()
    else:
        store['users'][user_id]['awaiting_input'] = None
        store.save()


async def navigate_page(update: Update):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    message_id = str(query.message.message_id)
    callback_data = query.data
    stored_message = store['users'][user_id]['messages'][message_id]
    message_type = stored_message['type']
    current_page = stored_message['current_page']
    wallet_positions = stored_message['wallet_positions']

    max_page = paginator.get_max_page_num(wallet_positions)

    if callback_data == CallbackData.NEXT.value:
        if current_page < max_page:
            current_page += 1
        else:
            current_page = 1
        store['users'][user_id]['messages'][message_id]['current_page'] = current_page
        store.save()
    elif callback_data == CallbackData.PREV.value:
        if current_page > 1:
            current_page -= 1
        else:
            current_page = max_page
        store['users'][user_id]['messages'][message_id]['current_page'] = current_page
        store.save()
    else:
        raise NotImplementedError()

    tokens_page = paginator.get_page_list(wallet_positions, page=current_page)
    tokens_page_content = construct_token_list_content(user_id, tokens_page, message_type=message_type)

    if message_type == 'sell':
        reply_keyboard = pagination_keyboard(current_page, max_page, CallbackData.SELL_REFRESH.value)
        await query.edit_message_text(
            f"{len(wallet_positions)} tokens found \n\n"
            f"{tokens_page_content}"
            f"\n\n <b>Page {current_page}/{max_page}</b>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(reply_keyboard)
        )
    elif message_type == 'positions':
        reply_keyboard = pagination_keyboard(current_page, max_page, CallbackData.POSITIONS_REFRESH.value)
        await query.edit_message_text(
            f"{tokens_page_content}"
            f"\n\n <b>Page {current_page}/{max_page}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(reply_keyboard),
            disable_web_page_preview=True,
        )
    else:
        raise NotImplementedError()


async def help_button(update: Update):
    query = update.callback_query
    reply_keyboard = [
        [
            InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)
        ]
    ]
    await query.message.reply_text("Use /start to test this bot.",
                                   parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(reply_keyboard)
                                   )


async def nothing(update: Update):
    pass


async def referral(update: Update):
    query = update.callback_query
    user_id = str(query.from_user.id)
    ref_code = store['users'][user_id]['referral_code']
    referred_users_count = len(store['referral_codes_to_users'][ref_code]['referred_users'])
    reply_keyboard = [
        [
            InlineKeyboardButton("CLOSE", callback_data=CallbackData.DELETE.value)
        ]
    ]
    await query.message.reply_text(
        f"<b>Your referral link is:</b>\n\n<code>https://t.me/SlashMvp_bot?start=referral_{ref_code}</code> \n\n"
        f"Total referred users: {referred_users_count}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard)
    )


async def deny_access(update: Update):
    await update.message.reply_text(
        text=deny_access_reply_text(),
        parse_mode="HTML"
    )


async def accept_terms(update: Update):
    reply_keyboard = [[InlineKeyboardButton("ACCEPT", callback_data=CallbackData.INIT.value)]]
    await update.message.reply_text(
        text=accept_terms_reply_text(),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(reply_keyboard),
        disable_web_page_preview=True
    )


async def not_supported_command(update: Update):
    await update.message.reply_text(
        text=not_supported_command_reply_text(),
        parse_mode="HTML"
    )


CALLBACK_QUERY_ROUTER = {
    CallbackData.EXPORT.value: export,
    CallbackData.BUY.value: buy,
    CallbackData.SELL.value: sell,
    CallbackData.SELL_BACK.value: sell,
    CallbackData.SELL_REFRESH.value: sell,
    CallbackData.WALLET.value: wallet,
    CallbackData.SETTINGS.value: settings,
    CallbackData.BUY_1.value: update_buy_left_preset,
    CallbackData.BUY_2.value: update_buy_right_preset,
    CallbackData.REFRESH_TOKEN.value: token_info,
    CallbackData.START.value: start,
    CallbackData.START_REFRESH.value: start,
    CallbackData.BACK.value: start,
    CallbackData.PRIORITY.value: update_priority,
    CallbackData.SLIPPAGE.value: update_slippage,
    CallbackData.SLIPPAGE_TOKEN_INFO.value: update_slippage,
    CallbackData.SELL_1.value: update_sell_left_preset,
    CallbackData.SELL_2.value: update_sell_right_preset,
    CallbackData.WITHDRAW_ALL.value: withdraw_all,
    CallbackData.WITHDRAW_X.value: withdraw_x,
    CallbackData.DELETE.value: delete,
    CallbackData.INIT.value: init,
    CallbackData.SOON.value: coming_soon,
    CallbackData.BUY_FIRST.value: buy_preset,
    CallbackData.BUY_SECOND.value: buy_preset,
    CallbackData.BUY_CUSTOM.value: buy_custom,
    CallbackData.POSITIONS.value: positions,
    CallbackData.POSITIONS_BACK.value: positions,
    CallbackData.POSITIONS_REFRESH.value: positions,
    CallbackData.NEXT.value: navigate_page,
    CallbackData.PREV.value: navigate_page,
    CallbackData.REFERRAL.value: referral,
    CallbackData.HELP.value: help_button,
    CallbackData.NOTHING.value: nothing,
}

COMMAND_ROUTER = {
    "/start": start,
    "/buy": buy,
    "/sell": sell,
    "/wallet": wallet,
    "/positions": positions,
    "/settings": settings,
}


async def route_update(update: Update):
    try:
        # in case this is a command then always check for
        # eligibility as input of commands is independent of app flow
        if update.message:
            user_id = str(update.message.from_user.id)

            if user_id not in store.get('allowed_users', {}):
                await deny_access(update)
                return

            if not store.get('users', {}).get(user_id, {}).get('accepted_terms', False):
                await accept_terms(update)
                return

        if update.message:
            text = update.message.text.encode("utf-8").decode()
            command_syntax = text.startswith("/")

            if command_syntax:
                text_parts = update.message.text.split(" ", 1)
                _command = text_parts[0]

                if _command in COMMAND_ROUTER:
                    await COMMAND_ROUTER[_command](update)
                    await delete(update)
                else:
                    await delete(update)
                    await not_supported_command(update)
            else:
                await text_input(update)
        elif update.callback_query:
            callback_data = update.callback_query.data
            await CALLBACK_QUERY_ROUTER[callback_data](update)
    except BadRequest:
        logging.warning(f"Telegram bad request: {traceback.format_exc()}")

