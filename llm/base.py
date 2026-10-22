"""Shared shape both LLM backends produce.

Kept intentionally small — just the fields the local tools read.
Each backend (llm/gemini.py, llm/claude.py) is responsible for getting its
provider's response into exactly this shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Opener angles. One draft per angle, so a profile gets the main draft plus
# up to two backups that each try something different, and the funnel can
# later show which angle actually gets replies. Keep in sync with the
# "Opener shapes" list in memory.py.
LANES = {
    "question": "detail + easy question",
    "guess": "guess she can correct",
    "take_side": "take a side on her take",
    "small_thing": "the small thing nobody else mentions",
    "scenario": "shared scenario",
    "sincere": "sincere reaction",
    "dry_riff": "dry riff",
}

# Fields every backend must return. Newer fields (draft_lane, alternatives)
# are requested too but parsed leniently so an older/looser model reply
# still produces a usable Decision.
CORE_FIELDS = ("decision", "reasoning", "target_prompt", "draft_message")

MAX_ALTERNATIVES = 2


def profile_user_text(n: int, app: str = "generic") -> str:
    """User-turn text sent with the screenshots. `target_prompt` is the hook."""
    from apps import display_name

    label = display_name(app)
    return (
        f"Above are {n} screenshots of one {label} profile, in "
        f"order. Decide whether to like or skip, per the instructions."
    )


@dataclass
class Decision:
    decision: str          # "like" | "skip"
    reasoning: str
    target_prompt: str = ""    # which of her prompts to respond to; '' if skip
    draft_message: str = ""    # '' if skip, or if LIKE with no good hook found
    draft_lane: str = ""       # one of LANES, or '' when there is no draft
    # Backups: [{"lane", "target", "message"}, ...], at most MAX_ALTERNATIVES,
    # each a different lane from draft_lane and from each other.
    alternatives: list[dict[str, str]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.draft_lane = self.draft_lane if self.draft_lane in LANES else ""
        if not self.draft_message:
            self.draft_lane = ""
        self.alternatives = clean_alternatives(
            self.alternatives, self.draft_message, self.draft_lane
        )


def clean_alternatives(
    raw: Any, main_message: str = "", main_lane: str = ""
) -> list[dict[str, str]]:
    """Normalise whatever the model sent for `alternatives`: keep only
    well-formed entries with a known lane and a non-empty message, drop
    duplicates of the main draft or of each other (by text or lane), cap
    at MAX_ALTERNATIVES."""
    if not isinstance(raw, list):
        return []
    seen_text = {main_message.strip().lower()} if main_message else set()
    seen_lane = {main_lane} if main_lane else set()
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        msg = str(item.get("message") or "").strip()
        lane = str(item.get("lane") or "").strip()
        if not msg or lane not in LANES:
            continue
        if msg.lower() in seen_text or lane in seen_lane:
            continue
        seen_text.add(msg.lower())
        seen_lane.add(lane)
        out.append({
            "lane": lane,
            "target": str(item.get("target") or "").strip(),
            "message": msg,
        })
        if len(out) >= MAX_ALTERNATIVES:
            break
    return out


# JSON schema shared by both backends' structured-output config. Each
# backend adapts the shape to its own SDK's expectations (Gemini's
# response_json_schema, Claude's tool input_schema) but the fields and
# descriptions are the single source of truth here.
DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["like", "skip"],
            "description": "Whether to like or skip this profile.",
        },
        "reasoning": {
            "type": "string",
            "description": (
                "One or two sentences. Reference something specific and "
                "real from the profile — a prompt answer or a photo detail."
            ),
        },
        "target_prompt": {
            "type": "string",
            "description": (
                "Which of her prompts the draft message responds to — "
                "quote its label (e.g. 'Two truths and a lie'). Empty "
                "string if decision is 'skip', or if liking with no "
                "draft message."
            ),
        },
        "draft_message": {
            "type": "string",
            "description": (
                "Opener referencing target_prompt or a specific photo "
                "detail, written in the user's actual voice per the "
                "examples given. Empty string if decision is 'skip', or "
                "if no sufficiently specific hook exists on the profile."
            ),
        },
        "draft_lane": {
            "type": "string",
            "description": (
                "Which opener shape draft_message uses: one of "
                + ", ".join(LANES)
                + ". Empty string when draft_message is empty."
            ),
        },
        "alternatives": {
            "type": "array",
            "maxItems": MAX_ALTERNATIVES,
            "description": (
                "Up to two backup openers, each a DIFFERENT shape from "
                "draft_lane and from each other, each passing every rule "
                "draft_message must pass. Empty array if skip, if there is "
                "no main draft, or if no other clean draft exists."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "lane": {"type": "string", "enum": list(LANES)},
                    "target": {
                        "type": "string",
                        "description": (
                            "The prompt label or photo detail this backup "
                            "answers. May differ from target_prompt."
                        ),
                    },
                    "message": {"type": "string"},
                },
                "required": ["lane", "target", "message"],
            },
        },
    },
    "required": [*CORE_FIELDS, "draft_lane", "alternatives"],
}
