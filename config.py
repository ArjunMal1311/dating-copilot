"""Configuration for the generic-bot Telegram assistant.

All values come from .env (see .env.example). Nothing here is guessed or
defaulted silently for the things that matter — a missing token or key
fails loudly at startup, not mid-conversation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent


def _fail(msg: str) -> None:
    print(f"config error: {msg}", file=sys.stderr)
    sys.exit(1)


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        _fail(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return val


# ---------- Telegram ----------
TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")

_raw_user_id = _require("TELEGRAM_ALLOWED_USER_ID")
try:
    TELEGRAM_ALLOWED_USER_ID = int(_raw_user_id)
except ValueError:
    _fail(f"TELEGRAM_ALLOWED_USER_ID={_raw_user_id!r} isn't a number. "
          f"Message @userinfobot on Telegram to get your numeric id.")

# ---------- Judge backend ----------
LLM_BACKEND = os.environ.get("LLM_BACKEND", "gemini").strip().lower()
if LLM_BACKEND not in ("gemini", "claude"):
    _fail(f"LLM_BACKEND={LLM_BACKEND!r} — must be 'gemini' or 'claude'.")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

if LLM_BACKEND == "gemini" and not GEMINI_API_KEY:
    _fail("LLM_BACKEND=gemini but GEMINI_API_KEY is empty. Get one at "
          "https://aistudio.google.com/apikey")
if LLM_BACKEND == "claude" and not ANTHROPIC_API_KEY:
    _fail("LLM_BACKEND=claude but ANTHROPIC_API_KEY is empty.")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5").strip()

# ---------- Identity / memory ----------
USER_NAME = os.environ.get("USER_NAME", "the user").strip()

_context_path = os.environ.get("CONTEXT_MD_PATH", "").strip()
CONTEXT_MD_PATH = Path(_context_path) if _context_path else BASE_DIR / "context.md"

# How many of your most recent confirmed sent messages to sample as
# few-shot voice examples on each judge call. Recency-based, no embeddings —
# fine at personal-bot volume; revisit only if this ever needs to scale.
VOICE_SAMPLE_COUNT = int(os.environ.get("VOICE_SAMPLE_COUNT", "12"))

# How many active /about notes to include (most recent first). Soft cap so
# a very long history doesn't silently balloon every request.
CONTEXT_NOTE_LIMIT = int(os.environ.get("CONTEXT_NOTE_LIMIT", "40"))

# ---------- Storage ----------
DB_PATH = BASE_DIR / "generic.db"

# ---------- Images ----------
MAX_EDGE = 1092       # long-edge downscale before sending to the judge
JPEG_QUALITY = 85

# ---------- Telegram album handling ----------
# Telegram delivers an album as N separate Updates sharing one
# media_group_id, not one Update with N photos. This is how long to wait
# after the last photo in a group before treating it as complete.
ALBUM_DEBOUNCE_SECONDS = 1.5


def check_context_file() -> None:
    """Warn (not fail) if context.md is missing — the bot still runs, but
    every judge call will be operating with no identity at all."""
    if not CONTEXT_MD_PATH.exists():
        print(
            f"warning: {CONTEXT_MD_PATH} not found. Copy context.md.example "
            f"to context.md (or set CONTEXT_MD_PATH) and fill it in — "
            f"until then the bot has no idea who you are.",
            file=sys.stderr,
        )
