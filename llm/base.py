"""Shared shape both LLM backends produce.

Kept intentionally small — just the fields the rest of the bot reads.
Each backend (llm/gemini.py, llm/claude.py) is responsible for getting its
provider's response into exactly this shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Decision:
    decision: str          # "like" | "skip"
    reasoning: str
    target_prompt: str = ""    # which of her prompts to respond to; '' if skip
    draft_message: str = ""    # '' if skip, or if LIKE with no good hook found
    usage: dict[str, Any] = field(default_factory=dict)


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
    },
    "required": ["decision", "reasoning", "target_prompt", "draft_message"],
}
