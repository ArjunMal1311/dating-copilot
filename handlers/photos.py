"""Album capture -> judge -> reply with confirm buttons.

Telegram delivers an album as N separate Updates sharing one
media_group_id, not one Update with N photos — so this buffers by group id
and debounces before treating the group as complete. A lone photo (no
media_group_id) is processed immediately, no debounce delay.
"""

from __future__ import annotations

import io
import logging

from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, MessageHandler, filters

import config
import db
import memory
from llm import load_backend

logger = logging.getLogger(__name__)

# media_group_id -> {"chat_id": int, "file_ids": list[str]}
_pending: dict[str, dict] = {}


def _downscale(raw: bytes) -> bytes:
    with Image.open(io.BytesIO(raw)) as img:
        img = img.convert("RGB")
        img.thumbnail((config.MAX_EDGE, config.MAX_EDGE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=config.JPEG_QUALITY)
        return buf.getvalue()


async def _run_judge_and_reply(chat_id: int, file_ids: list[str],
                                context: ContextTypes.DEFAULT_TYPE) -> None:
    status = await context.bot.send_message(chat_id, f"judging {len(file_ids)} photos...")

    images = []
    for file_id in file_ids:
        tg_file = await context.bot.get_file(file_id)
        raw = bytes(await tg_file.download_as_bytearray())
        images.append(_downscale(raw))

    judge = load_backend().judge
    system_prompt = memory.build_system_prompt()

    try:
        decision = judge(images, system_prompt)
    except Exception as e:
        logger.exception("judge failed")
        await status.edit_text(f"judge failed: {e}")
        return

    alternatives = memory.drop_failing_alternatives(decision.alternatives)
    decision_id = db.insert_decision(
        decision=decision.decision,
        reasoning=decision.reasoning,
        target_prompt=decision.target_prompt,
        draft_message=decision.draft_message,
        draft_lane=decision.draft_lane,
        alternatives=alternatives,
    )

    if decision.decision == "like":
        lines = [f"LIKE — {decision.reasoning}"]
        if decision.target_prompt:
            lines.append(f"\nrespond to: {decision.target_prompt}")
        if decision.draft_message:
            lines.append(f"\n{decision.draft_message}")
            for alt in alternatives:
                lines.append(f"\nbackup ({alt['target']}):\n{alt['message']}")
        else:
            lines.append("\n(no draft — write your own)")
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("liked it", callback_data=f"liked:{decision_id}"),
            InlineKeyboardButton("skipped it", callback_data=f"skipped:{decision_id}"),
        ]])
        await status.edit_text("\n".join(lines), reply_markup=keyboard)
    else:
        await status.edit_text(f"SKIP — {decision.reasoning}")


async def _process_group(context: ContextTypes.DEFAULT_TYPE) -> None:
    media_group_id = context.job.data
    entry = _pending.pop(media_group_id, None)
    if entry is None:
        return
    await _run_judge_and_reply(entry["chat_id"], entry["file_ids"], context)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or not update.message.photo:
        return

    # Largest available size for the photo.
    file_id = update.message.photo[-1].file_id
    media_group_id = update.message.media_group_id
    chat_id = update.effective_chat.id

    if media_group_id is None:
        # Lone photo — no album to wait for, process now.
        await _run_judge_and_reply(chat_id, [file_id], context)
        return

    entry = _pending.setdefault(media_group_id, {"chat_id": chat_id, "file_ids": []})
    entry["file_ids"].append(file_id)

    # Debounce: cancel any pending job for this group and reschedule.
    # JobQueue.run_once with a repeated name replaces the prior job.
    for job in context.job_queue.get_jobs_by_name(media_group_id):
        job.schedule_removal()
    context.job_queue.run_once(
        _process_group,
        when=config.ALBUM_DEBOUNCE_SECONDS,
        data=media_group_id,
        name=media_group_id,
    )


def register(app, allowed_user_filter) -> None:
    app.add_handler(MessageHandler(filters.PHOTO & allowed_user_filter, on_photo))
