"""/about — identity memory that grows over time, explicitly.

/about <text>       add a new fact/update
/about list         show active notes with their ids
/about forget <id>  retire a stale one (soft delete)
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

import config
import db


async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args

    if not args:
        await update.message.reply_text(
            "usage:\n"
            "/about <text> — add a note\n"
            "/about list — show active notes\n"
            "/about forget <id> — retire one"
        )
        return

    if args[0] == "list":
        notes = db.list_active_notes(config.CONTEXT_NOTE_LIMIT)
        if not notes:
            await update.message.reply_text("no active notes yet.")
            return
        lines = [f"#{row['id']} ({row['ts'][:10]}) {row['text']}" for row in notes]
        await update.message.reply_text("\n".join(lines))
        return

    if args[0] == "forget":
        if len(args) < 2 or not args[1].isdigit():
            await update.message.reply_text("usage: /about forget <id>")
            return
        ok = db.deactivate_note(int(args[1]))
        await update.message.reply_text("retired." if ok else "no active note with that id.")
        return

    text = " ".join(args)
    note_id = db.add_context_note(text)
    await update.message.reply_text(f"noted (#{note_id}).")


def register(app, allowed_user_filter) -> None:
    app.add_handler(CommandHandler("about", about_cmd, filters=allowed_user_filter))
