"""Deterministic funnel diagnosis — shared by /report (handlers/week.py) and
the funnel_report MCP tool (generic_mcp.py).

Rule-based, not LLM-based, on purpose: the same numbers must always produce
the same read, and week-to-week noise is bigger than most real effects.
"""

from __future__ import annotations

import db


def diagnose() -> str:
    """Two header lines + exactly one diagnosis line, joined by newlines."""
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
            "not enough weekly data yet — log /week for at least 2 weeks "
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

    return "\n".join(lines)
