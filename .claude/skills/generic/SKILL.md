---
name: generic
description: judge a Generic profile from screenshots — LIKE/SKIP + which prompt to answer + an opener in the user's voice, then log what actually happened
trigger: /generic
---

# /generic

Screenshots of one Generic profile in → LIKE or SKIP, which of her prompts to
answer, and a draft opener in the user's real voice. The user sends every
message and makes every swipe themselves — this only reads screenshots and
replies with text.

Backed by the `generic` MCP server (`generic_mcp.py` in
`/home/atg/Documents/Personal/generic-bot`). Tools appear as `mcp__generic__*`.
Shares one `generic.db` + `context.md` with the standalone Telegram bot, so
judgements and funnel stats stay unified across both.

## Usage

```
/generic <path> [<path> ...]     # judge one profile from these screenshot files
/generic                         # then paste/point at the screenshot paths
```

Screenshots must be **files on disk** — pass paths, in top-to-bottom profile
order (her photos and prompt answers). 1–12 images, all one profile.

## Live capture instead of pasting screenshots

`grab.py` (in `generic-bot/`) captures a profile straight off the Waydroid
window and judges it in one shot — no manual screenshotting or pasting.

Before starting a live capture, ask: **"Is Waydroid open with the Generic
profile you want to judge visible?"** Wait for confirmation. If it is not
active, have the user start it, then ask again:

```
waydroid session start &
waydroid show-full-ui &
```

The container is already initialized with GAPPS, multi-window mode, and a
shrunk display resolution. These settings persist across reboots.

After the user confirms, run the capture:
```
cd generic-bot && .venv/bin/python grab.py
```
It prints a countdown (default 3s, `-l` to change) before capturing —
**click into the Waydroid profile window during the countdown**, since
capture uses `spectacle -a` (active window). Whatever has real focus at
capture time is what gets grabbed — if the countdown ends before you click
in, it'll capture whatever editor/terminal was focused instead (the judge
usually catches this and SKIPs rather than hallucinating a profile, but
it's a wasted call). Once focused, click-drag-scrolling the profile keeps
focus on it for the whole burst — no need to re-click each frame.

It captures, dedupes near-identical frames, calls `judge_profile` itself,
and prints the verdict plus the exact `record_outcome`/`record_sent_message`
calls to run after. Flags: `-s` burst seconds (default 12, longer for long
profiles), `-i` interval, `--no-judge` to just capture.

## Flow

1. **Judge.** Call `mcp__generic__judge_profile` with `image_paths`. It returns
   `{decision_id, decision, reasoning, target_prompt, draft_message,
   draft_lane, alternatives}` and persists the row immediately. Show the user:
   - **LIKE** / **SKIP** + the one-line reasoning
   - if LIKE: which prompt (`target_prompt`) and the `draft_message` verbatim,
     tagged with its angle (`draft_lane`)
   - then each backup in `alternatives` (0–2), with what it answers
     (`target`) and its angle (`lane`). Each is a different angle on purpose
     (question / guess / take a side / small thing / scenario / sincere /
     dry riff) so he can pick the one that sounds most like him.
   - if a draft breaks a rule from `memory.py` that the lint missed (stock
     phrase, backhanded line, made-up test), say so plainly rather than
     presenting it as good
   - remember the `decision_id` for this conversation

   If a prompt or photo references something you don't already know cold
   (a comedian's specific bit, a show, a meme, a current trend, a place),
   `WebSearch` it before drafting or explaining — don't guess or answer from
   stale memory. Same goes for follow-up drafts: if the user wants a reel
   idea, a callback, or anything tied to "what's trending right now," search
   first, then write the draft in voice. A correct specific beats a vague
   generic every time.

2. **User acts in Generic** (their swipe, their send). Then close the loop:
   - `mcp__generic__record_outcome(decision_id, "liked" | "skipped")` — what they
     actually did, so tracked counts match reality (not the recommendation).
   - If they liked **and** sent a message:
     `mcp__generic__record_sent_message(decision_id, final_text, was_edited)` —
     `final_text` is exactly what they sent (the draft as-is, a backup, or
     their edit); `was_edited` false if unchanged. The angle is inferred
     from whichever draft or backup the text is closest to; pass
     `lane="..."` only if he wrote something new in a clear angle. This
     feeds the voice bank and the per-angle reply stats, so always capture
     it when a message went out.
   - Later, when he knows: `mcp__generic__record_match_result(decision_id,
     matched, got_reply)`. Without this the angle stats stay empty.

   Ask for both conversationally ("did you send it? what did you actually
   send?") — there's no button here.

## Other tools

| Ask | Tool |
|---|---|
| "remember I <fact about me>" | `mcp__generic__add_about_note(text)` |
| "what do you know about me" | `mcp__generic__list_about_notes()` |
| "forget note 3" | `mcp__generic__forget_about_note(note_id)` |
| "log this week: 14 likes, 3 matches, 1 date" | `mcp__generic__log_week(likes=, matches=, dates=)` — any subset |
| "show my weekly numbers" | `mcp__generic__weekly_history()` |
| "where's my funnel leaking" / "which openers work" | `mcp__generic__funnel_report()` — deterministic rule read, plus match/reply rate per opener angle once results are logged |

## Notes

- The judge quality rides entirely on `context.md` (who the user is, what they
  want) + the voice examples in the DB. A thin `context.md` → generic output.
- Backend is set in `generic-bot/.env` (`LLM_BACKEND` = `gemini` | `claude` |
  `gateway`). `gateway` routes through the local ai-gateway on
  `LLM_GATEWAY_URL` and needs no provider key here.
- If `judge_profile` errors with "ai-gateway unreachable" → the gateway
  service isn't running (`cd ~/Documents/GitHub/gemini && docker compose up`).
