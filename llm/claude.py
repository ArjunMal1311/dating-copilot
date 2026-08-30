"""Claude backend — swap-in alternative to Gemini.

Same request shape as generic-auto's judge.py: vision + forced tool call,
cached system prompt. Requires `pip install -r requirements-claude.txt`
and ANTHROPIC_API_KEY, LLM_BACKEND=claude in .env.
"""

from __future__ import annotations

import base64

import anthropic

import config
from llm.base import DECISION_SCHEMA, Decision

DECIDE_TOOL = {
    "name": "submit_decision",
    "description": "Submit a like/skip decision for this Generic profile.",
    "input_schema": DECISION_SCHEMA,
}


def _image_block(png_bytes: bytes) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(png_bytes).decode("utf-8"),
        },
    }


def judge(images: list[bytes], system_prompt: str) -> Decision:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    content = [_image_block(img) for img in images]
    content.append({
        "type": "text",
        "text": (
            f"Above are {len(images)} screenshots of one Generic profile, in "
            f"order. Decide whether to like or skip, per the instructions."
        ),
    })

    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        tools=[DECIDE_TOOL],
        tool_choice={"type": "tool", "name": "submit_decision"},
        messages=[{"role": "user", "content": content}],
    )

    usage = {
        "input_tokens": getattr(response.usage, "input_tokens", 0),
        "output_tokens": getattr(response.usage, "output_tokens", 0),
        "cache_read_input_tokens":
            getattr(response.usage, "cache_read_input_tokens", 0) or 0,
    }

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_decision":
            return Decision(**block.input, usage=usage)

    raise RuntimeError(
        f"Claude did not return a tool_use block. stop_reason={response.stop_reason}"
    )
