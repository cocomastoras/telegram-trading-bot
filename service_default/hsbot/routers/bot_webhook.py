import traceback
from fastapi import Request, APIRouter
from fastapi.responses import JSONResponse
from telegram import Update
import logging
from hsbot.bot_handlers import bot, route_update
import os

BOT_WEBHOOK_TOKEN = os.getenv('BOT_WEBHOOK_TOKEN')

router = APIRouter()


@router.post(f"/webhook/{BOT_WEBHOOK_TOKEN}")
async def respond(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        logging.info(update)
        await route_update(update)
    except Exception:
        logging.error(traceback.format_exc())
    return JSONResponse(
        content={
            "status": "ok"
        }
    )
