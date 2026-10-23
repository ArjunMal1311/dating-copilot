---
name: context-setup
description: Help a first-time user create or improve their private personal context file so profile reviews and drafts reflect their real life and voice.
disable-model-invocation: true
---

# Set up personal context

Guide the user through creating `context.md`, the private file that gives
profile reviews and message drafts accurate information about them.

## Steps

1. Check whether `context.md` exists. If it does, ask whether the user wants
   to review it or start a new file. Never replace existing context without
   showing the proposed change and getting approval.
2. Explain that the file is local and gitignored. Offer to use another path
   through `CONTEXT_MD_PATH` if they prefer.
3. Ask short questions in manageable groups. Cover only the sections the user
   wants to provide:
   - Basics they want the assistant to know, such as age range or general area.
   - What kind of relationship and person they are looking for.
   - Specific, current interests and activities from their real life.
   - Their writing voice, ideally with a few messages they wrote themselves.
   - Topics, claims, or styles they want avoided.
4. Treat every detail as optional. Do not infer or fill gaps with stereotypes,
   demographic assumptions, imagined hobbies, or generic dating advice.
5. Draft concise Markdown using the headings in `context.md.example`. Show
   the complete draft and let the user correct it before writing.
6. After approval, write the file to `context.md` or the user's chosen path.
   Confirm the destination without repeating private details in the response.

## Ongoing updates

When the user wants to change one fact, update only that section and preserve
the rest. Prefer edits to `context.md`; do not create a second personal
profile store. `dating.db` holds judged decisions and confirmed messages, not
the canonical identity or voice profile.

## Attribution

This workflow is an original adaptation informed by the voice-profile skill
in Josh Pocock's MIT-licensed dating skill collection. See
`../dating-reply-reader/LICENSE` for the included license text.
