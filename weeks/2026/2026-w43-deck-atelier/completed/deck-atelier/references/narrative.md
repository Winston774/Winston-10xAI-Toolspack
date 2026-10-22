# Narrative — from material to a talk people can follow

A deck is an argument delivered at speaking pace. The audience cannot re-read, so the structure must
carry them: they should always know *where they are*, *what the point of this slide is*, and *why it
follows from the last one*. The presenter, too, should be able to give the talk from the titles alone.

## Contents
1. The method (governing thought → SCQA → key lines → ghost deck)
2. Action titles
3. Copy rules (Chinese and English)
4. Planning exactly N slides
5. Templates by source type
6. Audience calibration and analogies
7. Speaker notes
8. `storyline.md` format

---

## 1 · The method

Work top-down, in this order. Do not open `deck.html` before step 4 is written.

1. **Governing thought.** One sentence, the answer: what the audience should believe or do after the
   talk. For the Attention paper: 「只靠注意力，Transformer 做到了更快、更準，也更能擴展」.
2. **SCQA introduction** (Minto). *Situation* the audience already accepts → *Complication* that
   creates tension → the *Question* it raises → the *Answer* (= governing thought).
   Attention: RNNs dominate translation (S) → they compute word by word, slow and forgetful (C) →
   can we drop recurrence entirely? (Q) → yes, attention alone is faster and better (A).
3. **Key lines.** 3–5 supporting claims, each a full sentence, mutually exclusive and together
   sufficient (MECE). They usually become the chapters. Order them by time, by structure
   (problem → mechanism → evidence → impact), or by importance — and say which in your head.
4. **Ghost deck.** One line per slide: the action title + the layout + the exhibit you intend.
   Test it two ways:
   - *Horizontal (the story):* read only the titles in order. Does it flow as one argument without
     gaps or repeats?
   - *Vertical (the proof):* for each slide, does the exhibit prove exactly its title — no more, no less?

Answer first. Put the governing thought and its supports on slide 2 (an executive summary) so the
audience knows where the talk is going; the rest of the deck earns it.

## 2 · Action titles

The title is the slide's conclusion, written as a sentence a listener could repeat.

| Weak (topic label) | Strong (action title) |
|---|---|
| RNN 的問題 | 逐字計算帶來兩個瓶頸：慢，而且健忘 |
| 實驗結果 | 更準，也更省：以一小部分的訓練成本，刷新翻譯紀錄 |
| Multi-Head Attention | 八個注意力頭，同時從八個角度閱讀同一句話 |
| Results | Same compute, 3.8 BLEU better: the Transformer wins on cost and quality |

Rules:
- Full sentence with a verb; states the takeaway; quantified when the slide has numbers.
- At most two lines on the 1920 canvas at title size: Chinese ≈ 20–36 characters (hard ceiling ≈ 40),
  English ≤ 15 words. Too long means the slide holds two messages — split it.
- No "and" stacking two claims (「並且」「同時」「以及」 joining two points is a split signal).
- Parallel titles for parallel slides (「更快／更準／更能擴展」).
- Accent (`<em>`) at most one phrase per title — the words you would stress aloud.
- English terms inside Chinese titles in `<i>` get the text face's italic (`模型讀到 <i>its</i> 時…`).

Statement slides (`data-layout="statement"`) are the exception: a single provocative question or
claim, used once or twice per deck to turn a chapter.

## 3 · Copy rules

- **One message per slide.** Body text proves the title; it does not introduce new claims.
- **Few words.** Body blocks ≤ 3 sentences; lists of 2–4 items; a number beats an adjective.
  What the presenter will *say* goes in the notes, not on the slide (redundancy hurts recall).
- **Concrete and sourced.** Numbers with units, scope and source (「英→德翻譯 BLEU 28.4」, not
  「大幅提升」). Mark illustrative values as such on the slide (「示意數值」).
- **Parallel structure** across columns and list items (same grammatical shape, similar length).
- **Define jargon once,** at first use, in plain words (「Query：我在找什麼？」).

Traditional Chinese (Taiwan) specifics:
- Full-width punctuation: ，。、；：？！「」『』（）——⋯⋯. Quotes are 「」, nested 『』.
- Keep English technical terms in English; put a space between Chinese and Latin letters or digits
  (`Transformer 只靠注意力`, `12 小時`), but not next to full-width punctuation.
- Avoid filler: 進行、相關、的部分、透過…來、針對、有效地. Prefer verbs: 「訓練 12 小時」 not 「進行 12 小時的訓練」.
- Avoid two adjacent closing marks like 「」，」 — rephrase so a mark is not followed by a comma.
- Chinese wraps between any two characters. In titles, leads, stats and narrow columns, keep phrases
  intact with `<span class="nw">片語</span>` (see layouts.md); body paragraphs may wrap naturally.

