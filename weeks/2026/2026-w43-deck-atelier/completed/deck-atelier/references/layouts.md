# Layouts — the design system and the markup for every slide type

Everything here is implemented in `assets/engine/atelier.css`. Write slides with these classes and
the deck inherits the system; put deck-specific styles in the `<style>` block of `deck.html`.

## Contents
0. Choose a style
1. Canvas, grid, tokens
2. Type: roles, faces, the Chinese/Latin pairing
3. Slide anatomy and attributes
4. Layout catalog (markup)
5. Components
6. Rhythm across a deck

---

## 0 · Choose a style

Ten styles, set once on `<html data-style="…">` (scaffold: `new_deck.mjs --style …`; switch an
existing deck: `set_style.mjs`). Each has a light and a dark theme (`data-theme`, T while
presenting). Y / Shift+Y cycle all ten live as a preview — another style's fonts then load from
Google Fonts, so previews need internet; the deck's own style is embedded by the build.

| Style | Look and signature | Pick it for |
|---|---|---|
| `swiss` 網格 (default) | white, near-black, cobalt; Archivo + 黑體 bold; 3 px structural rules; square markers; inverted slides are a full **colour field** | reports, science, most talks — clear and confident |
| `press` 號外 | pure white, black, signal red; condensed black headlines; 6 px rules; black tag kickers; running-head rule; `<em>` is a **yellow highlighter** | punchy talks, a book with a strong thesis, anything urgent |
| `lab` 實驗室 | cool grey on a 40 px grid, signal green; IBM Plex Mono labels and figures, `[01]`, `//` kickers; boxed takeaways; navy blueprint inverts | research papers, engineering, data |
| `tokyo` 日式雜誌 | heavy 明朝 (Noto Serif TC 800) headlines, thin Josefin numerals, `No.01`, double rules, a **vertical running head** with 縱中橫 numbers, `<em>` gets **傍點 emphasis dots**, 瑠璃 blue; black spreads | culture, design, travel, food, lifestyle, humanities; anything that wants a Japanese-magazine feel |
| `kinfolk` 慢生活 | stone paper, light Cormorant + 明朝 headlines, airy light Jost body, monochrome with a muted olive, hairlines, no markers, centred statements; olive-charcoal inverts | slow, reflective topics: wellbeing, craft, philosophy, an author's life; photo-led decks |
| `dopamine` 多巴胺 | white with six saturated colours; Bricolage Grotesque + **粉圓 (Huninn)** headlines; a rainbow edge, pill kickers, yellow pill `<em>`, numbered colour dots, blobs; violet fields | young audiences, classrooms, events, product launches — joy and energy |
| `glitch` 故障 (dark) | near-black, cyan/magenta **RGB split** on display type, scanlines, Chakra Petch + Space Mono, `>` prompt kickers with a blinking cursor, an occasional jitter on statements; acid-lime inverts | technology, AI, security, games, the future — use the dark theme |
| `geometric` 幾何抽象 | Bauhaus red / yellow / blue on light grey; Futura-like Jost; circle · square · triangle markers, tri-colour bars, a **Bauhaus composition** on statement slides; blue fields | design, architecture, maths, structure, art history |
| `postmodern` 後現代 | Memphis: Syne + 黑體 900, **wavy underlines**, tilted tag kickers, outlined colour numbers, **hard offset shadows**, confetti on statements; teal fields | creative, playful or contrarian talks; art and pop culture |
| `riso` 孔版印刷 | two spot inks — riso blue text and fluorescent pink — with **misregistration**, paper grain, halftone dots, pink highlighter `<em>`, blue monotone photos, 芫荽 (Iansui) hand-lettered body; pink sheets as inverts | zines, education, community, independent culture — warm and handmade |

How to choose: match the **content's character** first (a paper → lab or swiss; a lifestyle book →
kinfolk or tokyo; a youth event → dopamine), then the **room** (dark hall or LED wall → the dark
theme; glitch is dark by default), then the **presenter's personality**. When the user hasn't
named a style and it matters, show them a gallery of their own deck in a few candidates
(`snapshot.mjs … --styles swiss,tokyo,dopamine --slides 1,2,6`) and let them pick.

