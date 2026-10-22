"""ai-gateway backend — judge over HTTP instead of a local provider key.

Set LLM_BACKEND=gateway. dating-copilot then holds no Gemini/Anthropic key at all:
it POSTs the profile to a running ai-gateway
(github.com/<you>/gemini — "Standalone LLM gateway microservice: multi-key
pool, rate limiting, per-key cooldown/backoff"), which owns the key pool and
picks a model off its own config/models.yaml priority list.

Start the gateway first (from its own checkout):

    cd ~/Documents/GitHub/gemini
    docker compose up --build          # Redis + app on :8080
    # or, with a local Redis already running:
    uvicorn app.main:app --port 8080

then point dating-copilot at it (.env):

    LLM_BACKEND=gateway
    LLM_GATEWAY_URL=http://localhost:8080     # default; override if remote
    # LLM_GATEWAY_MODEL=gemini-3.5-flash      # optional; omit => gateway picks

Design note — the gateway's POST /v1/generate is a bare
`generate_content(model, contents)` with NO GenerateContentConfig, so unlike
llm/gemini.py this path has:
  * no response_json_schema  -> we instruct JSON in the prompt and parse it,
    tolerating markdown fences / stray prose;
  * no system_instruction    -> the system prompt rides as the first text part;
  * no safety_settings        -> the gateway uses Gemini's DEFAULT thresholds
    (llm/gemini.py loosens them to BLOCK_ONLY_HIGH). If dating photos start
    coming back blocked ("no text (finish_reason=SAFETY)"), that passthrough
    has to be added on the gateway side — it can't be set from here.
"""

from __future__ import annotations

import base64
import json
import re

import httpx

import config
from llm.base import CORE_FIELDS, LANES, Decision, profile_user_text

# Spelled out because the gateway can't enforce the schema for us (no
# response_json_schema on its generate call).
_JSON_INSTRUCTION = (
    "Return your answer as a single raw JSON object and nothing else — no "
    "prose before or after, no ```json fences. Exactly these keys:\n"
    '  "decision": "like" or "skip"\n'
    '  "reasoning": one or two sentences citing something real from the profile\n'
    '  "target_prompt": which of her prompts the draft answers (quote its '
    'label), or "" if skip / no draft\n'
    '  "draft_message": the opener in the user\'s voice, or "" if skip / no '
    "specific hook\n"
    '  "draft_lane": which opener shape draft_message uses, one of '
    + ", ".join(f'"{k}"' for k in LANES)
    + ', or "" if no draft\n'
    '  "alternatives": up to 2 backup openers as '
    '[{"lane": ..., "target": ..., "message": ...}], each a different lane '
    "from draft_lane and from each other, or [] if none\n"
    'All keys are required; use "" or [] for the empties, never null.'
)

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _endpoint() -> str:
    return f"{config.LLM_GATEWAY_URL}/v1/generate"


def judge(images: list[bytes], system_prompt: str, app: str = "generic") -> Decision:
    """images: JPEG bytes, top-to-bottom profile order. Returns a Decision."""
    parts: list = [f"{system_prompt}\n\n{_JSON_INSTRUCTION}"]
    parts.extend(
        {
            "mime_type": "image/jpeg",
            "data": base64.standard_b64encode(img).decode("ascii"),
        }
        for img in images
    )
    parts.append(profile_user_text(len(images), app) + " Respond with ONLY the JSON object.")

    payload: dict = {"parts": parts}
    if config.LLM_GATEWAY_MODEL:
        payload["model"] = config.LLM_GATEWAY_MODEL

    try:
        resp = httpx.post(_endpoint(), json=payload, timeout=config.LLM_GATEWAY_TIMEOUT)
    except httpx.ConnectError as e:
        raise RuntimeError(
            f"ai-gateway unreachable at {config.LLM_GATEWAY_URL} — start it "
            f"(see llm/gateway.py) or fix LLM_GATEWAY_URL. ({e})"
        ) from e
    except httpx.TimeoutException as e:
        raise RuntimeError(
            f"ai-gateway did not respond within "
            f"{config.LLM_GATEWAY_TIMEOUT:.0f}s at {config.LLM_GATEWAY_URL}."
        ) from e

    if resp.status_code != 200:
        raise RuntimeError(_error_message(resp))

    try:
        body = resp.json()
    except ValueError as e:
        raise RuntimeError(f"ai-gateway returned non-JSON on 200: {resp.text[:300]!r}") from e

    text = (body.get("text") or "").strip()
    if not text:
        raise RuntimeError(f"ai-gateway returned an empty 'text' field. Full body: {body!r}")

    data = _parse_decision_json(text)

    missing = [k for k in CORE_FIELDS if k not in data]
    if missing:
        raise RuntimeError(f"ai-gateway JSON missing required fields {missing}: {data!r}")

    return Decision(
        decision=data["decision"],
        reasoning=data["reasoning"],
        target_prompt=data.get("target_prompt") or "",
        draft_message=data.get("draft_message") or "",
        draft_lane=data.get("draft_lane") or "",
        alternatives=data.get("alternatives") or [],
        usage={
            "input_tokens": body.get("input_tokens") or 0,
            "output_tokens": body.get("output_tokens") or 0,
            # which model in the gateway's pool actually answered — handy when a
            # judgement looks off and you want to know if it fell back.
            "gateway_model": body.get("model"),
        },
    )


def _parse_decision_json(text: str) -> dict:
    """The gateway can't force JSON, so be forgiving: strip fences, and if
    that still isn't valid JSON, salvage the outermost {...} span."""
    stripped = _FENCE_RE.sub("", text).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start, end = stripped.find("{"), stripped.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise RuntimeError(
        f"ai-gateway response wasn't JSON (no schema enforcement on this path): {text[:300]!r}"
    )


def _error_message(resp: httpx.Response) -> str:
    """Turn the gateway's typed error body into one actionable line.

    Shape (app/models/responses.py GenerateErrorResponse):
      {request_id, error, detail, retry_after_seconds?, key_statuses?}
    """
    try:
        err = resp.json()
    except ValueError:
        return f"ai-gateway HTTP {resp.status_code}: {resp.text[:300]!r}"

    detail = err.get("detail") or err.get("error") or ""
    code = resp.status_code

    if code == 429:
        wait = err.get("retry_after_seconds")
        tail = f" retry in ~{wait:.0f}s." if isinstance(wait, (int, float)) else ""
        return f"ai-gateway 429: every key/model is in backoff.{tail} {detail}".strip()
    if code == 503:
        return f"ai-gateway 503: all configured keys are dead. {detail}".strip()
    if code == 422:
        return (
            f"ai-gateway 422: request rejected ({err.get('error')}). {detail} "
            f"— check LLM_GATEWAY_MODEL."
        ).strip()
    if code == 500 and re.search(r"no text|finish_reason|SAFETY|RECITATION", detail):
        return (
            f"ai-gateway 500: the model returned no text — likely a safety "
            f"block (this path can't loosen safety_settings; see "
            f"llm/gateway.py). {detail}"
        )
    return f"ai-gateway HTTP {code}: {detail or resp.text[:300]!r}"
