/* ============================================================================
   deck-atelier · phrase.mjs — phrase-aware line breaks for CJK text, shared by
   build.mjs (the bundle) and snapshot.mjs (QA renders of deck.html).

     import { phraseBreaks, deckLang } from './phrase.mjs';
     const { html: out, elements, breaks, glue } = phraseBreaks(html, deckLang(html));

   Chinese may wrap between any two characters, which splits words in large type.
   BudouX (scripts/phrase.py, run through `uv`) proposes phrase boundaries; ICU's
   dictionary (Intl.Segmenter) must agree that each one falls between two words, and a
   one-character particle (的 了 們…) or a leaning function word (更 不 每 把…) is never
   left alone at a line edge. Survivors become <wbr>, and the element gets
   data-phrase="auto", which atelier.css turns into word-break: keep-all (break only
   there) + overflow-wrap: anywhere (never overflow). Two kinds of glue go with it: a
   no-break space between a number and its CJK unit (2026&nbsp;年, 第&nbsp;7), and word
   joiners around a symbol that links two words (英&#8288;→&#8288;德), which keep-all
   alone would let break. Hands off: SVG, notes, code, anything inside [data-phrase],
   and elements that hold a .nw span or an authored <wbr> — those are set by hand.
   phraseBreaks throws when `uv` or phrase.py fails; callers log it and carry on.
   ========================================================================== */
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const PHRASE_PY = fileURLToPath(new URL('phrase.py', import.meta.url));

// the one rule phrase breaks need; engine copies older than phrase breaks lack it
export const PHRASE_CSS = '[data-phrase="auto"] { word-break: keep-all; overflow-wrap: anywhere; }';

// <html lang> picks the BudouX model (phrase.py): zh-Hant unless the deck says otherwise
export const deckLang = (html) => (html.match(/<html\b[^>]*\blang=["']?([\w-]+)/i)?.[1] || 'zh-Hant').replace(/_/g, '-');

const PHRASE_TAGS = new Set(['p', 'h2', 'h3', 'h4', 'li', 'td', 'th', 'figcaption', 'blockquote']);
const PHRASE_CLASSES = ['title', 'statement', 'lead', 'takeaway', 'stat__label', 'desc', 'caption'];
const HANDS_OFF = new Set(['svg', 'math', 'script', 'style', 'template', 'textarea', 'pre', 'code', 'kbd', 'samp', 'noscript']);
const RAW_TEXT = new Set(['script', 'style', 'textarea', 'title', 'noscript']);
const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);
const BLOCK = new Set(['br', 'hr', 'div', 'p', 'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'table', 'tr', 'td', 'th', 'figure', 'blockquote', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']);
const ENTITY = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: '\u00A0', ensp: '\u2002', emsp: '\u2003', thinsp: '\u2009',
  mdash: '—', ndash: '–', hellip: '…', middot: '·', times: '×', rarr: '→', larr: '←', ldquo: '“', rdquo: '”', lsquo: '‘', rsquo: '’',
};
const CJK = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Bopomofo}〇]/u;
const LETTER = /[\p{L}〇]/u; // letters of any script; digits, punctuation, symbols and spaces never take a <wbr>
const DIGIT = /\p{Nd}/u;
const LINKER = /[\u2190-\u21FF\u27F0-\u27FF×÷±=+−~～/／·‧・–&＆]/u; // arrows, operators, slashes, dots, en dash
const NO_LINE_START = /[々〻ゝゞヽヾーぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶㇰ-ㇿ]/u;
// words (as ICU segments them) that belong to their neighbour, Traditional + Simplified
const LEANS_BACK = new Set([...'的了著过過嗎吗呢吧啊呀啦們们地得裡里中時时後后等性化度率式者完', // never start a line
  '起來', '起来', '下來', '下来', '出來', '出来', '進來', '进来', '回來', '回来', '上去', '下去', '進去', '进去', '出去', '回去']);
