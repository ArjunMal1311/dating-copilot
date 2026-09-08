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

BASE_DIR = Path(__file__).parent

# Load this project's .env explicitly, not whatever happens to be in the
# process's cwd — generic_mcp.py is spawned by an MCP client from its own
# directory, not this one.
load_dotenv(BASE_DIR / ".env")


def _fail(msg: str) -> None:
    print(f"config error: {msg}", file=sys.stderr)
    sys.exit(1)


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        _fail(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return val


# ---------- Telegram ----------
# Not required at import: generic_mcp.py (MCP-client integration) reuses this
# module for the Gemini key, DB path and identity config but never touches
# Telegram. bot.py calls require_telegram() at startup to fail loudly.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

_raw_user_id = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()
try:
    TELEGRAM_ALLOWED_USER_ID = int(_raw_user_id) if _raw_user_id else None
except ValueError:
    _fail(f"TELEGRAM_ALLOWED_USER_ID={_raw_user_id!r} isn't a number. "
          f"Message @userinfobot on Telegram to get your numeric id.")


def require_telegram() -> None:
    """Fail loudly if the Telegram vars needed by bot.py are missing.

    Called from bot.main(), not at import — so generic_mcp.py can import this
    module without a bot token.
    """
    if not TELEGRAM_BOT_TOKEN:
        _fail("TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and "
              "fill it in.")
    if TELEGRAM_ALLOWED_USER_ID is None:
        _fail("TELEGRAM_ALLOWED_USER_ID is not set. Message @userinfobot on "
              "Telegram to get your numeric id.")

# ---------- Judge backend ----------
# gemini  — call the Gemini SDK directly with a single local GEMINI_API_KEY.
# claude  — call the Anthropic SDK directly with ANTHROPIC_API_KEY.
# gateway — POST to a running ai-gateway over HTTP; the gateway owns the key
#           pool, rate limiting and backoff, so generic-bot holds no provider key
#           at all. See llm/gateway.py.
LLM_BACKEND = os.environ.get("LLM_BACKEND", "gemini").strip().lower()
if LLM_BACKEND not in ("gemini", "claude", "gateway"):
    _fail(f"LLM_BACKEND={LLM_BACKEND!r} — must be 'gemini', 'claude' or 'gateway'.")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

if LLM_BACKEND == "gemini" and not GEMINI_API_KEY:
    _fail("LLM_BACKEND=gemini but GEMINI_API_KEY is empty. Get one at "
          "https://aistudio.google.com/apikey")
if LLM_BACKEND == "claude" and not ANTHROPIC_API_KEY:
    _fail("LLM_BACKEND=claude but ANTHROPIC_API_KEY is empty.")
# gateway needs no local key — the gateway service holds the pool.

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5").strip()

# ---------- ai-gateway backend (LLM_BACKEND=gateway) ----------
# Base URL of the running gateway. Trailing slash trimmed so f"{URL}/v1/generate"
# is always well-formed.
LLM_GATEWAY_URL = os.environ.get(
    "LLM_GATEWAY_URL", "http://localhost:8080"
).strip().rstrip("/")
# Empty => let the gateway walk its own config/models.yaml priority list (kept
# current there). Set it to pin one model (gateway then does no cross-model
# fallback for this call).
LLM_GATEWAY_MODEL = os.environ.get("LLM_GATEWAY_MODEL", "").strip()
# Client-side read timeout for the judge call, seconds. The gateway's own
# per-request deadline is ~120s; give it headroom above that.
LLM_GATEWAY_TIMEOUT = float(os.environ.get("LLM_GATEWAY_TIMEOUT", "150"))

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
