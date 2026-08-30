# generic-bot

Send it a screenshot of a Generic profile. It tells you LIKE or SKIP, which
of her prompts to respond to, and drafts an opener in your actual voice.
You review, edit if you want, and send everything yourself in Generic — the
bot never touches the app. Zero automation of your account, zero ToS risk.

Companion to `generic-lab` (the profile analyzer) — different tool, same
`context.md` idea. This one's for judging *her* profile and drafting what
to say; generic-lab is for fixing *your* profile.

## What it does

- Send a profile album (or a single photo) → judged against your
  `context.md` → LIKE/SKIP + reasoning, and if LIKE, which prompt to
  answer + a draft opener.
- Two taps close the loop: **liked/skipped** (so tracked counts match what
  you actually did), then **sent as-is/edited** (so the message you
  *actually sent* — not the draft — becomes a voice example for next time).
- `/about <text>` — tell it something new about you; it remembers.
- `/week likes=X matches=Y dates=Z` — log your week.
- `/report` — a plain-rule funnel diagnosis: are likes converting to
  matches, are matches converting to dates, where's the actual leak.

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

### Get a Telegram bot token

1. Message **@BotFather** on Telegram.
2. `/newbot`, follow the prompts, name it whatever.
3. Copy the token it gives you into `.env` as `TELEGRAM_BOT_TOKEN`.
4. Message **@userinfobot** to get your own numeric Telegram user id, put
   it in `.env` as `TELEGRAM_ALLOWED_USER_ID`. The bot ignores anyone else
   who messages it — this is a personal tool, not a public one.

### Get a Gemini key (default backend)

1. <https://aistudio.google.com/apikey> → create a key.
2. Put it in `.env` as `GEMINI_API_KEY`.

Want Claude instead? Set `LLM_BACKEND=claude`, add `ANTHROPIC_API_KEY`, and
`.venv/bin/pip install -r requirements-claude.txt`. Same schema, same
prompt, different SDK underneath — see `llm/base.py`.

### Fill in context.md

```
cp context.md.example context.md
```

Fill it in — or, if you already built `generic-lab`, skip the copy and point
`CONTEXT_MD_PATH` in `.env` at that project's `context.md` instead, so
you're maintaining one identity document, not two.

This file is read on every single judge call. It's the entire reason the
bot can pick a relevant prompt and write in your voice instead of
generic dating-app copy.

## Run it

```
.venv/bin/python bot.py
```

Long-polling — no public port, no webhook. Keeps running as long as this
process is alive. Message the bot `/start` to confirm it's up, then send
it a profile.

Runs on your machine while it's on. If you want it reachable with your
laptop closed, move it to a cheap always-on box later (a $5/mo VPS, same
code, `systemd` or `tmux` to keep it alive) — not needed to try it out.

## Commands

| Command | Does |
|---|---|
| send photo(s) | judges the profile, replies with verdict + draft |
| `/about <text>` | add a fact about yourself |
| `/about list` | show what it remembers |
| `/about forget <id>` | retire a stale note |
| `/week likes=14 matches=3 dates=1` | log this week (any subset) |
| `/report` | funnel diagnosis |
| `/history` | raw weekly numbers |

## Troubleshooting

- **"Gemini returned no text (likely blocked)"** — the safety filter
  flagged the images. `llm/gemini.py` already loosens the four harm
  categories to `BLOCK_ONLY_HIGH`; if it's still blocking, that's the
  first place to widen further.
- **Model not found** — `GEMINI_MODEL` in `.env` (default
  `gemini-3.5-flash`) may not match what's available to your key/region.
  `.venv/bin/python -c "from google import genai; [print(m.name) for m in genai.Client(api_key='YOUR_KEY').models.list()]"`
  lists what you actually have access to.
- **Album judged as several single photos instead of one profile** —
  Telegram only groups photos sent together as one *album* (select
  multiple in the picker, or forward them together), not several separate
  single-photo messages in a row.

## Privacy

`context.md`, `generic.db`, and `.env` are gitignored. All of it — her
photos, your identity doc, every message you've sent — stays local. Images
are sent to whichever judge backend you configured (Gemini or Claude) for
the single API call that judges them, and nowhere else.
