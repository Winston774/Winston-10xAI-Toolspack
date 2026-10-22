# QA — before a deck is done

A deck is done when a design director, the subject expert and the presenter would each sign it off.
Run the tools, then look with your own eyes; the lint cannot judge hierarchy or a bad line break.

## 1 · Automated pass

```bash
node scripts/snapshot.mjs decks/<slug>/deck.html --out decks/<slug>/qa --check --slides 1-99
```

The JSON report lists, per slide: text outside the safe area, overflowing containers, text under
13 px, body content running into the footer — and whether each font family loaded. Fix everything it
reports (or know exactly why an item is intentional) and re-run until it is empty.

## 2 · Contact sheet (`qa/sheet.png`)

- Rhythm: layouts vary; dense and airy slides alternate; inverted slides are rare and purposeful.
- Alignment: titles start at the same height on every content slide; nothing floats arbitrarily.
- Weight: no slide is visibly heavier (text walls) or emptier (a lonely line) than its neighbours,
  unless it is a statement slide by design.
- Accent: one accented thing per slide.
- Style: the sheet reads as the chosen style (swiss / press / lab) from across the room, and nothing
  on it drifts back to the generic AI look — cream paper, terracotta accent, light or italic serif
  display, tracked-caps micro-labels with dashes, soft rounded cards, gradients (layouts.md §0).
  Hex colours and font names in the deck's `<style>` are deliberate exceptions only — deck CSS
  uses role tokens.

## 3 · Each slide at full size

- **Title** is a full sentence, ≤ 2 lines, no widow (1–3 characters alone on the last line), no word
  split across lines in large type. The build's phrase breaks prevent most splits, and the QA
  snapshots of `deck.html` already show them; fix what remains with `.nw` (layouts.md §2).
- **The exhibit proves the title** — exactly that claim, nothing extra.
- **Text**: no orphaned punctuation at line starts; Chinese/Latin spacing consistent; full-width
  punctuation; no `」，` collisions; English terms consistent in spelling and case.
- **Labels** don't touch lines or each other (use `halo-text`, move labels, or drop the least
  important); chart text ≥ 19 px. Leader lines start *on* the thing they name; art never runs into
  the text block above it (statement slides: check the art's tallest point against the lead).
- **Caps labels** (press and lab uppercase kickers, cover meta, chrome, glosses) don't mangle
  case-sensitive text: URLs, video IDs and brand names sit in `.keep-case`.
- **Numbers** match the source exactly (check against `source.md`, not memory); units present
  (convert imperial units for a Taiwanese audience and say it is a conversion); illustrative values
  labelled as such. Hedged claims stay hedged («暗示», «可能», «尚未驗證»).
- **Source line** present on data, quote and figure slides, one line where possible (long original
  quotes belong in the notes); credits on images, saying when a picture shows a different occasion.
- **Accent**: one accented thing per slide — in diagrams too (a red flame *and* red drops *and* a red
  stat is three).
- **Notes** exist, are speakable, include build cues and timing.

## 4 · Motion pass (Part 2)

- Filmstrip every curtain and every morph transition (`--film N`), and every slide with builds
  (`--steps --slides N`). Look for: jumps at the end of animations, morph targets fading instead of
  travelling, titles unreadable after ~900 ms, steps that reveal the point too late.
- Click through the whole deck once at presenting speed in a browser (serve the folder or open the
  dist file in Chrome); press quickly twice — transitions must finish instantly, never queue.
- Toggle M (motion off) on a few slides: everything must be visible and correct statically.

## 5 · Build outputs

```bash
node scripts/build.mjs decks/<slug>/deck.html
node scripts/snapshot.mjs decks/<slug>/dist/<slug>.html --out decks/<slug>/qa/dist --check --slides 1-99
node scripts/snapshot.mjs decks/<slug>/dist/<slug>.html --out decks/<slug>/qa/pdf --pdf decks/<slug>/dist/<slug>.pdf --slides 1
```

- Build log shows the glyph count and font size embedded (~1 MB for a CJK deck is normal), and a
  `phrase breaks: N <wbr> …` line for CJK decks (if it says *skipped*, install `uv` and rebuild).
- `qa/dist/` screenshots should break Chinese lines exactly as `qa/` did (both get the phrase pass);
  check titles and narrow columns once more.
- The lint on the dist file reports every family as `loaded` (proves the embedded subsets work).
- Open the PDF's first pages: correct fonts (no system fallback), one slide per page.

## 6 · Self-critique questions (answer honestly before handing over)

1. Could the presenter give this talk from the titles alone?
2. Is there any slide whose point I could not state in one breath? Split or cut it.
3. Which slide would a sceptical expert attack first? Is its source line strong enough?
4. Where would the audience get lost? Is there an agenda/tracker cue there?
5. Is there anything decorative that carries no meaning? Remove it.
6. Would I be proud to show this next to a top consultancy's final deck? If not, what is the gap?
