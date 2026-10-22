"""SQLite storage for dating-copilot.

Three tables, no ORM — this is a single-user local tool, not a service.
A fresh connection is opened per call; at this volume (a handful of writes
a day) that costs nothing and avoids any connection-lifecycle bugs.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    decision        TEXT NOT NULL,      -- 'like' | 'skip'
    reasoning       TEXT NOT NULL DEFAULT '',
    target_prompt   TEXT NOT NULL DEFAULT '',
    draft_message   TEXT NOT NULL DEFAULT '',
    draft_lane      TEXT,               -- opener shape of draft_message (llm.base.LANES)
    alternatives    TEXT,               -- JSON list of backup drafts [{lane, target, message}]
    final_message   TEXT,               -- NULL until confirmed
    sent_lane       TEXT,               -- shape of what was actually sent, NULL if unknown
    was_edited      INTEGER,            -- NULL until confirmed; 0 or 1 after
    user_action     TEXT,               -- NULL | 'liked' | 'skipped'
    matched         INTEGER,            -- NULL unknown; 0 or 1 once she's had a chance to respond
    got_reply       INTEGER,            -- NULL unknown; 0 or 1 once matched
    app             TEXT NOT NULL DEFAULT 'generic'
);

CREATE TABLE IF NOT EXISTS context_notes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    text     TEXT NOT NULL,
    active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS weekly_stats (
    week_start      TEXT PRIMARY KEY,   -- ISO date, Monday of that week
    likes_received  INTEGER,
    matches         INTEGER,
    dates           INTEGER,
    note            TEXT
);
"""


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(decisions)")}
        for col, typ in (
            ("matched", "INTEGER"),
            ("got_reply", "INTEGER"),
            ("draft_lane", "TEXT"),
            ("alternatives", "TEXT"),
            ("sent_lane", "TEXT"),
            ("app", "TEXT"),
        ):
            if col not in existing:
                conn.execute(f"ALTER TABLE decisions ADD COLUMN {col} {typ}")
        conn.execute(
            "UPDATE decisions SET app = 'generic' WHERE app IS NULL OR app = '' "
            "OR app NOT IN ('generic','like_comment','match_then_message',"
            "'she_opens','essays')"
        )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- decisions ----------


def insert_decision(
    decision: str,
    reasoning: str,
    target_prompt: str,
    draft_message: str,
    draft_lane: str = "",
    alternatives: list[dict] | None = None,
    app: str = "generic",
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO decisions (ts, decision, reasoning, target_prompt, "
            "draft_message, draft_lane, alternatives, app) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _now(),
                decision,
                reasoning,
                target_prompt,
                draft_message,
                draft_lane or None,
                json.dumps(alternatives or []),
                app or "generic",
            ),
        )
        return cur.lastrowid


def get_alternatives(row: sqlite3.Row) -> list[dict]:
    try:
        return json.loads(row["alternatives"] or "[]")
    except (ValueError, TypeError):
        return []


def infer_sent_lane(row: sqlite3.Row, final_message: str) -> str | None:
    """Which drafted angle the sent text came from: the closest of the main
    draft and the backups, if it's close enough to count as an edit of it
    rather than something he wrote from scratch."""
    candidates = []
    if row["draft_message"] and row["draft_lane"]:
        candidates.append((row["draft_message"], row["draft_lane"]))
    candidates += [(a["message"], a["lane"]) for a in get_alternatives(row)]
    best_lane, best_ratio = None, 0.0
    sent = final_message.strip().lower()
    for text, lane in candidates:
        ratio = SequenceMatcher(None, sent, text.strip().lower()).ratio()
        if ratio > best_ratio:
            best_lane, best_ratio = lane, ratio
    return best_lane if best_ratio >= 0.6 else None


def get_decision(decision_id: int) -> sqlite3.Row | None:
    with _conn() as conn:
        return conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()


def set_user_action(decision_id: int, action: str) -> None:
    assert action in ("liked", "skipped")
    with _conn() as conn:
        conn.execute(
            "UPDATE decisions SET user_action = ? WHERE id = ?",
            (action, decision_id),
        )


def set_final_message(
    decision_id: int,
    final_message: str,
    was_edited: bool,
    sent_lane: str | None = None,
) -> str | None:
    """Saves what was sent. sent_lane is inferred from the drafts when not
    given. Returns the lane that was stored (None if it couldn't be told)."""
    with _conn() as conn:
        if sent_lane is None:
            row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
            if row is not None:
                sent_lane = infer_sent_lane(row, final_message)
        conn.execute(
            "UPDATE decisions SET final_message = ?, was_edited = ?, sent_lane = ? WHERE id = ?",
            (final_message, int(was_edited), sent_lane, decision_id),
        )
    return sent_lane


def lane_stats() -> list[sqlite3.Row]:
    """Per opener angle: how many sent, and of those with a known result,
    how many matched / got a reply."""
    with _conn() as conn:
        return conn.execute(
            "SELECT sent_lane AS lane, COUNT(*) AS sent, "
            "SUM(matched IS NOT NULL) AS known, "
            "SUM(matched = 1) AS matched, "
            "SUM(got_reply = 1) AS replied "
            "FROM decisions "
            "WHERE user_action = 'liked' AND sent_lane IS NOT NULL "
            "GROUP BY sent_lane ORDER BY sent DESC"
        ).fetchall()


