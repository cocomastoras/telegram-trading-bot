from fastapi import FastAPI
import logging
import os
# initialize environment variables
from env_variables import init_env_variables
init_env_variables()

from hsbot.bot_handlers import configure_bot

from hsbot.routers import bot_webhook, worker


app = FastAPI(
    description="Telegram bot",
    version="0.0.1",
    docs_url="/documentation",
    redoc_url="/redocs"
)

# Init logging
if os.getenv('GAE_ENV', '').startswith('standard'):
    import google.cloud.logging
    from google.cloud.logging_v2.handlers import setup_logging

    from fastapi_gae_logging import FastAPIGAELoggingHandler

    client = google.cloud.logging.Client()
    gae_log_handler = FastAPIGAELoggingHandler(
        app=app,
        client=client
    )
    setup_logging(handler=gae_log_handler)


logging.getLogger().setLevel(logging.INFO)

app.include_router(bot_webhook.router)
app.include_router(worker.router)


if __name__ == '__main__':
    import asyncio
    import uvicorn
    import ssl
    from pyngrok import ngrok, conf, installer

    pyngrok_config = conf.get_default()

    if not os.path.exists(pyngrok_config.ngrok_path):
        myssl = ssl.create_default_context()
        myssl.check_hostname = False
        myssl.verify_mode = ssl.CERT_NONE
        installer.install_ngrok(pyngrok_config.ngrok_path, context=myssl)
    # in case of local dev:
    #  - set ngrok tunnel for communication from outter world
    #  - set the bot webhook pointing to that exposed public URL
    #  - configure the bot commands for menu
    PORT = 8080

    http_tunnel = ngrok.connect(PORT, bind_tls=True)
    public_url = http_tunnel.public_url

    webhook_token = os.getenv('BOT_WEBHOOK_TOKEN')
    webhook_url = f"{public_url}/webhook/{webhook_token}"

    asyncio.run(configure_bot(webhook_url))

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
