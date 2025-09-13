import os


def init_env_variables():
    if os.getenv('GAE_ENV', '').startswith('standard'):
        # Load from secrets engine
        from hsbot.services.gcp_secrets import access_secret_version

        os.environ.update(
            (
                ("HELIUS_API_KEY", access_secret_version("HELIUS_API_KEY")),
                ("SHYFT_API_KEY", access_secret_version("SHYFT_API_KEY")),
                ("SOLANA_PUBLICNODE_TOKEN", access_secret_version("SOLANA_PUBLICNODE_TOKEN")),
                ("BOT_TOKEN", access_secret_version("BOT_TOKEN")),
                ("BOT_WEBHOOK_TOKEN", access_secret_version("BOT_WEBHOOK_TOKEN")),
            )
        )
    else:
        # Define env variables for the local development environment
        os.environ.update(
            (
                ("GOOGLE_CLOUD_PROJECT", ""),
                ("HELIUS_API_KEY", ""),
                ("SHYFT_API_KEY", ""),
                ("SOLANA_PUBLICNODE_TOKEN", ""),
                ("BOT_TOKEN", ""),
                ("BOT_WEBHOOK_TOKEN", ""),
            )
        )
