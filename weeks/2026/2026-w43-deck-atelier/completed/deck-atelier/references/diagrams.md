# Diagrams, charts and imagery

The visuals are where a deck stops looking like a template. Draw the *mechanism of this content*
(arcs between the actual words, a heatmap per head, the real architecture), not generic icons.

## Contents
1. SVG conventions
2. The diagram vocabulary (classes)
3. Recipes
4. Charts (exhibit rules)
5. Generating repetitive geometry
6. Images: when, where from, how to credit

---

## 1 · SVG conventions

- Inline `<svg class="dg" viewBox="0 0 W H">` inside a `.figure`, with `W` equal to the rendered width
  on the 1920 canvas (`span-8` → 1096, `span-6` → 812, full width → 1664). Then one viewBox unit is one
  canvas pixel and font sizes mean what they say.
- Every exhibit gets `role="img"` and an `aria-label` sentence; decorative art gets `aria-hidden="true"`.
- Text styles inherit: put a class on a `<g>` to style all its labels (`<g class="t-display t-ink"
  font-size="42" text-anchor="middle">`). Font sizes ≥ 16 for labels, ≥ 22 for the words that matter.
- Labels that sit over lines get `class="halo-text"` (a paper-coloured outline) instead of a box.
- Arrowheads: a `<marker>` with `stroke="currentColor"`, or draw small `<path class="head">`
  triangles when they must appear only after the line draws (motion).
- Words the audience reads in the diagram (tokens, terms that will move to the next slide) are better
  as HTML `.token` elements positioned over the SVG: crisper, editable, and they can carry
  `data-morph`. Position them with `left/top` (never with CSS transforms — motion animates transforms).
- Keep ids unique per deck (marker ids like `ah`, `ah2`).

## 2 · Vocabulary

Strokes: `.line` (ink-2, `--stroke`) · `.line-soft` (rule-2, 1.25) · `.line-faint` (rule, 1) ·
`.line-accent` (accent, a little heavier) · `.dash` · `.axis` · `.grid-line`. Line ends are butt and
joins mitred — crisp, not rounded.
Boxes: `.box` (paper fill, ink stroke) · `.box-soft` (paper-2, rule-2) · `.box-accent` (accent wash) ·
`.box-solid` (filled accent block). Their corners come from the style (`--r-box`: square in swiss
and press, 6 px in lab) and override any `rx` in the markup — write `rx` only on other shapes.
Fills: `.fill-ink` `.fill-ink2` `.fill-muted` `.fill-paper` `.fill-paper2` `.fill-accent`
`.fill-accent-soft` · arrowheads `.head` `.head-accent`.
Text: `.t-fig` (figure face at `--w-fig`: numbers, words-as-objects) `.t-head` (headline face)
`.t-mono` `.t-label` (label face, 15 px; caps in press and lab) `.t-ink` `.t-muted` `.t-accent` ·
`.halo-text`. (`.t-display` and `.t-serif` are old names for `.t-fig` and `.t-head`.)

All colours and faces come from tokens, so diagrams work in every style, theme and inverted slide.
Prefer geometric marks — squares, bars, straight rules, crisp arcs — over soft blobs and glows.

## 3 · Recipes (all in the Attention sample)

| Idea | Recipe | Sample slide |
|---|---|---|
| Sequence / bottleneck | boxes in a row with short arrows; a time axis; one row that is short (parallel) | 4, 5 |
| Distance / connectivity | dots on a baseline; elliptical arcs `M x1 y A rx ry 0 0 1 x2 y`; one accent arc | 5, 6 |
| Attention over words | HTML tokens on fixed slots; arcs from the focus word, width ∝ weight; weight bars below, label only the top two | 7 |
| Retrieval (Q·K·V) | three columns: question chip → ranked rows with bars → stacked mix bar | 8 |
| Equation | `--f-math` italic, upright function names, SVG radical, annotations in a 4-column row | 9 |
| Parallel variants | small multiples (8 × 8 heatmaps), one in accent, converging lines into a concat bar | 10 |
| Encoding / signal | stacked sine waves, one accent "reading line" with value dots and halo labels | 11 |
| System architecture | redraw the source figure in the vocabulary; group parts (`.g-enc`, `.g-dec`) so builds can dim them | 12 |
| Cost vs quality | scatter, log x, highlighted series, bracket annotation for the decisive comparison | 13 |

Redraw source figures rather than pasting them: the page render in `source/pages/` is your reference
for structure; the vocabulary gives it the deck's voice. Say "依原圖重繪 / redrawn from Figure n" in
the source line.

## 4 · Charts — exhibit rules

