"""generic-bot entrypoint.

Long-polling Telegram bot. No public port, no webhook — runs on whatever
machine you leave on. Send it a profile screenshot, it judges and drafts;
you act in Generic yourself. See README.md for setup.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, filters

import config
import db
from handlers import about, confirm, photos, week

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # PTB's HTTP client is chatty


async def start_cmd(update: Update, context) -> None:
    await update.message.reply_text(
        "send a profile screenshot (or album) to judge it.\n"
        "/about <text> — tell me something new about you\n"
        "/about list — see what I remember\n"
        "/week likes=X matches=Y dates=Z — log this week\n"
        "/report — funnel diagnosis\n"
        "/history — raw weekly numbers"
    )


def main() -> None:
    config.require_telegram()
    config.check_context_file()
    db.init_db()

    allowed_user_filter = filters.User(user_id=config.TELEGRAM_ALLOWED_USER_ID)

    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd, filters=allowed_user_filter))
    photos.register(app, allowed_user_filter)
    confirm.register(app, allowed_user_filter)
    about.register(app, allowed_user_filter)
    week.register(app, allowed_user_filter)

    logging.info("generic-bot starting (backend=%s, user_id=%s)",
                 config.LLM_BACKEND, config.TELEGRAM_ALLOWED_USER_ID)
    app.run_polling()


if __name__ == "__main__":
    main()