const LEANS_ON = new Set([...'更最很太越愈不沒没未非再又也都就才只還还已將将會会能要可並并而且把被讓让從从向對对用以在為为與与和跟給给每各某該该此這这那哪第一自同整全逐任']); // never end one
const COUNTED = /^[一二兩两三四五六七八九十百千萬万幾几每這这那哪某各該该整半多]一?[個个種种類类些篇條条件位張张層层次步隻只本台份項项點点句段組组列行道筆笔封首部座輛辆顆颗名塊块片頁页]$/u; // 一個 這種 每篇: lean on the noun

const attrsOf = (s) => new Map([...s.matchAll(/([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g)]
  .map((m) => [m[1].toLowerCase(), m[2] ?? m[3] ?? m[4] ?? '']));

// Walk the markup; return one record per innermost phrase element: its visible text, and for
// every UTF-16 unit of that text where it starts and ends in the source (-1 for separators).
export function phraseTargets(html) {
  const TAG = /<!--[\s\S]*?-->|<![^>]*>|<\?[^>]*>|<(\/?)([a-zA-Z][\w:-]*)((?:\s+[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*)\s*(\/?)>/y;
  const recs = [];
  const stack = []; // open elements: { name, off (hands-off subtree), rec (nearest phrase element) }
  const top = () => stack[stack.length - 1];
  const push = (r, ch, start, end) => { r.text += ch; for (let k = 0; k < ch.length; k++) { r.starts.push(start); r.ends.push(end); } };
  const text = (s, e) => {
    const t = top();
    if (!t?.rec || t.off) return;
    for (const m of html.slice(s, e).matchAll(/&#(\d+);?|&#x([0-9a-f]+);?|&([a-z][a-z0-9]*);|[\s\S]/giu)) {
      const ch = m[1] ? String.fromCodePoint(+m[1]) : m[2] ? String.fromCodePoint(parseInt(m[2], 16)) : m[3] ? ENTITY[m[3]] ?? '\uFFFC' : m[0];
      push(t.rec, ch, s + m.index, s + m.index + m[0].length);
    }
  };
  let i = 0;
  while (i < html.length) {
    const lt = html.indexOf('<', i);
    text(i, lt < 0 ? html.length : lt);
    if (lt < 0) break;
    TAG.lastIndex = lt;
    const m = TAG.exec(html);
    if (!m) { text(lt, lt + 1); i = lt + 1; continue; }
    i = TAG.lastIndex;
    if (!m[2]) continue; // comment, doctype
    const name = m[2].toLowerCase();
    const parent = top();
    if (m[1]) { // end tag: close it and anything left open inside it
      const k = stack.map((e) => e.name).lastIndexOf(name);
      if (k >= 0) stack.length = k;
      if (k >= 0 && BLOCK.has(name) && top()?.rec && !top().off) push(top().rec, '\n', -1, -1);
      continue;
    }
    const a = attrsOf(m[3]);
    const cls = new Set((a.get('class') || '').split(/\s+/));
    const off = !!parent?.off || HANDS_OFF.has(name) || cls.has('notes') || a.has('data-phrase');
    const inner = parent?.rec && !parent.off;
    if (inner && (cls.has('nw') || name === 'wbr')) for (const e of stack) if (e.rec) e.rec.manual = true;
    if (inner && (BLOCK.has(name) || cls.has('en'))) push(parent.rec, '\n', -1, -1); // .en: the subtitle line under an h3
    else if (inner && off) push(parent.rec, '\uFFFC', -1, -1); // an inline island (code, svg icon): no break beside it
    let rec = parent?.rec || null;
    if (!off && !cls.has('nw') && (PHRASE_TAGS.has(name) || PHRASE_CLASSES.some((c) => cls.has(c)))) {
      if (inner) parent.rec.nested = true;
      rec = { text: '', starts: [], ends: [], attrAt: i - 1 - m[4].length };
      recs.push(rec);
    }
    if (VOID.has(name) || m[4]) continue;
    stack.push({ name, off, rec });
    if (RAW_TEXT.has(name)) { // jump to the end tag; script/style text is never markup
      const close = new RegExp(`</${name}\\s*>`, 'ig');
      close.lastIndex = i;
      i = close.exec(html)?.index ?? html.length;
    }
  }
  return recs.filter((r) => !r.manual && !r.nested && /\p{Script=Han}|\p{Script=Hiragana}|\p{Script=Katakana}/u.test(r.text));
}

export function phraseBreaks(html, lang) {
  const recs = phraseTargets(html);
  if (!recs.length) return { html, model: null, elements: 0, breaks: 0, glue: 0 };
  const res = spawnSync('uv', ['run', '--quiet', '--script', PHRASE_PY], {
    input: JSON.stringify({ lang, texts: recs.map((r) => r.text) }), encoding: 'utf8', maxBuffer: 1 << 28, timeout: 180000,
  });
  if (res.error) throw new Error(res.error.code === 'ENOENT' ? '`uv` not found' : res.error.message);
  if (res.status !== 0) throw new Error((res.stderr || '').trim().split('\n').pop() || `phrase.py exited with ${res.status}`);
  const { model, breaks } = JSON.parse(res.stdout);
  let words;
  try { words = new Intl.Segmenter(lang, { granularity: 'word' }); } catch { words = new Intl.Segmenter('zh', { granularity: 'word' }); }
  const before = (s, k) => (k > 1 && /[\uDC00-\uDFFF]/.test(s[k - 1]) ? s.slice(k - 2, k) : s[k - 1]);
  const after = (s, k) => (k < s.length ? String.fromCodePoint(s.codePointAt(k)) : '');
  const word = /[\p{L}\p{Nd}]/u;
  const edits = []; // [source offset, text to insert, characters it replaces]
  let wbr = 0;
  let glue = 0;
  for (const [n, r] of recs.entries()) {
    const segs = [...words.segment(r.text)];
    const wordAt = new Map(segs.map((w) => [w.index, w.segment]));
    const wordTo = new Map(segs.map((w) => [w.index + w.segment.length, w.segment]));
    for (const k of breaks[n]) {
      const a = before(r.text, k);
      const b = after(r.text, k);
      if (!wordAt.has(k) || LEANS_ON.has(wordTo.get(k)) || COUNTED.test(wordTo.get(k)) || LEANS_BACK.has(wordAt.get(k))) continue;
      const w = wordAt.get(k);
      if ([...w].length === 1 && !/[\p{L}\p{N}]/u.test(r.text.slice(k + w.length).split('\n')[0])) continue; // no lone last character
      if (LETTER.test(a) && LETTER.test(b) && (CJK.test(a) || CJK.test(b)) && !NO_LINE_START.test(b)) { edits.push([r.ends[k - 1], '<wbr>', 0]); wbr++; }
    }
    for (let k = 1; k < r.text.length - 1; k++) {
      const c = r.text[k];
      const a = before(r.text, k);
      const b = after(r.text, k + 1);
      if (c === ' ' && html[r.starts[k]] === ' ' && r.ends[k] - r.starts[k] === 1
        && ((DIGIT.test(a) && CJK.test(b)) || (CJK.test(a) && DIGIT.test(b)))) {
        edits.push([r.starts[k], '&nbsp;', 1]);
        glue++;
      } else if (LINKER.test(c) && word.test(a) && word.test(b) && (CJK.test(a) || CJK.test(b))) {
        edits.push([r.starts[k], '&#8288;', 0], [r.ends[k], '&#8288;', 0]);
        glue++;
      }
    }
    edits.push([r.attrAt, ' data-phrase="auto"', 0]);
  }
  edits.sort((x, y) => x[0] - y[0] || x[2] - y[2]);
  let out = '';
  let last = 0;
  for (const [at, s, del] of edits) { out += html.slice(last, at) + s; last = at + del; }
  return { html: out + html.slice(last), model, elements: recs.length, breaks: wbr, glue };
}
