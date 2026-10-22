# dating-copilot

Local, screenshot-in profile review. It returns a like/skip recommendation,
the best detail to answer, and opener drafts in your voice. You review and
send everything yourself; it never controls an account or types into an app.

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
cp context.md.example context.md
```

Set the API key for your chosen backend in `.env`, then fill in
`context.md`, especially **Your voice**. The tool keeps decisions, sent
messages, and identity notes locally in `dating.db`.

## Direct use

Judge existing screenshots in their top-to-bottom profile order:

```
.venv/bin/python judge.py shots/profile/01.png shots/profile/02.png
.venv/bin/python judge.py --app like_comment shots/profile/*.png
```

On KDE/Wayland with Waydroid open to a profile, capture and judge it in one
step:

```
.venv/bin/python grab.py --app generic
```

`grab.py --manual` gives you a countdown to focus the window and scroll it
yourself. Both modes only read screenshots and use scroll gestures; neither
likes, skips, or sends text.

Profile formats are `generic` (the default), `like_comment`,
`match_then_message`, `she_opens`, and `essays`. Use the format that describes
the interaction shape, not a product name.

## Agent skill

The repository includes a `/judge` skill at `.claude/skills/judge/SKILL.md`.
With screenshots, invoke `/judge <path> ...`; with Waydroid already open,
invoke `/judge` and ask for a capture. The skill calls the local commands
above directly, so it does not require a chat bot or an external bridge.

## Optional MCP interface

`dating_mcp.py` exposes the same local judge engine to an MCP client. Its
tools include `judge_profile`, `record_outcome`, `record_sent_message`, and
reporting and identity helpers. `mcp` is installed with the standard
requirements.

## Privacy

`context.md`, `*.db`, and screenshots are gitignored. Images are sent only to
the configured model backend for each judgment; the local files and history
stay on your machine.

## License

MIT. See [CONTRIBUTING.md](CONTRIBUTING.md) for profile-format guidance.
