"""Entry point: starts the keepalive server and the Telegram bot."""
from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import config
from downloader import cleanup_stale
from handlers import audio_command, handle_link, help_command, on_error, start
from keepalive import start_keepalive

log = logging.getLogger("bot")


async def _post_init(application: Application) -> None:
    """Register the command menu shown in Telegram's UI."""
    await application.bot.set_my_commands([
        BotCommand("start", "Show the welcome message"),
        BotCommand("audio", "Download a link as MP3"),
        BotCommand("help", "How to use the bot"),
    ])


def build_application() -> Application:
    """Create and configure the Telegram bot application."""
    application = (
        Application.builder()
        .token(config.require_token())
        .concurrent_updates(True)  # one slow download must not block other users
        .post_init(_post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("audio", audio_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    application.add_error_handler(on_error)
    return application


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # don't log the bot token in URLs

    application = build_application()  # validates BOT_TOKEN first
    cleanup_stale()
    if start_keepalive():
        log.info("Health endpoint listening on port %s (/ and /health)", config.PORT)

    log.info("Telegram downloader bot is starting...")
    application.run_polling(allowed_updates=["message"], drop_pending_updates=True)


if __name__ == "__main__":
    main()
