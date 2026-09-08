"""Backend-agnostic judge loader.

llm/gemini.py (default), llm/claude.py (swap-in) and llm/gateway.py (HTTP to a
running ai-gateway) each expose judge(images, system_prompt) -> Decision. This
module resolves config.LLM_BACKEND to the right one, same pattern as
generic-auto's judge_common.load_backend().
"""

from __future__ import annotations

import config


def load_backend():
    if config.LLM_BACKEND == "gemini":
        import llm.gemini as backend
        return backend
    if config.LLM_BACKEND == "claude":
        import llm.claude as backend
        return backend
    if config.LLM_BACKEND == "gateway":
        import llm.gateway as backend
        return backend
    raise ValueError(f"Unknown LLM_BACKEND={config.LLM_BACKEND!r}")
