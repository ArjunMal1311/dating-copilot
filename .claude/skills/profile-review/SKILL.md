---
name: profile-review
description: Review the user's own dating profile from screenshots or pasted text. Give specific photo and writing feedback, then draft truthful profile improvements in the user's voice.
---

# Review my profile

Help the user improve their own profile. This is different from `/judge`,
which reviews another person's profile to help decide whether and how to
respond.

## Inputs

Accept screenshots, pasted bio and prompt text, or both. The user can use any
device to capture screenshots; Waydroid is not required. Ask for the order of
photos if it is unclear. If images are not available, work from the user's
descriptions and label visual conclusions as unknown.

Before drafting, read `context.md` if it exists. Use it to match the user's
voice and check that profile claims reflect their actual life. If no context
exists, ask a few questions or invite them to use `/context-setup` first.

## Review

1. State the profile's strongest authentic signal and the main improvement
   opportunity.
2. Review photos by function and order: clear first impression, variety,
   visible face, activity or interest, and social context. Discuss image
   quality and what each photo communicates; do not rate the user's physical
   attractiveness.
3. Review bio and prompts for specificity, ease of replying, consistency, and
   truthful details. Separate observed issues from suggestions.
4. Give up to three prioritized changes. Make rewrites sound like the user's
   voice and preserve their meaning.
5. Check every proposed claim against the supplied profile or `context.md`.
   Ask before adding a detail that is not supported. Never invent a job,
   location, hobby, achievement, preference, or story.

## Output

Keep the review direct and kind. Include:

- What is already working.
- The highest-impact changes, in order.
- Any photo order or replacement suggestions, with uncertainty stated.
- Revised bio or prompt options only where useful.
- A short truth check showing any detail that needs the user's confirmation.

The user makes all edits and publishes the profile themselves. Do not claim
to have changed anything in an account.

## Attribution

This workflow is an original adaptation informed by the profile-glowup,
photo-ranker, and bio-rewriter skills in Josh Pocock's MIT-licensed dating
skill collection. See `../dating-reply-reader/LICENSE` for the included
license text.
