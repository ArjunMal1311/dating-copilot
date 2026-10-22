---
name: judge
description: Directly review profile screenshots or capture the active Waydroid profile, then return a like/skip recommendation and opener drafts in the user's voice. Use when the user asks to judge a profile, select a profile photo prompt to answer, draft an opener from screenshots, or capture a visible Waydroid profile.
---

# Direct profile review

Screenshots of one dating profile in → LIKE or SKIP, which hook to
answer, and a draft opener in the user's real voice. The user sends every
message and makes every swipe themselves — this only reads screenshots and
replies with text.

## Inputs

```
/judge <path> [<path> ...]     # judge one profile from screenshot files
/judge                         # capture the visible Waydroid profile
```

Pass `app` as a format: generic (default), like_comment,
match_then_message, she_opens, or essays. Screenshots must be **files on
disk**, top-to-bottom profile order. 1–12 images, all one profile.

## Execution

1. Choose the format from the screenshots. Use `generic` unless the user
   identifies one of the named interaction formats.
2. If the user supplied paths, run:

```
.venv/bin/python judge.py --app <format> <path> [<path> ...]
```

3. If no files were supplied and Waydroid is visible, ask whether the profile
   is ready, then run:

```
.venv/bin/python grab.py --app <format>
```

Use `--manual` only when the user needs to focus or scroll the window
themselves. Capture only reads pixels and scrolls; it never likes, skips, or
sends text.

## Response

Report the decision, short reasoning, the target detail, the recommended
draft, and backups. Never imply that an action was taken. If the user later
shares what they did, offer to record it through the local MCP helper only
when that integration is available.

The judge quality rides on `context.md` + the voice examples in the DB.
Backend is `LLM_BACKEND` in `.env`.
