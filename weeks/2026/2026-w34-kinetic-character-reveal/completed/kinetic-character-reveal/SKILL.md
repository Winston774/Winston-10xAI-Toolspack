---
name: kinetic-character-reveal
description: Extract, preserve, generate, and audit fast motion-graphics character-reveal video prompts—especially 13-cut, 15-second, 16:9 trailers combining kinetic typography, hard-edged graphic systems, and tightly locked character action. Use for style-DNA analysis, reusable binding constraints, same-series prompt variations, shot-by-shot timelines, or continuity audits. Do not use for dialogue-led narrative films, ordinary montages, static image prompts, or videos where motion graphics are secondary.
---

# Kinetic Character Reveal

Turn one strong motion-graphics character trailer prompt into a reusable visual system rather than merely paraphrasing it.

The default output language is:
- Traditional Chinese for analysis, assumptions, and constraint maps.
- English for the final generation prompt.
- Match another language when the user requests it.

## Supported modes

Choose the mode from the user's intent. Do not require a clarification when the request is sufficiently specified.

1. **EXTRACT** — Analyze a reference prompt and return its style DNA, binding hierarchy, controlled variables, cut functions, and drift risks.
2. **FAITHFUL** — Preserve the source character, palette, format, cut count, timeline, graphic vocabulary, and cut-role architecture. Change only the requested content.
3. **SERIES** — Create a new character or campaign in the same visual family. Preserve the source's structural signature while replacing the character bible, brand token, palette, action vocabulary, and selected motifs.
4. **REMIX** — Preserve the motion-graphics grammar and dramatic arc while allowing wider changes to duration, cut count, palette, or motif system.
5. **AUDIT** — Check an existing prompt for timing errors, character drift, style dilution, repeated shots, weak transitions, text overload, or violations of the selected binding profile.

Default decisions:
- Reference prompt + request to reuse its style: run **EXTRACT**, then **SERIES**.
- New concept with no reference: run **SERIES** using the default 13-cut architecture.
- Request to stay extremely close: run **FAITHFUL**.
- Request to check or fix a prompt: run **AUDIT**.

## Read supporting references selectively

- Read [source analysis](references/source-analysis.md) when explaining the supplied AO reference prompt.
- Read [style DNA](references/style-dna.md) when extracting or transferring the visual signature.
- Read [constraint matrix](references/constraint-matrix.md) when selecting hard locks and variation budget.
- Read [13-cut blueprint](references/cut-blueprint.md) when generating or repairing a 13-cut timeline.
- Use `assets/input-brief.yaml` to normalize sparse user input.
- Use `assets/output-template.md` when writing the final deliverable.
- Apply `assets/negative-constraints.txt` to all strict and series outputs.

## Binding hierarchy

Resolve conflicts from highest to lowest priority:

1. **Explicit user instructions**
2. **Delivery lock** — aspect ratio, fps, total duration, exact cut count, output language
3. **Identity lock** — face, body proportions, hairstyle, outfit construction, materials, accessories, colors, logos, and footwear
4. **Visual-system lock** — palette roles, typography scale, shapes, UI marks, texture vocabulary, graphic-to-character ratio
5. **Motion-grammar lock** — beat-synced snaps, slams, wipes, punches, shatters, freeze/release, stroboscopic echoes, graphic-object interaction
6. **Cut-role lock** — each cut's narrative and design function
7. **Continuity lock** — screen direction, pose carryover, recurring motifs, object persistence, transition handoffs
8. **Decorative choice** — exact adjectives, local camera flourish, secondary particle type

Never solve a lower-priority preference by violating a higher-priority lock.

## Reference signature that must remain recognizable

In **FAITHFUL** and **SERIES** modes, preserve all of the following unless the user explicitly changes one:

