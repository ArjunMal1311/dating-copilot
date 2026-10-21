"""MCP server exposing generic-bot's judge, voice bank and funnel as tools.

Run this INSTEAD of bot.py when you want an existing MCP client (e.g. Hermes
Agent, already connected to Telegram/Discord/Slack) to drive the judge —
rather than generic-bot running its own Telegram bot. bot.py and handlers/ are
unused in this mode; db.py, memory.py, llm/, report.py and context.md are
shared verbatim, so a decision judged here shows up in the same generic.db and
/report as one judged by the standalone bot.

Register in the client. For Hermes, add to ~/.hermes/config.yaml:

    mcp_servers:
      generic:
        command: /ABSOLUTE/PATH/TO/generic-bot/.venv/bin/python
        args: ["-m", "generic_mcp"]
        env:
          GEMINI_API_KEY: "your-key"      # or put it in generic-bot/.env

then: systemctl --user restart hermes-gateway

Env needed (generic-bot/.env or the mcp_servers env: block): GEMINI_API_KEY,
and optionally GEMINI_MODEL / LLM_BACKEND / USER_NAME / CONTEXT_MD_PATH /
VOICE_SAMPLE_COUNT / CONTEXT_NOTE_LIMIT. The Telegram vars are NOT used here.
"""

from __future__ import annotations

import io
from pathlib import Path
from urllib.parse import unquote, urlparse

from mcp.server.fastmcp import FastMCP
from PIL import Image

import config
import db
import memory
import report
from llm import load_backend
from llm.base import LANES

mcp = FastMCP("generic")

# Same ceiling the standalone album handler works within — a Generic profile is
# at most a handful of screenshots.
_MAX_IMAGES = 12


def _resolve(path: str) -> Path:
    """Accept a plain path or a file:// URL (Hermes hands tools file:// paths
    for cached inbound images)."""
    if path.startswith("file://"):
        path = unquote(urlparse(path).path)
    return Path(path).expanduser()


