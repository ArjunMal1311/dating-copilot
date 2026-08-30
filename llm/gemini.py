"""Gemini backend — default judge.

Verified against the python-genai SDK's own README before writing this
(client.models.generate_content, types.Part.from_bytes, GenerateContentConfig
with response_mime_type + response_json_schema + system_instruction +
safety_settings) rather than guessed from memory.
"""

from __future__ import annotations

import json

from google import genai
from google.genai import types

import config
from llm.base import DECISION_SCHEMA, Decision

# Dating-profile photos (swimwear, low light, close-ups) commonly trip
# Gemini's default safety thresholds even when nothing is actually explicit.
# Loosened here, not disabled — BLOCK_ONLY_HIGH still blocks genuinely
# severe content. If a profile still comes back blocked, the categories/
# thresholds below are the first thing to widen.
_SAFETY_SETTINGS = [
    types.SafetySetting(category=cat, threshold="BLOCK_ONLY_HIGH")
    for cat in (
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    )
]


def _client() -> genai.Client:
    return genai.Client(api_key=config.GEMINI_API_KEY)


def judge(images: list[bytes], system_prompt: str) -> Decision:
    """images: JPEG bytes, top-to-bottom profile order. Returns a Decision."""
    client = _client()

    contents = [
        types.Part.from_bytes(data=img, mime_type="image/jpeg") for img in images
    ]
    contents.append(
        f"Above are {len(images)} screenshots of one Generic profile, in "
        f"order. Decide whether to like or skip, per the instructions."
    )

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_json_schema=DECISION_SCHEMA,
            safety_settings=_SAFETY_SETTINGS,
        ),
    )

    text = getattr(response, "text", None)
    if not text:
        # Most likely cause: safety filter blocked the response outright.
        # Surface that plainly instead of returning a hollow Decision the
        # caller would otherwise treat as a real (empty) skip.
        reason = _block_reason(response)
        raise RuntimeError(
            f"Gemini returned no text (likely blocked). {reason}"
        )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Gemini response wasn't valid JSON despite response_mime_type="
            f"'application/json': {text[:300]!r}"
        ) from e

    missing = [k for k in DECISION_SCHEMA["required"] if k not in data]
    if missing:
        raise RuntimeError(f"Gemini JSON missing required fields {missing}: {data!r}")

    usage_meta = getattr(response, "usage_metadata", None)
    usage = {
        "input_tokens": getattr(usage_meta, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(usage_meta, "candidates_token_count", 0) or 0,
    }

    return Decision(
        decision=data["decision"],
        reasoning=data["reasoning"],
        target_prompt=data.get("target_prompt", ""),
        draft_message=data.get("draft_message", ""),
        usage=usage,
    )


def _block_reason(response) -> str:
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None:
        block_reason = getattr(feedback, "block_reason", None)
        if block_reason:
            return f"prompt_feedback.block_reason={block_reason}"
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        finish = getattr(candidates[0], "finish_reason", None)
        if finish:
            return f"candidates[0].finish_reason={finish}"
    return "no further detail on response object."
