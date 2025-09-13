import traceback
from fastapi import Request, APIRouter
from fastapi.responses import JSONResponse
import logging
from hsbot.bot_handlers import delete_message

router = APIRouter(prefix="/worker")


@router.post(f"/delete-tg-message")
async def delete_tg_message(request: Request):
    try:
        data = await request.json()
        await delete_message(
            user_id=data.get("user_id"),
            chat_id=data.get("chat_id"),
            message_id=data.get("message_id")
        )

        logging.info(f"Message {data.get('message_id')} deleted for user {data.get('user_id')}")
    except Exception:
        logging.error(traceback.format_exc())
    return JSONResponse(
        content={
            "status": "ok"
        }
    )