def set_match_result(decision_id: int, matched: bool, got_reply: bool | None = None) -> None:
    """Record what actually happened after a sent message — the only real
    signal for which draft shapes work, as opposed to which ones merely
    look clean."""
    with _conn() as conn:
        conn.execute(
            "UPDATE decisions SET matched = ?, got_reply = ? WHERE id = ?",
            (int(matched), None if got_reply is None else int(got_reply), decision_id),
        )


def get_recent_voice_examples(limit: int) -> list[sqlite3.Row]:
    """Confirmed sent messages — the voice bank. Ones known to have gotten a
    reply or a match come first; recency is only the tiebreaker, since a
    message that went nowhere isn't evidence of a voice worth repeating."""
    with _conn() as conn:
        return conn.execute(
            "SELECT target_prompt, final_message, matched, got_reply "
            "FROM decisions "
            "WHERE user_action = 'liked' AND final_message IS NOT NULL "
            "AND final_message != '' "
            "ORDER BY "
            "CASE WHEN got_reply = 1 THEN 0 "
            "     WHEN matched = 1 THEN 1 "
            "     WHEN matched = 0 THEN 3 "
            "     ELSE 2 END, "
            "ts DESC LIMIT ?",
            (limit,),
        ).fetchall()


def all_sent_messages() -> list[str]:
    """Every opener he has sent, for the never-reuse-a-line check. Not
    limited like the voice sample: a line sent once to anyone is spent."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT final_message FROM decisions "
            "WHERE final_message IS NOT NULL AND final_message != ''"
        ).fetchall()
    return [r["final_message"] for r in rows]


def count_decisions() -> dict[str, int]:
    """Funnel counts for reporting."""
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        liked_rec = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE decision = 'like'"
        ).fetchone()[0]
        liked_confirmed = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE user_action = 'liked'"
        ).fetchone()[0]
        skipped_confirmed = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE user_action = 'skipped'"
        ).fetchone()[0]
    return {
        "profiles_judged": total,
        "likes_recommended": liked_rec,
        "likes_confirmed": liked_confirmed,
        "skips_confirmed": skipped_confirmed,
    }


def count_decisions_by_app() -> list[sqlite3.Row]:
    """Judged / liked counts per profile format, for reporting."""
    with _conn() as conn:
        return conn.execute(
            "SELECT COALESCE(app, 'generic') AS app, COUNT(*) AS judged, "
            "SUM(user_action = 'liked') AS liked "
            "FROM decisions GROUP BY COALESCE(app, 'generic') "
            "ORDER BY judged DESC"
        ).fetchall()


# ---------- context_notes ----------


def add_context_note(text: str) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO context_notes (ts, text, active) VALUES (?, ?, 1)",
            (_now(), text),
        )
        return cur.lastrowid


def list_active_notes(limit: int) -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            "SELECT id, ts, text FROM context_notes WHERE active = 1 ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()


def deactivate_note(note_id: int) -> bool:
    """Returns False if no active note with that id existed."""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE context_notes SET active = 0 WHERE id = ? AND active = 1",
            (note_id,),
        )
        return cur.rowcount > 0


# ---------- weekly_stats ----------


def current_week_start(today: date | None = None) -> str:
    """ISO date of the Monday on or before `today` (default: today)."""
    d = today or date.today()
    return (d - timedelta(days=d.weekday())).isoformat()


def upsert_weekly_stats(
    week_start: str,
    likes_received: int | None = None,
    matches: int | None = None,
    dates: int | None = None,
    note: str | None = None,
) -> None:
    with _conn() as conn:
        existing = conn.execute(
            "SELECT * FROM weekly_stats WHERE week_start = ?", (week_start,)
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO weekly_stats (week_start, likes_received, "
                "matches, dates, note) VALUES (?, ?, ?, ?, ?)",
                (week_start, likes_received, matches, dates, note),
            )
        else:
            conn.execute(
                "UPDATE weekly_stats SET "
                "likes_received = COALESCE(?, likes_received), "
                "matches = COALESCE(?, matches), "
                "dates = COALESCE(?, dates), "
                "note = COALESCE(?, note) "
                "WHERE week_start = ?",
                (likes_received, matches, dates, note, week_start),
            )


def list_weekly_stats(limit: int = 12) -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM weekly_stats ORDER BY week_start DESC LIMIT ?",
            (limit,),
        ).fetchall()


def sum_recent_weekly_stats(weeks: int = 4) -> dict[str, int]:
    rows = list_weekly_stats(limit=weeks)
    return {
        "matches": sum(r["matches"] or 0 for r in rows),
        "dates": sum(r["dates"] or 0 for r in rows),
        "likes_received": sum(r["likes_received"] or 0 for r in rows),
        "weeks_counted": len(rows),
    }
