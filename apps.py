"""Dating-app catalog: short judge briefs, not account clients.

Each apps/<slug>.md tells the model how likes and first messages work on
that app, what a profile contains, and what `target_prompt` (the hook) means.
The copilot never logs in, swipes, or sends — it only reads screenshots.
"""

from __future__ import annotations

import config

KNOWN_APPS = ("generic", "generic", "generic", "generic", "generic")
DEFAULT_APP = "generic"

DISPLAY_NAMES = {
    "generic": "Generic",
    "generic": "Generic",
    "generic": "Generic",
    "generic": "Generic",
    "generic": "dating-app",
}

# Android package names for optional Waydroid capture (grab.py auto mode).
# The copilot does not use these to automate likes or messages.
PACKAGES = {
    "generic": "co.generic.app",
    "generic": "com.generic",
    "generic": "com.generic.app",
    "generic": "com.generic.generic",
}


def normalize(app: str | None) -> str:
    slug = (app or config.DEFAULT_APP or DEFAULT_APP).strip().lower()
    if slug not in KNOWN_APPS:
        known = ", ".join(KNOWN_APPS)
        raise ValueError(f"unknown app {app!r} — use one of: {known}")
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
