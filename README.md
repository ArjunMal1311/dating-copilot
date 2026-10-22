# dating-copilot

Send it screenshots of a dating profile (Generic, Generic, Generic, Generic,
or anything similar). It tells you LIKE or SKIP, which detail to answer,
and drafts an opener in your actual voice. You review, edit if you want,
and send everything yourself — **the copilot never touches the app.**
Zero account automation, zero unofficial APIs.

## What it does

- Send a profile album (or a single photo) → judged against your
  `context.md` → LIKE/SKIP + reasoning, and if LIKE, a target/hook + a
  draft opener (or no draft, which is a valid answer).
- Tell it which app the shots are from (`/app generic`, or `app=` on the
  MCP tool). Default is Generic so existing workflows don't break.
- Two taps close the loop: **liked/skipped**, then **sent as-is/edited**
  (so the message you *actually sent* becomes a voice example).
- `/about <text>` — tell it something new about you; it remembers.
- `/week likes=X matches=Y dates=Z` — log your week.
- `/report` — a plain-rule funnel diagnosis, including a split by app
  once you've judged more than one.

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
cp context.md.example context.md
```

Fill `context.md` — especially **Your voice**. A thin identity doc
produces generic copy.

### Telegram

1. Message **@BotFather** → `/newbot` → put the token in `.env` as
   `TELEGRAM_BOT_TOKEN`.
2. Message **@userinfobot** for your numeric id → `TELEGRAM_ALLOWED_USER_ID`.
   The bot ignores everyone else.

### Judge backend

Default is Gemini (`GEMINI_API_KEY`). Claude: `LLM_BACKEND=claude` plus
`ANTHROPIC_API_KEY` and `pip install -r requirements-claude.txt`. Or
`LLM_BACKEND=gateway` against a running ai-gateway (`LLM_GATEWAY_URL`)
so this process holds no provider key.

`DEFAULT_APP=generic` unless you change it.

## Run it

```
.venv/bin/python bot.py
```

Long-polling — no public port. `/start`, then send a profile. `/app generic`
before an album if the shots aren't Generic.

Optional Linux/KWin window grab (not required):

```
.venv/bin/python grab.py --manual --app generic
```

That captures the focused window. It never likes or types.

## MCP

```
.venv/bin/pip install -r requirements-mcp.txt
```

```yaml
mcp_servers:
  dating:
    command: /ABSOLUTE/PATH/TO/dating-copilot/.venv/bin/python
    args: ["-m", "dating_mcp"]
```

| Tool | Maps to |
|---|---|
| `judge_profile(image_paths, app="generic")` | screenshots → verdict + drafts |
| `record_outcome` / `record_sent_message` / `record_match_result` | close the loop |
| `add_about_note` / `list_about_notes` / `forget_about_note` | `/about` |
| `log_week` / `weekly_history` / `funnel_report` | `/week` / `/history` / `/report` |

## Privacy

`context.md`, `*.db`, and `.env` are gitignored. Her photos, your identity
doc, and every message you've sent stay local. Images are sent to whichever
judge backend you configured for the single API call that judges them, and
nowhere else.

## License

MIT. See [CONTRIBUTING.md](CONTRIBUTING.md) if you want to add an app
profile (`apps/<slug>.md`) — not an account client. Opener research:
[docs/research.md](docs/research.md).
