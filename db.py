"""SQLite storage for generic-bot.

Three tables, no ORM — this is a single-user personal bot, not a service.
A fresh connection is opened per call; at this volume (a handful of writes
a day) that costs nothing and avoids any connection-lifecycle bugs.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterator

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    decision        TEXT NOT NULL,      -- 'like' | 'skip'
    reasoning       TEXT NOT NULL DEFAULT '',
    target_prompt   TEXT NOT NULL DEFAULT '',
    draft_message   TEXT NOT NULL DEFAULT '',
    final_message   TEXT,               -- NULL until confirmed
    was_edited      INTEGER,            -- NULL until confirmed; 0 or 1 after
    user_action     TEXT                -- NULL | 'liked' | 'skipped'
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


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- decisions ----------

def insert_decision(
    decision: str,
    reasoning: str,
    target_prompt: str,
    draft_message: str,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO decisions (ts, decision, reasoning, target_prompt, "
            "draft_message) VALUES (?, ?, ?, ?, ?)",
            (_now(), decision, reasoning, target_prompt, draft_message),
        )
        return cur.lastrowid


def get_decision(decision_id: int) -> sqlite3.Row | None:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision_id,)
        ).fetchone()


def set_user_action(decision_id: int, action: str) -> None:
    assert action in ("liked", "skipped")
    with _conn() as conn:
        conn.execute(
            "UPDATE decisions SET user_action = ? WHERE id = ?",
            (action, decision_id),
        )


def set_final_message(decision_id: int, final_message: str, was_edited: bool) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE decisions SET final_message = ?, was_edited = ? WHERE id = ?",
            (final_message, int(was_edited), decision_id),
        )


def get_recent_voice_examples(limit: int) -> list[sqlite3.Row]:
    """Confirmed sent messages, most recent first — the voice bank."""
    with _conn() as conn:
        return conn.execute(
            "SELECT target_prompt, final_message FROM decisions "
            "WHERE user_action = 'liked' AND final_message IS NOT NULL "
            "AND final_message != '' "
            "ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()


def count_decisions() -> dict[str, int]:
    """Funnel counts for /report."""
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
            "SELECT id, ts, text FROM context_notes WHERE active = 1 "
            "ORDER BY ts DESC LIMIT ?",
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
