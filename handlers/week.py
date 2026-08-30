"""/week, /report, /history — the funnel side.

/week likes=14 matches=3 dates=1     log this week's numbers
/report                              deterministic bottleneck diagnosis
/history                             raw table of weekly_stats
"""

from __future__ import annotations

import re

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

import db

_KV_RE = re.compile(r"(likes|matches|dates)\s*=\s*(\d+)")


async def week_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args)
    values = {k: int(v) for k, v in _KV_RE.findall(text)}
    if not values:
        await update.message.reply_text(
            "usage: /week likes=14 matches=3 dates=1\n"
            "(any subset — leave out what you don't have yet)"
        )
        return

    week_start = db.current_week_start()
    db.upsert_weekly_stats(
        week_start,
        likes_received=values.get("likes"),
        matches=values.get("matches"),
        dates=values.get("dates"),
    )
    await update.message.reply_text(f"logged for week of {week_start}: {values}")


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = db.list_weekly_stats(limit=12)
    if not rows:
        await update.message.reply_text("no weekly numbers logged yet. try /week likes=X matches=Y dates=Z")
        return
    lines = ["week         likes  match  dates"]
    for r in rows:
        lines.append(
            f"{r['week_start']}   "
            f"{r['likes_received'] if r['likes_received'] is not None else '-':>5}  "
            f"{r['matches'] if r['matches'] is not None else '-':>5}  "
            f"{r['dates'] if r['dates'] is not None else '-':>5}"
        )
    await update.message.reply_text("```\n" + "\n".join(lines) + "\n```", parse_mode="MarkdownV2")


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    await update.message.reply_text("\n".join(lines))


def register(app, allowed_user_filter) -> None:
    app.add_handler(CommandHandler("week", week_cmd, filters=allowed_user_filter))
    app.add_handler(CommandHandler("history", history_cmd, filters=allowed_user_filter))
    app.add_handler(CommandHandler("report", report_cmd, filters=allowed_user_filter))