Pick the form by the comparison: ranking → bars; change over time → line/columns; part of a whole →
stacked bar (≤ 6 parts); correlation or trade-off → scatter; a single number → a stat, not a chart.

- **One message.** The title states it; the chart proves it; a takeaway or annotation points at it.
- **Highlight one series** in the accent; everything else in ink-3/rule greys. Text stays in ink
  tokens — never colour labels with the series colour; identity comes from the mark beside them.
- **Direct labels** on the marks that matter; a small legend whenever there are ≥ 2 series.
- **Hairline grid** (`.grid-line`), solid, ~5 ticks; axis titles say unit and direction
  (「越高越準」, 「越右越貴」). One y-axis only — never dual axes.
- **Bars start at zero.** If differences are small, use dots (dot plot / scatter) instead of
  truncating bars.
- **Marks:** markers ≥ 8 px with a 2.5 px paper ring (`stroke: var(--paper)`), lines 2 px, bars ≤ 24 px
  thick with square ends (corners follow `--r-chip`).
- **Annotate the decisive comparison** (bracket + two-line label: 「同樣成本 / BLEU 高出 3.8」).
- **Source line** on every chart slide, including how a derived metric was computed.
- Add `<title>` inside each mark group for hover tooltips (useful when the deck is shared).
- Projected decks need large chart text: ticks ≥ 19 px, labels ≥ 20 px.

## 5 · Generating repetitive geometry

Hand-write structural diagrams. Generate anything with many computed coordinates (arcs from weights,
heatmap cells, sine paths, scatter positions) with a small script that writes between markers in
`deck.html`:

```html
<svg class="dg" viewBox="0 0 1096 520"><!--gen:heads--><!--/gen--></svg>
```

```python
# scratchpad/gen_figs.py — re-runnable: replaces whatever sits between the markers
import re, sys
from pathlib import Path
deck = Path(sys.argv[1]); html = deck.read_text()
def heads(): ...  # return SVG markup as a string
for name, fn in {"heads": heads}.items():
    html = re.sub(rf"(<!--gen:{name}-->)(.*?)(<!--/gen-->)", lambda m: m[1] + "\n" + fn() + "\n" + m[3], html, flags=re.S)
deck.write_text(html)
```

Keep the generator in the scratchpad (or `decks/<slug>/scripts/` if the user will want to regenerate).
Put motion offsets (`data-draw`, `data-pop`) into the generated markup at the same time.

## 6 · Images

Use a photograph only when it carries information: a person who is quoted, a place, an object, a
moment in the recorded talk. Otherwise a diagram or typography does more.

Sources, in order of preference:
1. **The source itself** — `source/figures/` (images from the PDF or EPUB) and `source/frames/`
   (video keyframes named by timestamp; `contact.jpg` shows them all). Credit as the source, with the
   licence from the manifest (a CC BY YouTube talk: 「影格：講者 [hh:mm:ss] · 頻道 / YouTube · CC BY」);
   cite the timestamp. Copy the chosen file into `decks/<slug>/assets/` — re-ingesting rebuilds
   `source/`. Mind the resolution: a frame narrower than ~1280 px goes into a framed `.media` in a
   split (span-5/6), never full-bleed.
2. **Wikimedia Commons** — free, no key. API search (add `size` to `iiprop` to see the resolution):
   `https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrsearch=<q>&prop=imageinfo&iiprop=url|size|extmetadata&format=json`
   Send a descriptive User-Agent (generic agents are throttled). `extmetadata` holds licence and
   author. CC BY / BY-SA need attribution; PD / CC0 do not. Historical engravings and lithographs of a
   book's author or setting are usually public domain and make the best context image for a classic.
   Download once into `decks/<slug>/assets/` (ask the user before downloading large files); on macOS
   `sips -Z 2400 in.jpg --out out.jpg` resizes without extra tools. If the picture shows a different
   occasion than the slide's (another year, another lecture), say so in the credit.
3. **Openverse** (`api.openverse.org/v1/images/?q=…&license_type=commercial,modification`) — works
   anonymously at low rates; returns attribution strings.
4. **Pexels / Unsplash** — need the user's API key; Unsplash's terms require hotlinking, which
   conflicts with offline decks, so prefer Pexels when the user has a key.
5. Icons, if ever needed: Lucide (ISC) or Phosphor (MIT), inlined as SVG paths.

Rules: keep a `decks/<slug>/assets/credits.md` (file → author, licence, URL); show a `.credit` line
on the slide for anything that needs attribution; never present AI-generated images as real
photographs; do not use logos or brand marks to decorate (only when the brand is the subject).
Images are inlined into the single-file build automatically (`build.mjs`); resize large photos to
~2400 px on the long side first.
