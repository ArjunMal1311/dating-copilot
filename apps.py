"""Profile-format catalog: short judge briefs, not account clients.

Each apps/<slug>.md tells the model how likes and first messages work for
that *format* (comment-on-like vs match-then-message, etc.). No product
names. The copilot never logs in, swipes, or sends — it only reads
screenshots.
"""

from __future__ import annotations

import config

KNOWN_APPS = (
    "generic",
    "like_comment",
    "match_then_message",
    "she_opens",
    "essays",
)
DEFAULT_APP = "generic"

DISPLAY_NAMES = {
    "generic": "dating-app",
    "like_comment": "like-comment",
    "match_then_message": "match-then-message",
    "she_opens": "she-opens",
    "essays": "essay",
}


def normalize(app: str | None) -> str:
    slug = (app or config.DEFAULT_APP or DEFAULT_APP).strip().lower().replace("-", "_")
    if slug not in KNOWN_APPS:
        known = ", ".join(KNOWN_APPS)
        raise ValueError(f"unknown format {app!r} — use one of: {known}")
    return slug


def display_name(app: str | None) -> str:
    slug = normalize(app)
    return DISPLAY_NAMES.get(slug, slug)


def load_profile(app: str | None) -> str:
    slug = normalize(app)
    path = config.BASE_DIR / "apps" / f"{slug}.md"
    if not path.is_file():
        path = config.BASE_DIR / "apps" / "generic.md"
    return path.read_text(encoding="utf-8").strip()
