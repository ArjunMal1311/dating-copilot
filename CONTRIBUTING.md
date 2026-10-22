# Contributing

This is a **screenshot-in, draft-out copilot**. It never logs into a dating
app, never swipes, and never sends a message. Pull requests that add account
clients, unofficial APIs, or swipe/send automation will be closed.

## Adding a profile format

1. Copy `apps/generic.md` to `apps/<slug>.md`. Use a format name
   (`like_comment`, `essays`), never a product name.
2. Fill in: how likes/messages work, what's on a profile, what the hook
   (`target_prompt`) means, screenshot hints.
3. Add the slug to `KNOWN_APPS` and `DISPLAY_NAMES` in `apps.py`.

Do not add per-app Python packages, plugins, or product names. One judge,
one catalog. Capture is optional; the normal path is `judge.py` for existing
screenshots or `grab.py` for Waydroid.

## Voice and identity

Keep operator-specific typing rules (age, city, slang) out of `memory.py`.
They belong in the operator's `context.md`. The default prompt matches
whatever is in that file.

## Privacy

Never commit `context.md`, `*.db`, or screenshots. Images go to the
configured LLM provider for one judge call and nowhere else.