- 16:9, 24fps, exactly 13 distinct cuts, exactly 15.00 seconds.
- Roughly 80% motion graphic design and 20% character action.
- A premium title-sequence × streetwear-campaign tone.
- High-contrast flat fields, oversized typography, hard-edged shapes, split screens, UI ticks, barcode strips, halftone, speed lines, shutter flashes, and a recurring emblem or shape.
- Fast, percussive, beat-synced motion; no languid transitions.
- One dominant character action and one dominant graphic event per cut.
- Character and graphics physically affect one another: type compresses, rings become portals, panes shatter, letters shed fragments, targets stamp around frozen poses.
- A dramatic arc from graphic ignition → partial identity reveal → full kinetic entrance → escalating action/type interaction → freeze/release → poster montage → hero landing → identity card.
- Repetition with progression: recurring shapes, brand letters, palette, and UI marks return in more developed forms.

## Character lock

For any recurring character, write one complete immutable visual bible before the cuts. Include:

- Name and archetype
- Face shape and facial proportions
- Eye shape and color
- Skin tone
- Hair length, silhouette, texture, color, and bangs/fringe
- Body proportions and apparent age range
- Every garment, garment silhouette, construction detail, material, closure, drawstring, pocket, label, logo, accessory, and shoe
- Exact palette placement by item

Then include this lock sentence, adapted to the subject:

> Preserve the character's exact face, facial proportions, body proportions, skin tone, hairstyle, hair length, hair color, eye shape and color, clothing silhouette, garment construction, materials, accessories, footwear, logos, labels, and color placement in every shot. Never redesign, simplify, recolor, age-shift, gender-shift, substitute, remove, or add any item. No costume changes and no alternate hairstyle.

When the user supplies a character reference image, treat visible identity and costume details as higher priority than textual defaults.

## Variation profiles

### FAITHFUL

Lock:
- 13 cuts / 15.00s / 24fps / 16:9
- Exact character bible
- Exact palette
- 80/20 ratio
- Original 13 cut roles
- Original design and motion grammar

Allow:
- Replacement of individual action verbs, typography words, and local camera moves only when the new choice serves the same cut function.

### SERIES

Lock:
- 13 cuts / 15.00s / 24fps / 16:9
- 80/20 ratio
- 13 cut-role architecture
- Beat-synced hard motion grammar
- Character-to-graphics physical interaction
- Recurrent motif progression
- Campaign/title-sequence finish

Allow:
- A completely new character bible, then lock it across the sequence
- A new five-color role-based palette
- New brand token, slogans, emblem, action family, and recurring geometry
- New surface textures that remain graphic, editorial, and high contrast

### REMIX

Lock at least these seven invariants:
- Graphic design remains the main performer
- One strong character identity remains consistent
- Typography and shapes interact with the character
- Motion is beat-driven and percussive
- Cuts have distinct functions rather than random spectacle
- Recurring motifs develop across the film
- The ending resolves into an iconic identity card

Allow:
- 9–15 cuts
- 10–20 seconds
- Alternative aspect ratios
- Different graphic-to-character ratios no lower than 60/40
- Broader palettes and motif systems

## Prompt-construction workflow

1. **Normalize the brief.** Fill missing values with the defaults in `assets/input-brief.yaml`. State only material assumptions.
2. **Extract or create the character bible.** Lock identity before writing any shot.
3. **Define the visual system.** Assign palette roles rather than listing colors only:
   - base field
   - dominant accent
   - secondary accent
   - neutral
   - contrast/ink
4. **Define the type system.** Choose:
   - brand token: 1–4 letters or one short word
   - trait words: four short uppercase words
   - hero slogan: 2–5 words
   - final identity token
5. **Define the motif inventory.** Use 5–8 recurring motifs. At least one motif must transform across multiple cuts.
6. **Define the action inventory.** Use 6–9 actions from one coherent physical family: parkour, skating, dance, martial arts, sprinting, aerial gymnastics, cycling, or another user-specified family.
7. **Build the timeline from cut functions.** Use `references/cut-blueprint.md`. Preserve exact timing in FAITHFUL and SERIES modes unless explicitly changed.
8. **Write each cut with one visual thesis.** Use this sentence order:
   - field/composition
   - character action
   - graphic transformation or typography behavior
   - camera/time treatment
   - exit transition or handoff
