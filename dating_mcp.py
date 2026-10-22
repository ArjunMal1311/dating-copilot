"""Local judge engine with an optional MCP server interface.

Use ``judge.py`` for profile screenshots or ``grab.py`` for a Waydroid
capture. This module exposes the same functions to an MCP client when one is
useful. Decisions, voice examples, and reports are stored locally in
``dating.db``.

To register the optional MCP interface, add:

    mcp_servers:
      dating:
        command: /ABSOLUTE/PATH/TO/dating-copilot/.venv/bin/python
        args: ["-m", "dating_mcp"]
        env:
          GEMINI_API_KEY: "your-key"      # or put it in dating-copilot/.env

Env needed (.env or the mcp_servers env: block): GEMINI_API_KEY,
and optionally GEMINI_MODEL / LLM_BACKEND / USER_NAME / CONTEXT_MD_PATH /
DEFAULT_APP / VOICE_SAMPLE_COUNT / CONTEXT_NOTE_LIMIT.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import config
import db
import report
from judge_service import judge_profile as _judge_profile
from llm.base import LANES

mcp = FastMCP("dating")


@mcp.tool()
def judge_profile(image_paths: list[str], app: str = "generic") -> dict:
    """Judge ONE dating-app profile from its screenshot files.

    image_paths: absolute paths (or file:// URLs) to the profile's
    screenshots — photos and any text (prompts, bio, essays) — in the order
    they appear top-to-bottom in the app. 1 to 12 images, all one profile.

    app: generic | like_comment | match_then_message | she_opens | essays
    (default generic). Format of the profile, not a product name.

    Returns a dict:
      decision_id     int
      decision        str   — "like" or "skip"
      reasoning       str
      target_prompt   str   — target / hook (prompt, bio line, photo, …)
      draft_message   str   — opener in the user's voice ("" if skip / no hook)
      draft_lane      str
      alternatives    list
      app             str

    After the user acts in the app, call record_outcome; if they liked and
    sent, also call record_sent_message with the exact text they sent.
    """
    return _judge_profile(image_paths, app)


@mcp.tool()
def record_outcome(decision_id: int, action: str) -> str:
    """Record what the user ACTUALLY did for a judged
    profile, so tracked counts match reality instead of the recommendation.

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
    """Save the message the user ACTUALLY sent — not the draft — into the
    voice bank, where it becomes a few-shot example on future drafts.

    Call this only after the user liked and sent.
      final_text:  verbatim what they sent (the draft as-is, or their edit)
      was_edited:  False if they sent the draft unchanged, True if they changed it
      lane:        optional opener angle (a key of llm.base.LANES).

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
def record_match_result(decision_id: int, matched: bool, got_reply: bool | None = None) -> str:
    """Record what actually happened after a sent message — the real signal
    for which draft shapes work.

    Call this once you know: matched=False as soon as you know she didn't
    match; matched=True (with got_reply if known yet) once she does.
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
    """Add a fact about the user to persistent identity memory."""
    text = text.strip()
    if not text:
        raise ValueError("text is empty.")
    note_id = db.add_context_note(text)
    return f"noted (#{note_id})."


@mcp.tool()
def list_about_notes() -> list[dict]:
    """Return active identity notes, most recent first."""
    return [
        {"id": r["id"], "date": r["ts"][:10], "text": r["text"]}
        for r in db.list_active_notes(config.CONTEXT_NOTE_LIMIT)
    ]


@mcp.tool()
def forget_about_note(note_id: int) -> str:
    """Retire a stale identity note by id."""
    return "retired." if db.deactivate_note(note_id) else "no active note with that id."


@mcp.tool()
def log_week(
    likes: int | None = None,
    matches: int | None = None,
    dates: int | None = None,
) -> str:
    """Log this week's funnel numbers. Any subset."""
    if likes is None and matches is None and dates is None:
        raise ValueError("pass at least one of likes / matches / dates.")
    week_start = db.current_week_start()
    db.upsert_weekly_stats(week_start, likes_received=likes, matches=matches, dates=dates)
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
    """Deterministic funnel diagnosis — which stage is leaking."""
    return report.diagnose()


def main() -> None:
    config.check_context_file()
    db.init_db()
    mcp.run()


if __name__ == "__main__":
    main()
