# Project guidance

## Purpose

This is a local-first profile review and message-drafting tool. It reads
user-supplied screenshots, produces recommendations, and stores personal
history on the user's machine. It does not automate account actions.

## Architecture

- `judge_service.py` owns the profile-judging workflow: image preparation,
  prompt building, model calls, draft checks, and persistence.
- `judge.py` and `grab.py` are local command-line interfaces.
- `dating_mcp.py` is an optional MCP adapter. Keep interface-specific code
  there; share judging behavior through `judge_service.py`.
- `llm/` contains model adapters. Keep their output normalized as
  `llm.base.Decision`.
- `memory.py` builds prompts from the user's private context and saved examples.
- `db.py` owns SQLite persistence and schema upgrades.
- `apps.py` and `apps/` define profile formats, not account integrations.
- `.claude/skills/` contains user workflows. Keep coding guidance here in
  `AGENTS.md`, not duplicated across every skill.

## User data and privacy

- `context.md`, `.env`, databases, screenshots, and generated captures are
  private local data. Do not read them unless the task requires it, and never
  add them to version control.
- Use `context.md.example` for the shape of the user's identity and voice
  context. Do not treat its sample details as facts about a real user.
- Screenshots may contain sensitive information. Use synthetic fixtures in
  tests and avoid printing image or database contents in logs.
- Keep recommendations review-only. Do not add code that likes, skips,
  messages, or otherwise acts on an account.

## Development

Install runtime dependencies with `python -m pip install -r requirements.txt`.
Install contributor tools with `python -m pip install -r requirements-dev.txt`.
Run the full local check with `PYTHON=.venv/bin/python make check`.

Add behavior tests through the `judge_service.judge_profile` interface. Use
an injected fake model adapter and an isolated temporary database; tests must
not require real credentials or contact a model provider.

When changing a profile format, update its brief under `apps/`, the catalog in
`apps.py`, and the relevant tests or docs. When changing setup or CLI behavior,
update the README and `--help` text together.