def _downscale(fp: Path) -> bytes:
    """Long-edge downscale to JPEG — identical to handlers/photos.py so the
    judge sees the same thing either way."""
    with Image.open(fp) as img:
        img = img.convert("RGB")
        img.thumbnail((config.MAX_EDGE, config.MAX_EDGE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=config.JPEG_QUALITY)
        return buf.getvalue()


@mcp.tool()
def judge_profile(image_paths: list[str]) -> dict:
    """Judge ONE Generic profile from its screenshot files.

    image_paths: absolute paths (or file:// URLs) to the profile's
    screenshots — her photos and prompt answers — in the order they appear
    top-to-bottom in the app. 1 to 12 images, all one profile.

    Returns a dict:
      decision_id     int   — pass to record_outcome / record_sent_message
      decision        str   — "like" or "skip"
      reasoning       str   — one or two sentences, references a real detail
      target_prompt   str   — which of her prompts to answer ("" if skip / no hook)
      draft_message   str   — opener in the user's voice ("" if skip / no hook)
      draft_lane      str   — which opener angle draft_message uses ("" if none)
      alternatives    list  — up to 2 backups [{lane, target, message}], each
                              a different angle; may be empty

    The decision is persisted immediately. After the user acts in Generic, call
    record_outcome; if they liked and sent, also call record_sent_message
    with the exact text they sent so it feeds the voice bank.
    """
    if not image_paths:
        raise ValueError("image_paths is empty — pass the profile screenshots.")
    if len(image_paths) > _MAX_IMAGES:
        raise ValueError(
            f"got {len(image_paths)} images; max is {_MAX_IMAGES}. Send one "
            f"profile at a time."
        )

    images: list[bytes] = []
    for raw_path in image_paths:
        fp = _resolve(raw_path)
        if not fp.is_file():
            raise ValueError(f"not a readable file: {fp}")
        images.append(_downscale(fp))

    system_prompt = memory.build_system_prompt()
    decision = load_backend().judge(images, system_prompt)

    # The model doesn't reliably self-check a long rule list in one pass —
    # give it one shot to fix anything mechanically checkable before this
    # ever reaches the user.
    if decision.draft_message:
        issues = memory.check_draft(decision.draft_message)
        if issues:
            retry_prompt = (
                f"{system_prompt}\n\n"
                "# Your previous draft failed these checks\n\n"
                f'draft_message was: {decision.draft_message!r}\n'
                "Problems found:\n"
                + "\n".join(f"- {issue}" for issue in issues)
                + "\n\nRewrite draft_message to fix every problem above while "
                "keeping the same decision, reasoning and target_prompt. If "
                "no clean draft is possible, use an empty string instead."
            )
            retried = load_backend().judge(images, retry_prompt)
            if retried.draft_message or not decision.draft_message:
                decision = retried

    alternatives = memory.drop_failing_alternatives(decision.alternatives)

    # Last guard: a main draft that still copies a sent line never reaches
    # him. Promote the first clean backup, or fall back to no draft.
    if decision.draft_message and memory.reused_line(decision.draft_message):
        if alternatives:
            promoted = alternatives.pop(0)
            decision.draft_message = promoted["message"]
            decision.draft_lane = promoted["lane"]
            decision.target_prompt = promoted["target"] or decision.target_prompt
        else:
            decision.draft_message, decision.draft_lane = "", ""

    decision_id = db.insert_decision(
        decision=decision.decision,
        reasoning=decision.reasoning,
        target_prompt=decision.target_prompt,
        draft_message=decision.draft_message,
        draft_lane=decision.draft_lane,
        alternatives=alternatives,
    )
    return {
        "decision_id": decision_id,
        "decision": decision.decision,
        "reasoning": decision.reasoning,
        "target_prompt": decision.target_prompt,
        "draft_message": decision.draft_message,
        "draft_lane": decision.draft_lane,
        "alternatives": alternatives,
    }


@mcp.tool()
def record_outcome(decision_id: int, action: str) -> str:
    """Record what the user ACTUALLY did in Generic for a judged profile, so
    tracked counts match reality instead of the bot's recommendation.

    action: "liked" or "skipped".
    """
    action = action.strip().lower()
    if action not in ("liked", "skipped"):
        raise ValueError('action must be "liked" or "skipped".')
    if db.get_decision(decision_id) is None:
        raise ValueError(f"no decision with id {decision_id}.")
    db.set_user_action(decision_id, action)
    return f"recorded: {action} (#{decision_id})"


@mcp.tool()
def record_sent_message(
    decision_id: int, final_text: str, was_edited: bool, lane: str | None = None
) -> str:
    """Save the message the user ACTUALLY sent her — not the draft — into the
    voice bank, where it becomes a few-shot example on future drafts.

    Call this only after the user liked and sent.
      final_text:  verbatim what they sent (the draft as-is, or their edit)
      was_edited:  False if they sent the draft unchanged, True if they changed it
      lane:        optional opener angle of what was sent (a key of
                   llm.base.LANES). Leave it out and it's inferred from
                   whichever draft or backup the text is closest to.

    Implies the outcome was "liked" and sets it if not already recorded.
    """
    row = db.get_decision(decision_id)
    if row is None:
        raise ValueError(f"no decision with id {decision_id}.")
    if not final_text.strip():
        raise ValueError("final_text is empty — pass what was actually sent.")
    if row["user_action"] != "liked":
        db.set_user_action(decision_id, "liked")
    if lane is not None and lane not in LANES:
        raise ValueError(f"lane must be one of {sorted(LANES)} or omitted.")
    stored = db.set_final_message(
        decision_id, final_text, was_edited=bool(was_edited), sent_lane=lane
    )
    return (
        f"saved to voice memory (#{decision_id}, edited={bool(was_edited)}, "
        f"angle={stored or 'unknown'})"
    )


@mcp.tool()
def record_match_result(
    decision_id: int, matched: bool, got_reply: bool | None = None
) -> str:
    """Record what actually happened after a sent message — the real signal
    for which draft shapes work, since a clean-looking draft that gets
    ignored is worse evidence than a rough one that gets a reply.

    Call this once you know: matched=False as soon as you know she didn't
    match; matched=True (with got_reply if known yet) once she does. Safe to
    call again later with got_reply once that's known too.
    """
    row = db.get_decision(decision_id)
    if row is None:
        raise ValueError(f"no decision with id {decision_id}.")
    db.set_match_result(decision_id, matched=matched, got_reply=got_reply)
    detail = "matched" if matched else "no match"
    if got_reply is not None:
        detail += ", replied" if got_reply else ", no reply"
    return f"recorded (#{decision_id}): {detail}"


@mcp.tool()
def add_about_note(text: str) -> str:
    """Add a fact about the user to persistent identity memory (like /about
    <text>). Folded into every future judge call."""
    text = text.strip()
    if not text:
        raise ValueError("text is empty.")
    note_id = db.add_context_note(text)
    return f"noted (#{note_id})."


@mcp.tool()
def list_about_notes() -> list[dict]:
    """Active identity notes, most recent first (like /about list)."""
    return [
        {"id": r["id"], "date": r["ts"][:10], "text": r["text"]}
        for r in db.list_active_notes(config.CONTEXT_NOTE_LIMIT)
    ]


@mcp.tool()
def forget_about_note(note_id: int) -> str:
    """Retire a stale identity note by id — soft delete (like /about forget)."""
    return "retired." if db.deactivate_note(note_id) else "no active note with that id."


@mcp.tool()
def log_week(
    likes: int | None = None,
    matches: int | None = None,
    dates: int | None = None,
) -> str:
    """Log this week's funnel numbers (like /week). Any subset — pass only
    what you have. Upserts the current (Monday-anchored) week."""
    if likes is None and matches is None and dates is None:
        raise ValueError("pass at least one of likes / matches / dates.")
    week_start = db.current_week_start()
    db.upsert_weekly_stats(
        week_start, likes_received=likes, matches=matches, dates=dates
    )
    logged = ", ".join(
        f"{k}={v}"
        for k, v in (("likes", likes), ("matches", matches), ("dates", dates))
        if v is not None
    )
    return f"logged for week of {week_start}: {logged}"


@mcp.tool()
def weekly_history() -> list[dict]:
    """Raw weekly_stats, most recent first, up to 12 weeks (like /history)."""
    return [
        {
            "week_start": r["week_start"],
            "likes_received": r["likes_received"],
            "matches": r["matches"],
            "dates": r["dates"],
        }
        for r in db.list_weekly_stats(limit=12)
    ]


@mcp.tool()
def funnel_report() -> str:
    """Deterministic funnel diagnosis — which stage is leaking (like /report).
    Rule-based; the same numbers always produce the same read."""
    return report.diagnose()


def main() -> None:
    config.check_context_file()  # warn (not fail) if context.md is missing
    db.init_db()
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
