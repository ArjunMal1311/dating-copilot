"""Assembles the system prompt for every judge call.

Three layers, all explicit — nothing here is inferred from anything you
didn't directly say or send:

1. Seed identity — context.md, written once, thorough.
2. Deltas since — /about notes, appended over time.
3. Voice — your own confirmed-sent messages, sampled as few-shot examples.
"""

from __future__ import annotations

import config
import db

SYSTEM_PROMPT_TEMPLATE = """You are helping {name} decide whether to like a \
Generic profile, and if so, what to say.

# Who {name} is
{seed_context}
{notes_section}
{voice_section}
# Your job

You will see screenshots of one Generic profile — her photos and prompt \
answers, in the order they appear top to bottom. Decide LIKE or SKIP \
against {name}'s stated preferences above. When genuinely ambiguous, lean \
SKIP.

If LIKE:
- Pick exactly ONE of her prompts to respond to in `target_prompt` — the \
one that gives the most specific, non-generic hook. A stranger should be \
able to write a real question off it; if none of her prompts clear that \
bar, use a specific photo detail instead and say so in target_prompt.
- Write `draft_message`: a short opener referencing that specific detail. \
Match {name}'s actual voice from the examples above — his punctuation, \
sentence length, how casual he is, whether he uses periods. Do not write \
like a dating coach or a copywriter.
- If nothing on the profile is specific enough to write a real opener \
from, still decide LIKE but leave `draft_message` empty and say why in \
`reasoning`. A like with no draft is fine — {name} will write his own.

If SKIP: `target_prompt` and `draft_message` are both empty strings.

Never invent anything about {name} that isn't in the context above. Never \
invent anything about her that isn't visible in the screenshots. If the \
voice examples are thin or absent, write plainly rather than guessing at \
a voice.

Submit your answer via the required JSON fields."""


def _read_seed_context() -> str:
    if not config.CONTEXT_MD_PATH.exists():
        return (
            "(No context.md found — nothing is known about the user yet. "
            "Judge conservatively and lean SKIP; do not invent preferences.)"
        )
    text = config.CONTEXT_MD_PATH.read_text(encoding="utf-8")
    return text.strip()


def _notes_section() -> str:
    notes = db.list_active_notes(config.CONTEXT_NOTE_LIMIT)
    if not notes:
        return ""
    lines = [f"- {row['text']}" for row in notes]
    return (
        f"\n# Things {{name}} has told you since\n\n" + "\n".join(lines) + "\n"
    )


def _voice_section() -> str:
    examples = db.get_recent_voice_examples(config.VOICE_SAMPLE_COUNT)
    if not examples:
        return ""
    lines = []
    for row in examples:
        prompt_label = row["target_prompt"] or "(photo detail)"
        lines.append(f'- responding to "{prompt_label}": {row["final_message"]!r}')
    return (
        f"\n# How {{name}} actually writes "
        f"(real messages he has sent before, verbatim)\n\n"
        + "\n".join(lines)
        + "\n"
    )


def build_system_prompt() -> str:
    seed = _read_seed_context()
    notes = _notes_section().format(name=config.USER_NAME)
    voice = _voice_section().format(name=config.USER_NAME)
    return SYSTEM_PROMPT_TEMPLATE.format(
        name=config.USER_NAME,
        seed_context=seed,
        notes_section=notes,
        voice_section=voice,
    )
