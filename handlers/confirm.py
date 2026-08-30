"""Inline-button flow: liked/skipped, then sent-as-is/edited.

Two-stage confirm closes the gap between "the bot recommended LIKE" and
"a like actually got sent" (US-5/6's tracked-count requirement), and
captures the FINAL sent text into the voice bank (US on voice memory).
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db

# context.user_data key: set while waiting for the user to paste the
# edited final text after tapping "edited it".
_AWAITING_KEY = "awaiting_final_for"


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, _, raw_id = query.data.partition(":")
    decision_id = int(raw_id)

    if action == "liked":
        db.set_user_action(decision_id, "liked")
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("sent as-is", callback_data=f"asis:{decision_id}"),
            InlineKeyboardButton("I edited it", callback_data=f"edited:{decision_id}"),
        ]])
        await query.edit_message_text(
            query.message.text + "\n\n[liked] — did you send it as drafted, or edit it?",
            reply_markup=keyboard,
        )

    elif action == "skipped":
        db.set_user_action(decision_id, "skipped")
        await query.edit_message_text(query.message.text + "\n\n[skipped]")

    elif action == "asis":
        row = db.get_decision(decision_id)
        db.set_final_message(decision_id, row["draft_message"], was_edited=False)
        await query.edit_message_text(
            query.message.text.split("\n\n[liked]")[0]
            + "\n\n[liked, sent as-is — saved to voice memory]"
        )

    elif action == "edited":
        context.user_data[_AWAITING_KEY] = decision_id
        await query.edit_message_text(
            query.message.text.split("\n\n[liked]")[0]
            + "\n\n[liked, edited — paste exactly what you sent her next message]"
        )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catches the pasted final text after an 'edited' tap. No-ops if the
    bot isn't currently waiting on anything from this chat."""
    decision_id = context.user_data.get(_AWAITING_KEY)
    if decision_id is None:
        return
    final_text = update.message.text
    db.set_final_message(decision_id, final_text, was_edited=True)
    del context.user_data[_AWAITING_KEY]
    await update.message.reply_text("saved to voice memory.")


def register(app, allowed_user_filter) -> None:
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & allowed_user_filter, on_text)
    )
