# Motion — choreographing Part 2

The brief is a fashion house's landing page, not a keynote template: things *settle* into place, the
eye is led in reading order, slides hand over to each other, objects keep their identity across
slides. If the audience notices the animation before the content, it is too much.

Motion is written as attributes in `deck.html`. With `<html data-motion="off">` (the static build)
the engine ignores them, so Part 1 and Part 2 come from one source. Press M while presenting to
switch live.

## Contents
1. What the engine does by default
2. Attribute grammar
3. Recipes
4. Restraint rules and anti-patterns
5. Accessibility
6. QA with filmstrips
7. Why not Remotion / GSAP / View Transitions here

---

## 1 · Defaults (no attributes needed)

On every slide change the engine:
- exits the old slide's units: fade + rise of 34 px × depth over 480 ms, `cubic-bezier(.4,.14,1,1)`;
- reveals the new slide's units in DOM order, staggered ≤ 85 ms (whole slide within ~1.1 s), starting
  at 320 ms: text rises 46 px × depth with a 6 px blur-to-sharp over 1150 ms on expo-out
  `cubic-bezier(.16,1,.3,1)`; titles cascade character by character (opacity) while the block rises
  and sharpens; figures/SVG rise without blur (`soft`); kickers and source lines fade;
  `.cover__title .line`, `.display`, `.hero` rise out of a mask;
- keeps the chrome still: tracker and deck title don't move when unchanged; the page number rolls;
- curtains (clip-path wipe, 1150 ms, quart-in-out `cubic-bezier(.76,0,.24,1)`) when the tone changes
  (light ↔ inverted) — forward wipes upward, backward downward;
- moves `data-morph` pairs (1050 ms, quart-in-out) instead of exiting/entering them;
- finishes any running transition instantly if the presenter clicks again (never blocks the clicker).

Depth (parallax): text = 1, figures/SVG = 0.6, `.art` = 0.35. Different depths move different
distances, which is the parallax. Override with `data-depth="0.2"`.

Units are found automatically: known components (`.title`, `.points > li`, `.figure`, `.stat`,
`p`, `h3`, …) and any other visible block. A container holding a `data-morph`, `data-step` or
`data-reveal` element is split into its children so the inner element can move on its own.

## 2 · Attribute grammar

| Attribute | Where | Effect |
|---|---|---|
| `data-reveal="rise\|soft\|fade\|mask\|title\|scale\|none"` | any unit | override the reveal style |
| `data-delay="200"` | any unit | extra ms before this unit reveals |
| `data-depth="0.35"` | any unit | parallax depth for exit/entry distance |
| `data-step="1"` | any element | build: hidden until the k-th click; the slide gets `data-at="k"` |
| `data-morph="key"` | element on slide n and n+1 | shared element glides between slides (same text → pure move; different → crossfade while moving); `data-morph-stretch` allows non-uniform scaling |
| `data-draw="300"` | SVG path/line/rect/circle | stroke draws in, starting 300 ms after its unit reveals (`data-dur` to fix duration) |
| `data-pop="300"` | SVG element/group | scales from .82 and fades in |
| `data-fade="300"` | SVG element/group | fades in |
| `data-count="28.4"` | element with that number | counts up (decimals kept) |
| `data-ambient="drift\|drift-slow\|breathe\|float\|wave\|spin\|pulse\|flow\|travel"` | inner element | CSS loop while the slide is on screen |
| `data-transition="curtain\|fade\|none"` | slide | override how this slide arrives |
| `data-tone="invert"` | slide | inverted palette; implies the curtain |

Step-driven emphasis is plain CSS in the deck's `<style>`, scoped to motion mode:

```css
:root[data-motion="on"] .slide[data-at="1"] .f-group[data-term="qk"] { color: var(--accent); }
:root[data-motion="on"] .slide[data-at="1"] .arch .g-dec { opacity: .22; }
```