Commit to one style per deck and design inside its voice; every slide is QA'd in that style.
Switching later is a token change, but re-run QA — widths differ between styles (Plex Mono, Syne
and Bricolage set wide; condensed Archivo and Cormorant narrow; Cormorant's figures are tall), so
tight rows of tokens, labels or stats may need adjusting.

Chinese typefaces in the styles all follow Taiwan's standard glyph forms (為, 真). Don't swap in
LXGW WenKai TC (霞鶩文楷): it uses old forms (爲, 眞) that look wrong to a Taiwanese audience.

**Never rebuild the generic AI look** inside a deck's `<style>`: cream/beige paper with a
terracotta or coral accent, light or italic serif display type used by default, tracked-caps
micro-labels with a dash before each, purple gradients, soft rounded cards with drop shadows.
(tokyo and kinfolk use serif headlines on purpose — always with their own palette and devices,
never with cream and terracotta.)

## 1 · Canvas, grid, tokens

- Fixed canvas **1920 × 1080**, scaled to fit the screen (letterboxed with the stage colour).
  All sizes are canvas pixels — design as if the screen were exactly 1920 wide.
- Margins: 128 px left/right; content starts at y ≈ 132 (below the chrome) and ends at y ≈ 968.
  Chrome (tracker, deck title, page number, source line) sits in the 56 px bands top and bottom.
- `.grid` = 12 columns, 40 px gutters → one column ≈ 102 px. `span-4` ≈ 528 px, `span-6` ≈ 812 px,
  `span-8` ≈ 1096 px. Size SVG viewBoxes to these widths so 1 unit = 1 canvas px.
- Colour tokens: `--paper --paper-2 --paper-3 --ink --ink-2 --ink-3 --rule --rule-2 --accent
  --accent-ink --accent-soft --accent-wash` (+ `--mark`, press's highlighter; `--field`, swiss's
  colour-field slides). A single slide flips with `data-tone="invert"`.
- Shape tokens: `--bar` (structural rule weight, 1–8 px by style), `--r-box` and `--r-chip`
  (corners: square in most styles, 6 px in lab and riso, 28 px and pills in dopamine), `--r-dot`
  (square or round markers), `--stroke` (diagram line weight). Some styles add palette tokens their
  signatures use (`--c1…--c6` in dopamine and postmodern, `--c-r --c-y --c-b` in geometric).
- **Use tokens, never hex or font names** in deck CSS and SVG, so every style, theme and inverted
  slide works.
- **A different accent for one deck** (vetted for contrast; swiss's colour field follows it): put this
  in the deck's `<style>` — the `[data-style]` selector is needed to outrank the engine's style rules.
  ```css
  :root[data-style] { --accent: #00843D; --accent-ink: #00702F; --field: #00843D; }
  :root[data-style]:is([data-theme="dark"], [data-theme="noir"]) { --accent: #2FD27A; --accent-ink: #4ADE8A; }
  ```
  | Accent | light `--accent` / `--accent-ink` | dark `--accent` / `--accent-ink` | fits |
  |---|---|---|---|
  | cobalt (swiss default) | `#2340FF` / `#1E35DC` | `#6F86FF` / `#8C9EFF` | swiss |
  | green | `#00843D` / `#00702F` | `#2FD27A` / `#4ADE8A` | swiss, lab (lab default `#00875F`) |
  | signal red (press default) | `#E4002B` / `#CC0026` | `#FF3651` / `#FF5068` | swiss, press |
  | magenta | `#E6007E` / `#C4006B` | `#FF4FA7` / `#FF6BB5` | swiss, press |
  Avoid orange, terracotta, coral and beige accents, and any accent that cannot carry white text
  (swiss puts white text on the field). The other styles' palettes are part of their identity
  (tokyo's 瑠璃, riso's two inks, geometric's primaries); change them only when the user asks.

## 2 · Type

Every component reads **role tokens**; a style is a set of values for them.

| Role token | Used by |
|---|---|
| `--f-head` + `--w-head`, `--tr-head`, `--lh-title` | `.title`, `.statement`, `h3`, `.takeaway`, Chinese cover titles |
| `--f-text` + `--w-text` | body, lead, notes, tables |
| `--f-fig` + `--w-fig`, `--x-fig`, `--tr-fig` | numerals, Latin cover titles, `.token`, `.stat__value`, `.n` |
| `--f-label`, `--w-label`, `--case-label`, `--tr-label` | `.kicker`, chrome, `.en`, table heads, `.t-label` |
| `--f-math` (set italic) · `--f-mono` | `.math`, formulas · `.mono`, `.t-mono`, code |

Faces per style (Latin · Chinese):

| Style | Headlines | Text | Figures · labels |
|---|---|---|---|
| swiss | Archivo 700 · Noto Sans TC 700 | Archivo · Noto Sans TC | Archivo 700 · Archivo 600 |
| press | Archivo 900 · Noto Sans TC 900 | Archivo · Noto Sans TC | Archivo 800 at 72 % width · caps |
| lab | Archivo 600 · Noto Sans TC 600 | Archivo · Noto Sans TC | IBM Plex Mono · caps |
| tokyo | Noto Serif TC 800 (明朝) | Noto Sans TC | Josefin Sans 300 · caps |
| kinfolk | Cormorant Garamond 400 · Noto Serif TC 400 | Jost 300 · Noto Sans TC 300 | Cormorant 300 · Jost caps |
| dopamine | Bricolage Grotesque 800 · Huninn 粉圓 | Bricolage · Noto Sans TC | Bricolage 800 |
| glitch | Chakra Petch 700 · Noto Sans TC 700 | Chakra Petch · Noto Sans TC | Space Mono · caps |
| geometric | Jost 700 · Noto Sans TC 700 | Jost · Noto Sans TC | Jost 500 · caps |
| postmodern | Syne 800 · Noto Sans TC 900 | Noto Sans TC | Syne 800 · caps |
| riso | Rubik 800 · Noto Sans TC 900 | Rubik · Iansui 芫荽 | Rubik 800 · caps |

Sizes (canvas px) vary a little per style: hero 138–208 · statement 70–96 · title 52–62 · h3 in
components 36–42 · lead 32 · body 28 · small 22 · label 14–16 · source 15.

- The old names still resolve — `--f-display` → `--f-fig`, `--f-serif` → `--f-head`, `--f-sans` →
  `--f-text` — but write the role names in new decks.
- Emphasis: `<em>` is the accent colour (swiss, lab) or the highlighter band (press). Never italics,
  never bold-plus-colour. At most one phrase per title.
- `<i>` marks a variable, a quoted word or a foreign term: the text face's own italic at the same
  size. Don't enlarge it or switch it to a display face.
- Glosses: `<span class="en">Parallel</span>` inside an `h3` is a label-style second name (small,
  `--f-label`, uppercase in press and lab) — not an italic subtitle.
- Big numbers are the figure face at weight (`--w-fig`), tight tracking (`--tr-fig`), tabular.
  A Chinese unit inside one: `<span class="cjk-unit">萬</span>` (engine-styled).
- Text sizes below 18 px are for chrome and sources only. Diagram labels ≥ 16 px, chart text ≥ 17 px.
- Line-height: titles 1.2–1.3 (`--lh-title`), body 1.7. `text-wrap: balance` is on for titles and
  statements; `pretty` for paragraphs.
- **Phrase-aware wrapping (Chinese) is automatic — write plain text.** Browsers break CJK text
  between any two characters, which splits words in large type (看｜見, 注｜意力). `build.mjs` fixes
  this in the bundle: BudouX proposes phrase boundaries, ICU's word dictionary must confirm each one,
  and one-character particles or function words (的 了 更 不 每 一個…) never sit alone at a line edge.
  Each surviving boundary becomes a `<wbr>`, and the element gets `data-phrase="auto"`
  (→ `word-break: keep-all; overflow-wrap: anywhere`): lines break only between phrases, and a phrase
  longer than its line still wraps instead of overflowing. The build also glues a number to its CJK
  unit (`12&nbsp;小時`, `第&nbsp;7`) and a linking symbol to its words (`英→德`).
  - Covered: `.title .statement .lead .takeaway .stat__label .desc .caption` and `h2 h3 h4 p li td
    th figcaption blockquote` elements that contain CJK text and no other covered element.
  - Never touched: `deck.html` itself, SVG text, `.notes`, code, anything inside `[data-phrase]`.
  - Edited in the browser (E): that element drops its phrase breaks and wraps per character until
    the next build; untouched elements keep theirs when the bundle is saved.
  - Needs `uv` (BudouX runs in `scripts/phrase.py`); `--no-phrase` skips the pass. The model follows
    `<html lang>`: zh-Hant (default), zh-Hans, ja.
- **Manual override: `.nw`.** If an automatic break still lands badly, take that element over by
  hand: wrap its phrase units in `<span class="nw">…</span>` (each unit ≤ the column width). An
  element holding a `.nw` span or an authored `<wbr>` is left exactly as written. Example:
  `<p><span class="nw">RNN 把句子當成一條隊伍：</span><span class="nw">第 <i>t</i> 個字，</span>…</p>`.
  `data-phrase="off"` on an element or a whole slide keeps the browser's default breaking instead.
- Judge wrapping in `snapshot.mjs` output: it renders `deck.html` with the same phrase breaks as the
  build (and `dist/<slug>.html` has them built in). Only `deck.html` opened directly in a browser
  still breaks per character. Widows remain a QA item: a last line of 1–3 characters is a fix.
- Spaces: one ASCII space between Chinese and Latin/digits; none next to full-width punctuation.

## 3 · Slide anatomy

```html
<main class="deck" data-title="Deck title shown top-right">
  <section class="slide" data-chapter="01" data-chapter-title="困境 · The Bottleneck">
    <div class="head">
      <p class="kicker">Short label above the title</p>
      <h2 class="title">Action title as a full sentence, with <em>one accent</em></h2>
    </div>
    <div class="body"> … layout … </div>
    <p class="source">資料來源：Author (Year), Table 2。</p>
    <aside class="notes"><p>What to say…</p></aside>
  </section>
</main>
```

Slide attributes:

| Attribute | Effect |
|---|---|
| `data-layout` | `cover`, `statement`, `chapter`, `closing`, `image` (special layouts); omit for content slides |
| `data-chapter` / `data-chapter-title` | starts a chapter; the tracker (top-left) shows it on this and following slides |
| `data-tracker` | overrides the tracker text for one slide (e.g. 摘要 · Summary) |
| `data-chrome` | `none` (cover) or `minimal` (no top chrome) |
| `data-tone="invert"` | the style's inverted slide — swiss: colour field; press: black (yellow in dark); lab: navy blueprint (light paper in dark); arrives with a curtain in motion mode |
| `data-transition` | `curtain`, `fade`, `none` — motion mode only (see motion.md) |
| `data-source` | alternative to a `.source` element (not editable in the browser) |

`.body` modifiers: `body--center` (vertically centre the content) and `body--end` (bottom-align).
Answer-first slides (summary, agenda) read best centred; statements are centred by their layout.

## 4 · Layout catalog

Use the Attention deck (`examples/attention/deck.html`, swiss) as the reference implementation of each.

**Cover** — huge title bottom-left (Latin in the figure face, set tight and heavy), one-line
subtitle, metadata strip, a piece of geometric art that foreshadows the talk (top-right; solid
blocks, rules and the talk's own diagram motifs suit the styles better than soft curves).
`data-chrome="none"`.
```html
<section class="slide" data-layout="cover" data-chrome="none">
  <div class="cover__meta"><span>NeurIPS 2017</span><span class="dot"></span><span>論文導讀</span></div>
  <figure class="cover-art" aria-hidden="true" data-depth="0.35"><svg class="dg" viewBox="0 0 812 320">…</svg></figure>
  <h1 class="cover__title" lang="en"><span class="line">Attention</span><span class="line">Is All You <em>Need</em></span></h1>
  <p class="cover__subtitle">One sentence that says why this matters</p>
  <div class="cover__foot"><span>Authors / presenter</span><span>Affiliation · date</span></div>
</section>
```
Position the art in deck CSS (`.cover-art { position:absolute; left:…; top:…; width:…; }`) so it
never collides with the title block — check it in the deck's style (press's title is taller). A
Chinese title needs nothing extra: without `lang="en"` the engine sets `.cover__title` in the
headline face at 70 % of the hero size. Long Latin titles: break them into `.line`s or lower the
size on that element; never let the lint report overflow.

**Summary (answer first)** — title = governing thought; three numbered supports.
```html
<div class="body body--center">
  <ol class="points">            <!-- .cols-2 / .cols-4 for two or four -->
    <li><span class="n">01</span><h3>更快<span class="en">Parallel</span></h3><p>…</p></li>
    …
  </ol>
</div>
```

**Agenda** — 2×2 numbered questions; each chapter phrased as the question it answers.
```html
<ol class="agenda"><li><span class="n">01</span><div><h3>困境<span class="en">The bottleneck</span></h3><p>…？</p></div></li>…</ol>
```

**Split: text + figure** — the workhorse. Text 4–5 columns, figure 7–8.
```html
<div class="body"><div class="grid">
  <div class="span-4 stack stack--lg self-center"><p>…</p><p>…</p></div>
  <figure class="figure span-8 self-center"><svg class="dg" viewBox="0 0 1096 470">…</svg></figure>
</div></div>
```

**Exhibit** — one full-width figure or two side-by-side mini-exhibits, then the so-what.
```html
<div class="grid" style="grid-template-rows:auto auto; align-content:center; row-gap:80px">
  <div class="span-6"><div class="exhibit__h">…</div><svg class="dg" viewBox="0 0 812 340">…</svg></div>
  <div class="span-6">…</div>
  <p class="takeaway span-12">The one sentence the exhibit proves.</p>
</div>
```

**Statement** — one question or claim; usually inverted (a colour field in swiss, black in press,
blueprint in lab); optional art at the bottom.
```html
<section class="slide" data-layout="statement" data-tone="invert">
  <div class="body"><p class="kicker">核心想法 · The Idea</p>
    <p class="statement">如果每個字，都能直接看見句子裡的<em>每一個字</em>？</p>
    <p class="lead">One supporting sentence.</p></div>
</section>
```

**Chapter opener** — for decks of 20+ slides.
```html
<section class="slide" data-layout="chapter" data-tone="invert" data-chapter="02" data-chapter-title="機制">
  <p class="chapter__n">02</p><h2 class="chapter__title">注意力如何運作</h2><p class="chapter__sub">…</p>
</section>
```

**Formula** — one equation set large in `--f-math` (italic), annotations in a 4-column row below.
See slide 9 of the sample (`.formula`, `.f-frac`, `.f-num`, `.f-den` with an SVG radical,
`.annots`). Function names upright, variables italic.

**Comparison table** — a strong rule under the head, hairlines between rows; the row that matters
gets `is-key` (tinted, with an accent bar).
```html
<table class="table"><thead><tr><th>Layer</th><th>Sequential ops</th><th>Max path</th></tr></thead>
<tbody><tr class="is-key"><td>Self-attention</td><td class="math">O(1)</td><td class="math">O(1)</td></tr>…</tbody></table>
```

**Stats** — 2–4 figures that matter, each with a one-line label.
```html
<div class="stats" style="--n:3">
  <div class="stat"><div class="stat__value"><span data-count="28.4">28.4</span><small>BLEU</small></div>
    <div class="stat__label">英→德翻譯，比先前最佳高出 2 分以上</div></div> …
</div>
```
A Chinese unit inside a big numeral: `<span class="cjk-unit">萬</span>` (the engine sets it at
half size in the headline face; see slide 14 of the sample).

**Timeline** — up to 6 milestones; the one that matters gets `is-key`.
```html
<ol class="timeline" style="--n:6">
  <li class="is-key"><span class="when">2017</span><span class="dot"></span>
    <p class="what"><span class="en">Transformer</span></p><p class="desc">…</p></li> …
</ol>
```

**Quote** — `<blockquote class="quote">「…」<cite>— Name, Source, Year</cite></blockquote>` on a
statement-like slide; one per deck at most.

**Image** — a photograph or video frame that carries meaning. Full-bleed:
```html
<section class="slide" data-layout="image">
  <figure class="media"><img src="assets/photo.jpg" alt="…"></figure>
  <div class="overlay"><p class="kicker">…</p><h2 class="title">…</h2></div>
  <p class="credit">Photo: Name / Wikimedia Commons, CC BY-SA 4.0</p>
</section>
```
Framed inside a split: `<figure class="media span-7" style="height:560px"><img …></figure>`.

**Closing** — the line to remember (`.closing__line`: Latin in the figure face, Chinese in the
headline face), three takeaways, thanks/Q&A. Usually inverted to bookend the statement slide. See
slide 15 of the sample.

## 5 · Components

| Class | Use |
|---|---|
| `.kicker` | short label above a title — swiss: accent square; press: black tag; lab: `//` prefix (`.kicker--plain` without a mark) |
| `.title`, `.statement`, `.lead` | headline levels |
| `.points` (`.cols-2`, `.cols-4`) | numbered arguments in columns under a structural rule, each with `.n`, `h3` (+ `.en`), `p` |
| `.list` | bullet list with square (or round, lab) accent markers (2–4 items) |
| `.en` | gloss: a label-style second-language name inside a heading |
| `.stat`, `.stat--sm`, `.stats` | figures; `data-count` makes them count up in motion mode |
| `.takeaway` | the so-what: a heavy accent bar on the left (lab: a tinted box) |
| `.note`, `.caption`, `.credit`, `.source` | small explanatory text, figure captions, image credits, source line |
| `.table` | comparisons |
| `.timeline` | milestones |
| `.chip`, `.chip--accent`, `.token` | inline tokens; `.token` is the figure-face word used in diagrams (Archivo / Plex Mono) |
| `.rule`, `.rule--bar` | a hairline / a structural rule (`--bar` thick) as a separator |
| `.figure` | frame for an SVG; `figcaption` for the illustrative-value note |
| `.media` | photos/video frames, cropped with `object-fit: cover` |
| `.nw` | keep a phrase on one line — manual override; the build's automatic phrase breaks skip its element |
| `.keep-case` | inside caps labels (press and lab uppercase `.kicker`, cover meta, chrome, `.label`, `.en`): keeps URLs, video IDs and brand names (TEDx, iPhone, arXiv) as written — uppercasing breaks a link like `youtu.be/LdDnPYr6R0o` |
| `.accent`, `.muted`, `.ink`, `.head-face`, `.fig-face`, `.mono`, `.italic`, `.num`, `.tabular` | utilities (`.serif` / `.display-face` are old aliases of `.head-face` / `.fig-face`) |
| `.grid`, `.span-N`, `.start-N`, `.stack(--sm/--lg)`, `.self-center`, `.self-end` | layout |

## 6 · Rhythm

- Change the layout family every one or two slides (split → exhibit → statement → stats …).
- Alternate density: after two evidence-heavy slides, give the audience a breathing slide.
- Use inverted tone for at most ~15% of slides: statements, chapter openers, the closing. In swiss
  these are full colour fields — the strongest moment in the deck; spend them on chapter turns.
- Keep a consistent vertical rhythm: titles always start at the same y; bodies align to the grid.
- The accent colour should mark the single most important thing on each slide — if three things are
  accented, nothing is.
