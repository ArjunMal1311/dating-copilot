# dating-copilot

A local-first, screenshot-in copilot for reviewing dating profiles and
drafting openers in your own voice.

It reads screenshots, returns a recommendation and draft options, and keeps
your decision history locally. It does not log into accounts, swipe, like, or
send messages.

## What you get

- A like/skip recommendation with concise reasoning.
- The strongest profile detail to respond to.
- A primary opener and alternative angles, grounded in `context.md` and your
  confirmed sent-message history.
- A direct command-line workflow for existing screenshots or Waydroid capture.
- An optional MCP interface for supported clients.

## Quick start

Requires Python 3.11+, plus an API key for your selected model backend.

```bash
git clone https://github.com/ArjunMal1311/dating-copilot.git
cd dating-copilot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
cp context.md.example context.md
```

Set `GEMINI_API_KEY` in `.env`, then make `context.md` sound like you—especially
the **Your voice** section. Your configuration, screenshots, identity context,
and local database are ignored by Git.

Judge an ordered set of screenshots:

```bash
.venv/bin/python judge.py shots/profile/01.png shots/profile/02.png
```

The command prints the decision, reasoning, target detail, draft, and backups.

## Waydroid capture

On KDE/Wayland, you can capture the visible Waydroid profile and judge it in
one command:

```bash
.venv/bin/python grab.py --app generic
```

Automatic capture focuses Waydroid, scrolls the active profile, saves distinct
screenfuls under `shots/`, and judges them. It uses only screenshots and scroll
gestures.

Use manual capture when you want to control focus and scrolling yourself:

```bash
.venv/bin/python grab.py --manual --app like_comment
```

Waydroid capture needs KDE/Wayland, `spectacle`, `waydroid`, and `adb`. It is
optional; `judge.py` works with any local screenshot files.

## Profile formats

Choose a format based on the interaction shape, not a product name:

| Format | Use it when |
| --- | --- |
| `generic` | The screenshot layout needs no special rules. |
| `like_comment` | A like can include a comment. |
| `match_then_message` | Messaging starts only after a match. |
| `she_opens` | The other person sends the first message after a match. |
| `essays` | Written profile sections are central to the decision. |

Pass one with `--app`, for example:

```bash
.venv/bin/python judge.py --app essays shots/profile/*.png
```

The corresponding guidance lives in [`apps/`](apps/).

## Model backends

`LLM_BACKEND=gemini` is the default. Set `GEMINI_API_KEY` in `.env`.

For Claude, install the extra and set the matching values:

```bash
.venv/bin/pip install -r requirements-claude.txt
# .env: LLM_BACKEND=claude and ANTHROPIC_API_KEY=...
```

`LLM_BACKEND=gateway` sends requests to an existing compatible gateway at
`LLM_GATEWAY_URL`; it does not need a local provider key.

## Agent skill

Project guidance lives in [`AGENTS.md`](AGENTS.md), with a small
[`CLAUDE.md`](CLAUDE.md) entry point for Claude Code. The repository includes
these user workflows under [`.claude/skills/`](.claude/skills/):

- `/context-setup` — create or update the user's private `context.md`.
- `/profile-review` — review the user's own profile and suggest truthful
  improvements.
- `/judge` — review another person's profile and draft an opener.
- `/reply` — analyze a conversation and draft a reply.

For `/judge`, provide screenshot paths with `/judge <path> ...`, or invoke it
when a Waydroid profile is already visible. The skill runs the local CLI
directly. `/profile-review` works from screenshots taken on any device or from
pasted profile text; it does not require Waydroid.

## Optional MCP interface

`dating_mcp.py` exposes the same judge workflow to an MCP client. Register it
with a configuration shaped like:

```yaml
mcp_servers:
  dating:
    command: /absolute/path/to/dating-copilot/.venv/bin/python
    args: ["-m", "dating_mcp"]
```

Available tools include `judge_profile`, outcome recording, sent-message
recording, identity notes, weekly history, and funnel reporting.

## Privacy and boundaries

- `context.md`, `*.db`, `.env`, and screenshot directories stay out of Git.
- Screenshots are sent only to the model backend configured for that judgment.
- The project never performs account actions or uses unofficial account APIs.
- Review every suggestion before sending it.

## Development

The shared [`judge_service.py`](judge_service.py) module is the core workflow.
The CLI and MCP modules are adapters over it, so image preparation, validation,
retries, and persistence changes belong in the service.

```bash
.venv/bin/pip install -r requirements-dev.txt
PYTHON=.venv/bin/python make check
```

This runs Ruff formatting, linting, and the service-level test suite. GitHub
Actions runs the same checks for every push and pull request.

See [CONTRIBUTING.md](CONTRIBUTING.md) to add a profile format. Licensed under
the [MIT License](LICENSE).
