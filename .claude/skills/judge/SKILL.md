---
name: judge
description: judge a dating profile from screenshots — LIKE/SKIP + which hook to answer + an opener in the user's voice, then log what actually happened
trigger: /judge
---

# /judge

Screenshots of one dating profile in → LIKE or SKIP, which hook to
answer, and a draft opener in the user's real voice. The user sends every
message and makes every swipe themselves — this only reads screenshots and
replies with text.

Backed by the `dating` MCP server (`dating_mcp.py` in this repo). Tools
appear as `mcp__dating__*` (or `mcp_dating_*` depending on the client).
Shares one `dating.db` + `context.md` with the standalone Telegram bot.

## Usage

```
/judge <path> [<path> ...]     # judge one profile from these screenshot files
/judge                         # then paste/point at the screenshot paths
```

Pass `app` as generic (default), generic, generic, generic, or generic.
Screenshots must be **files on disk**, top-to-bottom profile order. 1–12
images, all one profile.

## Live capture instead of pasting screenshots

`grab.py` can capture a profile off a Waydroid/KWin window. Optional,
Linux-only, not the happy path. Ask first: **"Is the dating-app profile
you want to judge visible in the window you'll focus?"**

```
.venv/bin/python grab.py --app generic
.venv/bin/python grab.py --manual --app generic
```

Click into the profile window during the countdown. Capture uses
`spectacle -a` (active window). It never likes, skips, or types.

## Flow

1. **Judge.** Call `judge_profile` with `image_paths` and `app`. Show
   LIKE/SKIP, the hook (`target_prompt`), the `draft_message`, backups.
2. **User acts in the app.** Then `record_outcome`, and if they sent,
   `record_sent_message` with the exact text.
3. Later: `record_match_result`.

Other tools: `add_about_note`, `list_about_notes`, `forget_about_note`,
`log_week`, `weekly_history`, `funnel_report`.

The judge quality rides on `context.md` + the voice examples in the DB.
Backend is `LLM_BACKEND` in `.env`.
