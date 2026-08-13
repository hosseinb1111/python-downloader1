from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import BOT_TOKEN
from handlers import start, handle_link
from keepalive import start_keepalive


def build_application() -> Application:
    """Create and configure the Telegram bot application."""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)
    )

    return application


def main() -> None:
    """Start the keepalive server and the Telegram bot."""
    start_keepalive()

    application = build_application()

    print("Telegram downloader bot is starting...")
    print("Keepalive server: http://0.0.0.0:10000")

    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