9. **Create cross-cut handoffs.** Whenever possible, the final element of cut N becomes the first element of cut N+1: circle → portal, shards → speed debris, stripe → flip axis, frozen target → release burst, sneaker wipe → poster card.
10. **Apply negative constraints.** Remove redesign, palette drift, generic cinematic filler, soft transitions, redundant cuts, and extra text.
11. **Validate.** Check cut count, timestamps, total duration, continuity, identity, palette, ratio, typography load, and distinctness. When a prompt is saved to a file, run `scripts/validate_prompt.py`.

## Cut-writing rules

Every cut must:
- Start with `CUT NN | start-end s`.
- Use sequential zero-padded numbering.
- Contain a distinct composition and a distinct transition behavior.
- Include no more than one primary action phrase and one secondary action beat.
- Include no more than one major camera move.
- Keep on-screen copy short, uppercase, and exact.
- Avoid contradictory speed instructions. Slow motion is reserved for hero poses, airborne rotations, or the climax; the entrance and exits stay sharp.
- Name the dominant palette field or contrast relation when it matters.
- End with a clear visual handoff, hard cut, wipe, whip, flash, overexposure, or freeze/release cue.

## Typography constraints

- Use exact uppercase tokens only; do not invent extra copy.
- Prefer one word, a paired phrase, or short brand letters.
- Keep most cuts at 0–4 visible words.
- Reserve the longest phrase for one hero interaction cut.
- Typography must have a physical behavior: slam, punch, scroll, rotate, compress, rebound, fragment, mask, stamp, extrude as flat panes, or become a portal.
- Do not treat type as passive subtitles.

## Style-drift prohibitions

Do not introduce any of the following unless explicitly requested:

- Warm colors outside the locked palette
- Soft pastel gradients, watercolor, painterly texture, or dreamy bokeh
- Generic sci-fi holograms replacing the defined UI language
- Photorealistic locations that compete with the flat graphic stage
- Random explosions, magic powers, weapons, vehicles, or props
- Costume swaps, missing accessories, altered logos, changed hair, or changing body proportions
- More character acting than graphic design
- Long dialogue, lip sync, story exposition, or emotional melodrama
- Dissolves, slow fades, floating easing, or elegant luxury motion in place of hard beat-synced snaps
- Repeated compositions disguised by different colors
- Long text blocks or illegible typographic clutter

## Output contract

Unless the user asks for only one part, return:

1. **Style DNA** — concise classification of the source or chosen system
2. **Binding map** — HARD / CONTROLLED / FREE variables
3. **Assumptions** — only unresolved choices you filled in
4. **Final generation prompt** — one coherent English prompt, ready to paste
5. **Negative constraints** — concise block
6. **Validation summary** — cut count, time coverage, continuity, identity, palette, ratio, and drift status

When the user asks for multiple variants:
- Keep the same binding profile across all variants.
- Change one concept axis at a time where possible.
- Label what changed: character, palette, action family, motif, brand language, or tempo.
- Do not generate superficial synonyms while leaving the shot system unchanged.

## Validation gates

A result is not complete until all must-pass checks succeed:

- Exact required number of cuts
- Sequential cut numbering
- No time gaps or overlaps
- First cut begins at 0.00s
- Final cut ends at the declared total duration
- Character lock appears before the cut list
- Character description does not contradict itself
- Palette is fixed and reused
- Graphic-to-character ratio is stated
- Each cut has a distinct role and visual thesis
- At least four cross-cut handoffs are present
- At least one recurring shape and the brand token evolve across the film
- The climax and end card are clearly different functions
- No prohibited redesign or style drift

If any gate fails, repair the prompt before presenting it.