English decks: sentence case for titles, no terminal period on titles, serial comma, numerals for
all measurements.

## 4 · Planning exactly N slides

Budget ≈ 1 slide per spoken minute (1–2 minutes for dense exhibits). When the user names N, hit N
exactly by planning, never by cramming. Fixed skeleton first, then distribute the rest across key lines
in proportion to their importance to the governing thought.

| N | Skeleton |
|---|---|
| 5 | cover · summary (answer + 3 supports) · the one mechanism/insight · the evidence · takeaways |
| 8 | cover · summary · problem · idea (statement) · mechanism · evidence · impact · takeaways |
| 10–12 | + agenda · one more mechanism slide · one more evidence slide · a chapter-turn statement |
| 15 | the Attention sample: cover, summary, agenda, 2 × problem, statement, 6 × mechanism, results, legacy, closing |
| 20–30 | + chapter openers (`data-layout="chapter"`), one example/case slide per key line, an appendix after the closing |

Compressing (fewer slides than content): merge sibling mechanism slides into one exhibit with builds;
move derivations and secondary numbers to notes or an appendix; keep the summary and the strongest
exhibit — those are what people remember.
Expanding: give each key line its own evidence slide; add a worked example; add chapter openers and a
statement slide; split any slide whose exhibit has two halves.

When resizing an existing deck, rewrite `storyline.md` first, then change `deck.html` to match.

## 5 · Templates by source type

**Research paper** — problem → why existing approaches fail (with the paper's own comparison) →
the core idea in one sentence (statement slide) → mechanism, one component per slide, each with a
redrawn figure → results as one decisive exhibit (cost vs quality, before vs after) → limitations
(optional) → impact → takeaways. Use the paper's real examples (appendix figures are gold).

**Book** — the author's thesis → 3–5 big ideas (one chapter each; a story or case for each) →
what changes in practice → takeaways. Quote sparingly, one line at a time, with page numbers — or, when
the manifest says the edition has none (most EPUBs), with the chapter (「Lecture III」「第 4 章」). A
book that is itself a course of lectures or chapters can lend its table of contents to the agenda
slide. For a foreign-language book, put the translation on the slide and the original line under it,
small and italic — the audience trusts a quote they can check.

**Talk / interview / lecture (video or audio)** — the speaker's core message → the moments that carry
it, each with a timestamp and a quote → what to do with it. Cite `[hh:mm:ss]` in source lines so the
presenter can play the clip. Use a keyframe only where the picture carries information: a slide the
speaker showed, a demonstration, or the speaker once (who is talking). Single-camera talks rarely offer
more — look at `frames/contact.jpg` before planning visuals, and draw the rest. A talk usually gives
claims without data (no sample sizes, no effect sizes): do not invent numbers to fill a chart; show the
design of the study, the task, the comparison, and label it 示意. Keep the speaker's hedges («suggest»,
«we haven't done this») in the title or on the slide.

**Report / data / business document** — answer first (recommendation) → the drivers (one exhibit
each) → implications and options → recommendation with next steps and owners.

**Several sources** — organise by question, not by source; attribute each claim.

## 6 · Audience calibration

- Experts: skip the analogy, show the equation and the ablation; more density per slide is fine.
- General audiences: one analogy per hard concept, introduced before the formalism
  (Query/Key/Value as a library: 問題、書背標籤、書的內容), then the formal version.
- Students/teachers: add a "how to read this figure" sentence; make the agenda explicit; end with
  questions to think about.
- Executives: answer, numbers, decision, risks — in that order; push the mechanism to the appendix.

## 7 · Speaker notes

Write notes the presenter can actually speak: 2–4 short paragraphs per slide, conversational, in the
deck's language. Include where to point (「指著最粗的線」), build cues (「（下一步）」 / "(next)"),
a transition sentence into the next slide when the link is not obvious, and a time hint (「約 1 分鐘」).
Facts in notes need the same accuracy as facts on slides.

## 8 · `storyline.md` format

```markdown
# <Deck title>
Audience: … · Occasion: … · Length: N slides / M minutes · Language: …
Governing thought: …
SCQA: S … / C … / Q … / A …

| # | Chapter | Action title | Layout | Exhibit / visual | Source |
|---|---|---|---|---|---|
| 1 | — | (cover) Attention Is All You Need | cover | attention arcs | — |
| 2 | 摘要 | 只靠注意力，Transformer 做到了更快、更準，也更能擴展 | points ×3 | — | Abstract, Table 2 |
| … |
```