Ambient loops on a slide-specific element: write the keyframes in the deck style and scope them to
the active slide so they pause elsewhere:

```css
:root[data-motion="on"] .slide.is-active .seq { animation: seq-lit 5.6s var(--ease-in-out) infinite both;
  animation-delay: calc(var(--i) * .55s + 2.2s); }
```

## 3 · Recipes

- **Diagram drawing in reading order.** Give each stroke a `data-draw` offset that follows the flow
  (inputs → blocks → outputs; left → right); `data-pop` nodes just before the strokes that leave them;
  `data-fade` labels last. Keep the whole diagram under ~1.8 s.
- **Builds for dense exhibits.** Reveal the comparison in the order you will speak it: first half
  (step 0), second half (`data-step="1"`), the so-what (`data-step="2"`). Two to four steps per slide.
  Use builds to *pace*, not to hide the point: the title already states it.
- **Guided tour of a system.** Step 1 dims everything but part A (`.slide[data-at="1"] .g-b {opacity:.22}`)
  and reveals A's note; step 2 does B; the last step restores everything with the connection in accent.
- **Continuity across slides.** Morph the object the next slide is about: the word `its` on the
  attention slide becomes the Query chip on the next; `Law` and `application` slide into the key
  rows. One to three morphs per transition; they must be the same *thing*.
- **Chapter turns.** An inverted statement slide arriving by curtain marks a new chapter; the slide
  after it curtains back. Use two or three per deck.
- **Numbers.** `data-count` on the hero figures of a results slide; never on more than three.
- **Ambient life.** One loop per slide at most, and only where it explains something: a light
  travelling along an RNN chain (sequential processing), arcs breathing on a cover, a slow halo on the
  winning data point. Periods ≥ 4 s, amplitude ≤ 16 px, opacity changes ≤ 0.6.

## 4 · Restraint rules and anti-patterns

Keep: expo/quart easings, 0.8–1.3 s reveals, ≤ 85 ms staggers, ≤ 60 px travel, blur ≤ 8 px, masks.

Avoid: bounce/elastic easing; spinning, flipping, zooming slides; 3D; anything faster than 250 ms
except exits; slide-wide wipes on every slide; more than one ambient loop per slide; typing effects;
counting every number; morphing unrelated objects; steps that make the presenter click more than
four times on one slide; motion on text the audience is trying to read.

## 5 · Accessibility

`prefers-reduced-motion: reduce` turns every transition into a 260 ms crossfade and stops ambient
loops; the M key does the same for the whole room. Never encode meaning only in motion — the static
build must tell the same story.

## 6 · QA with filmstrips

```bash
node scripts/snapshot.mjs decks/<slug>/deck.html --out decks/<slug>/qa/film --film 8 --at 0,160,360,620,950,1500
node scripts/snapshot.mjs decks/<slug>/deck.html --out decks/<slug>/qa/steps --steps --slides 9
```

`--film N` freezes every animation of the transition into slide N at the listed milliseconds and
writes a sheet. Check: the old slide is gone by ~600 ms; nothing jumps at the end (a jump means a
unit carries a CSS transform, or a morph target lives inside an animated container); morphs travel
in a straight, readable path; the title is legible by ~900 ms; curtains cover fully by ~1150 ms.
`--steps` captures each build state of a slide.

## 7 · Why the engine is WAAPI and not Remotion, GSAP or View Transitions

- **Remotion** renders frame-based video. It is excellent for exporting the deck as an MP4 (an
  optional follow-up), but live presenting needs click-driven, interruptible state; it also needs
  React, a bundler, and a company licence above three people.
- **GSAP** is free since 2025 (including Flip/SplitText), but its licence forbids use in tools that
  compete with Webflow's visual animation builder; the native Web Animations API does everything this
  engine needs with zero bytes and no licence questions.
- **View Transitions** snapshot elements as bitmaps (text blurs while scaling) and have limits inside
  scaled stages; the engine's own FLIP keeps live, crisp text.
