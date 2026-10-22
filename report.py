"""Deterministic funnel diagnosis for the local record and MCP tool.

Rule-based, not LLM-based, on purpose: the same numbers must always produce
the same read, and week-to-week noise is bigger than most real effects.
"""

from __future__ import annotations

import db
from llm.base import LANES


def lane_breakdown() -> str:
    """Reply/match rate per opener angle, from what was actually sent.
    Empty string until at least one sent message has a known angle."""
    rows = db.lane_stats()
    if not rows:
        return ""
    lines = ["opener angles (what you sent -> what happened):"]
    for r in rows:
        label = LANES.get(r["lane"], r["lane"])
        known = r["known"] or 0
        result = (
            f"{r['matched'] or 0}/{known} matched, {r['replied'] or 0} replied"
            if known else "no results logged yet"
        )
        lines.append(f"  {label}: {r['sent']} sent, {result}")
    if sum(r["known"] or 0 for r in rows) < 10:
        lines.append(
            "  (under 10 results logged in total, so treat these as hints, "
            "not a verdict)"
        )
    return "\n".join(lines)


def diagnose() -> str:
    """Two header lines + one diagnosis line, then the per-angle breakdown
    once there is any data for it."""
    counts = db.count_decisions()
    stats = db.sum_recent_weekly_stats(weeks=4)

    lines = [
        f"last 4 weeks: {stats['likes_received']} likes received, "
        f"{stats['matches']} matches, {stats['dates']} dates "
        f"({stats['weeks_counted']} weeks logged)",
        f"bot has judged {counts['profiles_judged']} profiles, "
        f"recommended {counts['likes_recommended']} likes, "
        f"you confirmed {counts['likes_confirmed']} sent.",
        "",
    ]

    if stats["weeks_counted"] < 2:
        lines.append(
            "not enough weekly data yet — log at least 2 weeks "
            "before this diagnosis means anything. week-to-week noise is "
            "bigger than most real effects."
        )
    elif counts["likes_confirmed"] < 5:
        lines.append(
            "you've barely sent any likes yet. nothing else in this report "
            "is meaningful until there's volume — keep sending screenshots."
        )
    elif stats["likes_received"] > 0 and stats["matches"] == 0:
        lines.append(
            "likes received but zero matches — your bar or your openers, "
            "not your profile. check /history against what you changed."
        )
    elif counts["likes_confirmed"] > 0 and stats["matches"] == 0:
        lines.append(
            "you're liking people but not matching — either the rubric "
            "(context.md) is picking people who wouldn't reciprocate, or "
            "your profile isn't landing. this bot can't see your profile — "
            "check that separately."
        )
    elif stats["matches"] > 0 and stats["dates"] == 0:
        lines.append(
            "you're matching but zero dates — this is very likely you not "
            "asking. matches without a next step go cold fast."
        )
    else:
        lines.append(
            "funnel looks like it's moving at every stage. keep logging — "
            "the interesting signal shows up over several more weeks."
        )

    by_app = db.count_decisions_by_app()
    if len(by_app) > 1:
        bits = [
            f"{r['app']}: {r['judged']} judged, {r['liked'] or 0} liked"
            for r in by_app
        ]
        lines += ["", "by app: " + "; ".join(bits)]

    breakdown = lane_breakdown()
    if breakdown:
        lines += ["", breakdown]
    return "\n".join(lines)
