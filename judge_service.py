"""The local profile-judging workflow shared by every interface.

Call :func:`judge_profile` from a command-line interface, an MCP adapter, or
tests. The function owns image preparation, prompt construction, model retry,
draft validation, and persistence so callers only provide ordered image paths
and a profile format.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlparse

from PIL import Image

import apps as app_catalog
import config
import db
import memory
from llm import load_backend
from llm.base import Decision

_MAX_IMAGES = 12


class JudgeBackend(Protocol):
    """Model adapter used by the local judging workflow."""

    def judge(self, images: list[bytes], system_prompt: str, app: str) -> Decision: ...


def _resolve(path: str) -> Path:
    if path.startswith("file://"):
        path = unquote(urlparse(path).path)
    return Path(path).expanduser()


def _downscale(path: Path) -> bytes:
    """Convert one screenshot into the bounded JPEG used by every backend."""
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((config.MAX_EDGE, config.MAX_EDGE), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=config.JPEG_QUALITY)
        return buffer.getvalue()


def judge_profile(
    image_paths: list[str], app: str = "generic", *, backend: JudgeBackend | None = None
) -> dict:
    """Judge one ordered profile and persist the resulting recommendation.

    ``backend`` is an internal seam for tests; normal callers omit it and use
    the configured backend. Raises ``ValueError`` for invalid formats or image
    paths before any model request is made.
    """
    slug = app_catalog.normalize(app)
    if not image_paths:
        raise ValueError("image_paths is empty — pass the profile screenshots.")
    if len(image_paths) > _MAX_IMAGES:
        raise ValueError(
            f"got {len(image_paths)} images; max is {_MAX_IMAGES}. Send one profile at a time."
        )

    images: list[bytes] = []
    for raw_path in image_paths:
        path = _resolve(raw_path)
        if not path.is_file():
            raise ValueError(f"not a readable file: {path}")
        images.append(_downscale(path))

    judge_backend = backend or load_backend()
    system_prompt = memory.build_system_prompt(slug)
    decision = judge_backend.judge(images, system_prompt, app=slug)

    if decision.draft_message:
        issues = memory.check_draft(decision.draft_message)
        if issues:
            retry_prompt = (
                f"{system_prompt}\n\n"
                "# Your previous draft failed these checks\n\n"
                f"draft_message was: {decision.draft_message!r}\n"
                "Problems found:\n"
                + "\n".join(f"- {issue}" for issue in issues)
                + "\n\nRewrite draft_message to fix every problem above while "
                "keeping the same decision, reasoning and target_prompt. If "
                "no clean draft is possible, use an empty string instead."
            )
            retried = judge_backend.judge(images, retry_prompt, app=slug)
            if retried.draft_message or not decision.draft_message:
                decision = retried

    alternatives = memory.drop_failing_alternatives(decision.alternatives)
    if decision.draft_message and memory.reused_line(decision.draft_message):
        if alternatives:
            promoted = alternatives.pop(0)
            decision.draft_message = promoted["message"]
            decision.draft_lane = promoted["lane"]
            decision.target_prompt = promoted["target"] or decision.target_prompt
        else:
            decision.draft_message, decision.draft_lane = "", ""

    decision_id = db.insert_decision(
        decision=decision.decision,
        reasoning=decision.reasoning,
        target_prompt=decision.target_prompt,
        draft_message=decision.draft_message,
        draft_lane=decision.draft_lane,
        alternatives=alternatives,
        app=slug,
    )
    return {
        "decision_id": decision_id,
        "decision": decision.decision,
        "reasoning": decision.reasoning,
        "target_prompt": decision.target_prompt,
        "draft_message": decision.draft_message,
        "draft_lane": decision.draft_lane,
        "alternatives": alternatives,
        "app": slug,
    }
