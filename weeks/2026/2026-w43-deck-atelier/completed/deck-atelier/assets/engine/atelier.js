/* ============================================================================
   deck-atelier · atelier.js
   Presentation runtime — no dependencies.

   Scaling · navigation · builds (data-step) · motion choreography · overview ·
   presenter console · in-browser text editing with save-back.

   Motion vocabulary (only when <html data-motion="on">):
     units          headings, paragraphs, figures… reveal in DOM order, staggered
     data-reveal    rise | soft | fade | mask | title | scale | none   (override)
     data-delay     extra ms before a unit reveals
     data-depth     parallax depth 0–1 (bg art ≈ .35, figures ≈ .6, text = 1)
     data-step      build order on click: 1, 2, 3…  (slide gets data-at="k")
     data-morph     shared element: same key on consecutive slides glides across
     data-draw      SVG stroke draws in (value = ms offset inside its unit)
     data-pop       SVG element scales/fades in (value = ms offset)
     data-fade      SVG element fades in (value = ms offset)
     data-count     number counts up to its value
     data-ambient   CSS loop while the slide is on screen (drift, breathe, wave…)
     data-transition  default | curtain | fade | none   (on the incoming slide)
   ========================================================================== */
(() => {
  'use strict';

  const W = 1920;
  const H = 1080;
  const root = document.documentElement;
  const deck = document.querySelector('.deck');
  if (!deck || window.atelier) return;

  const slides = [...deck.children].filter((n) => n.classList.contains('slide'));
  const N = slides.length;
  const params = new URLSearchParams(location.search);
  const PRESENTER = params.has('presenter');
  const reducedMQ = matchMedia('(prefers-reduced-motion: reduce)');

  const EASE = {
    out: 'cubic-bezier(0.16, 1, 0.3, 1)',
    soft: 'cubic-bezier(0.22, 1, 0.36, 1)',
    inOut: 'cubic-bezier(0.65, 0, 0.35, 1)',
    move: 'cubic-bezier(0.76, 0, 0.24, 1)',
    draw: 'cubic-bezier(0.37, 0, 0.63, 1)',
    in: 'cubic-bezier(0.4, 0.14, 1, 1)',
  };
  const T = { exit: 480, enter: 1150, stagger: 85, window: 1100, base: 320, morph: 1050, curtain: 1150, step: 90 };

  const $ = (sel, r = document) => r.querySelector(sel);
  const $$ = (sel, r = document) => [...r.querySelectorAll(sel)];
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const pad2 = (n) => String(n).padStart(2, '0');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  const make = (tag, cls, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    n.dataset.runtime = '';
    return n;
  };

  if (params.get('motion')) root.dataset.motion = params.get('motion') === 'off' ? 'off' : 'on';
  if (!root.dataset.motion) root.dataset.motion = 'on';
  if (params.get('theme')) root.dataset.theme = params.get('theme');
  if (!root.dataset.theme) root.dataset.theme = 'light';
  /* Style registry: display name, Google Fonts families, preferred theme.
     scripts/new_deck.mjs, set_style.mjs and snapshot.mjs read this block as JSON — keep it valid JSON. */
  const STYLE_REGISTRY = /*registry*/{
    "swiss": { "name": "Swiss 網格", "fonts": "family=Archivo:ital,wdth,wght@0,62..125,100..900;1,62..125,100..900&family=Noto+Sans+TC:wght@100..900" },
    "press": { "name": "Press 號外", "fonts": "family=Archivo:ital,wdth,wght@0,62..125,100..900;1,62..125,100..900&family=Noto+Sans+TC:wght@100..900" },
    "lab": { "name": "Lab 實驗室", "fonts": "family=Archivo:ital,wdth,wght@0,62..125,100..900;1,62..125,100..900&family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Noto+Sans+TC:wght@100..900" },
    "tokyo": { "name": "Tokyo 日式雜誌", "fonts": "family=Josefin+Sans:ital,wght@0,100..700;1,100..700&family=Noto+Sans+TC:wght@100..900&family=Noto+Serif+TC:wght@200..900" },
    "kinfolk": { "name": "Kinfolk 慢生活", "fonts": "family=Cormorant+Garamond:ital,wght@0,300..700;1,300..700&family=Jost:ital,wght@0,100..900;1,100..900&family=Noto+Sans+TC:wght@100..900&family=Noto+Serif+TC:wght@200..900" },
    "dopamine": { "name": "Dopamine 多巴胺", "fonts": "family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,200..800&family=Huninn&family=Noto+Sans+TC:wght@100..900" },
    "glitch": { "name": "Glitch 故障", "fonts": "family=Chakra+Petch:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Noto+Sans+TC:wght@100..900", "theme": "dark" },
    "geometric": { "name": "Geometric 幾何抽象", "fonts": "family=Jost:ital,wght@0,100..900;1,100..900&family=Noto+Sans+TC:wght@100..900" },
    "postmodern": { "name": "Postmodern 後現代", "fonts": "family=Syne:wght@400..800&family=Noto+Sans+TC:wght@100..900" },
    "riso": { "name": "Riso 孔版印刷", "fonts": "family=Rubik:ital,wght@0,300..900;1,300..900&family=Iansui&family=Noto+Sans+TC:wght@100..900" }
  }/*/registry*/;
  const STYLES = Object.keys(STYLE_REGISTRY);
  const authoredStyle = root.dataset.style || 'swiss';
  if (params.get('style')) root.dataset.style = params.get('style');
  if (!STYLE_REGISTRY[root.dataset.style]) root.dataset.style = 'swiss';
  const isDark = () => root.dataset.theme === 'dark' || root.dataset.theme === 'noir';
  const motionOn = () => root.dataset.motion !== 'off' && !reducedMQ.matches;

  let index = 0;
  let step = 0;
  let scale = 1;
  let current = null; // in-flight transition: { anims, cleanup }
  let syncing = false;
  let presenterWin = null;
  const splitEls = new Set();

  /* ── chapters + chrome ──────────────────────────────────────────────── */

  let chapter = null;
  slides.forEach((s) => {
    if ('chapter' in s.dataset) {
      chapter = s.dataset.chapter ? { n: s.dataset.chapter, title: s.dataset.chapterTitle || '' } : null;
    }
    s._chapter = chapter;
  });

  function buildChrome(s, i) {
    if (s.dataset.chrome === 'none') return;
    const ch = s._chapter;
    const tracker = s.dataset.tracker != null
      ? esc(s.dataset.tracker)
      : ch ? `<b>${esc(ch.n)}</b><span class="sep"></span>${esc(ch.title)}` : '';
    const ownSource = s.querySelector(':scope > .source');
    s.append(
      make('div', 'chrome chrome--top',
        `<span class="chrome__part chrome__chapter" data-key="chapter">${tracker}</span>` +
        `<span class="chrome__part chrome__title" data-key="title">${esc(deck.dataset.title || '')}</span>`),
      make('div', 'chrome chrome--bottom',
        `<span class="chrome__part chrome__source" data-key="source">${ownSource ? '' : esc(s.dataset.source || '')}</span>` +
        `<span class="chrome__part chrome__page" data-key="page"><b>${pad2(i + 1)}</b>&ensp;/&ensp;${pad2(N)}</span>`),
    );
  }

  /* ── units: what animates, in which order, how ─────────────────────── */

  const UNIT_SEL = [
    '.kicker', '.title', '.statement', '.lead', '.hero', '.display', '.source', '.note', '.takeaway', '.caption',
    '.cover__meta', '.cover__title .line', '.cover__subtitle', '.cover__foot',
    '.points > li', '.agenda > li', '.timeline > li', '.list > li', '.stats > *',
    '.stat', '.figure', '.table', '.quote', '.art',
    '.chapter__n', '.chapter__title', '.chapter__sub', '.closing__line',
    '[data-reveal]', '[data-morph]', '[data-step]', 'p', 'h3', 'h4', 'blockquote', 'figure',
  ].join(',');
  const EXPLICIT = '[data-reveal]:not([data-reveal="none"]), [data-morph], [data-step]';
  const SKIP = 'defs, style, script, title, desc, .notes, .chrome, [hidden]';

  function unitsOf(s) {
    if (s._units) return s._units;
    const cand = new Set($$(UNIT_SEL, s).filter((n) => !n.closest('.chrome, .notes')));
    const units = [];
    const take = (n) => { if (n.dataset.reveal !== 'none') units.push(n); };
    // Candidates are units; containers of candidates are descended; anything else
    // visible is a "loose block" unit. A unit holding an explicit unit (morph, step,
    // data-reveal) is exploded so the inner one can move on its own.
    const visit = (box) => {
      for (const c of box.children) {
        if (c.matches(SKIP)) continue;
        const inner = c.querySelector(EXPLICIT);
        if (cand.has(c)) (inner ? visit(c) : take(c));
        else if (c.querySelector(UNIT_SEL)) visit(c);
        else take(c);
      }
    };
    visit(s);
    s._units = units;
    return units;
  }

  const stepOf = (u) => +(u.closest('[data-step]')?.dataset.step || 0);
  const maxStep = (s) => (s._max ??= Math.max(0, ...$$('[data-step]', s).map((n) => +n.dataset.step || 0)));

  function unitType(u) {
    if (u.dataset.reveal) return u.dataset.reveal;
    if (u.matches('.title, .statement, .cover__subtitle, .quote, .chapter__title, .closing__line')) return 'title';
    if (u.matches('.cover__title .line, .hero, .display, .chapter__n')) return 'mask';
    if (u.matches('.kicker, .cover__meta, .source, .note, .caption, .cover__foot')) return 'fade';
    if (u instanceof SVGElement || u.matches('.figure, .art, .table') || u.querySelector('svg, img')) return 'soft';
    return 'rise';
  }

  function unitDepth(u) {
    if (u.dataset.depth) return +u.dataset.depth;
    if (u.matches('.art, [data-layer="bg"]')) return 0.35;
    if (u instanceof SVGElement || u.matches('.figure, .table') || u.querySelector('svg, img')) return 0.6;
    return 1;
  }

  /* ── text splitting for title reveals (restored right after) ───────── */

  const TOKEN = /[A-Za-z0-9À-ɏͰ-Ͽ'’\-.,:;!?%°&/]+|\s+|[\s\S]/gu;

  function split(el) {
    unsplit(el);
    el._orig = el.innerHTML;
    el._gen = (el._gen || 0) + 1;
    splitEls.add(el);
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentElement.closest('svg, .no-split, [data-count]') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    const texts = [];
    while (walker.nextNode()) texts.push(walker.currentNode);
    const spans = [];
    for (const t of texts) {
      const frag = document.createDocumentFragment();
      for (const [tok] of t.data.matchAll(TOKEN)) {
        if (/^\s+$/.test(tok)) { frag.append(tok); continue; }
        const sp = document.createElement('span');
        sp.className = 'u';
        sp.textContent = tok;
        frag.append(sp);
        spans.push(sp);
      }
      t.replaceWith(frag);
    }
    return { spans, gen: el._gen };
  }

  function unsplit(el, gen) {
    if (el._orig == null || (gen != null && gen !== el._gen)) return;
    el.innerHTML = el._orig;
    el._orig = null;
    splitEls.delete(el);
  }

  /* ── reveal primitives ─────────────────────────────────────────────── */

  function reveal(u, delay, dir = 1) {
    const type = unitType(u);
    const dy = Math.round(46 * unitDepth(u)) * (dir || 1);
    const o = (duration, easing = EASE.out) => ({ duration, delay, easing, fill: 'backwards' });
    const out = [];
    switch (type) {
      case 'none':
        break;
      case 'fade':
        out.push(u.animate([{ opacity: 0 }, { opacity: 1 }], o(1100, EASE.soft)));
        break;
      case 'soft':
        out.push(u.animate([{ opacity: 0, transform: `translate3d(0, ${dy}px, 0)` }, { opacity: 1, transform: 'none' }], o(1350)));
        break;
      case 'mask':
        out.push(u.animate([
          { transform: 'translate3d(0, 104%, 0)', clipPath: 'inset(-30% -6% 104% -6%)' },
          { transform: 'none', clipPath: 'inset(-30% -6% -30% -6%)' },
        ], o(1300)));
        break;
      case 'scale':
        out.push(u.animate([{ opacity: 0, transform: 'scale(1.06)' }, { opacity: 1, transform: 'none' }], o(1700)));
        break;
      case 'title': {
        const { spans, gen } = split(u);
        const stagger = clamp(700 / Math.max(spans.length, 1), 10, 38);
        const parts = [u.animate(
          [{ transform: `translate3d(0, ${Math.round(dy * 0.7)}px, 0)`, filter: 'blur(7px)' }, { transform: 'none', filter: 'blur(0px)' }],
          o(1300),
        )];
        spans.forEach((sp, k) => parts.push(sp.animate([{ opacity: 0 }, { opacity: 1 }],
          { duration: 780, delay: delay + 60 + k * stagger, easing: EASE.soft, fill: 'backwards' })));
        const done = () => unsplit(u, gen);
        Promise.all(parts.map((a) => a.finished)).then(done, done);
        out.push(...parts);
        break;
      }
      case 'rise':
      default:
        out.push(u.animate([
          { opacity: 0, transform: `translate3d(0, ${dy}px, 0)`, filter: 'blur(6px)' },
          { opacity: 1, transform: 'none', filter: 'blur(0px)' },
        ], o(T.enter)));
    }
    out.push(...choreoSVG(u, delay), ...countUp(u, delay));
    return out;
  }

  function choreoSVG(u, base) {
    const out = [];
    const nodes = $$('[data-draw], [data-pop], [data-fade]', u);
    if (u.matches('[data-draw], [data-pop], [data-fade]')) nodes.unshift(u);
    for (const n of nodes) {
      const off = (k) => +(n.getAttribute(k) || 0);
      if (n.hasAttribute('data-draw') && typeof n.getTotalLength === 'function') {
        const len = Math.ceil(n.getTotalLength());
        const dur = +(n.dataset.dur || clamp(len * 1.15, 520, 1900));
        out.push(n.animate([
          { strokeDasharray: `${len} ${len}`, strokeDashoffset: len },
          { strokeDasharray: `${len} ${len}`, strokeDashoffset: 0 },
        ], { duration: dur, delay: base + off('data-draw'), easing: EASE.draw, fill: 'backwards' }));
      } else if (n.hasAttribute('data-pop')) {
        out.push(n.animate([{ opacity: 0, transform: 'scale(0.82)' }, { opacity: 1, transform: 'none' }],
          { duration: 760, delay: base + off('data-pop'), easing: EASE.out, fill: 'backwards' }));
      } else if (n.hasAttribute('data-fade')) {
        out.push(n.animate([{ opacity: 0 }, { opacity: 1 }],
          { duration: +(n.dataset.dur || 900), delay: base + off('data-fade'), easing: EASE.soft, fill: 'backwards' }));
      }
    }
    return out;
  }

  function countUp(u, delay) {
    const nodes = $$('[data-count]', u);
    if (u.matches('[data-count]')) nodes.unshift(u);
    return nodes.map((n) => {
      const target = n.dataset.count;
      const to = parseFloat(target);
      const dec = (target.split('.')[1] || '').length;
      const dur = 1700;
      const a = n.animate([{ opacity: 1 }, { opacity: 1 }], { duration: dur, delay, fill: 'backwards' });
      const ease = (t) => 1 - Math.pow(1 - t, 4);
      const tick = () => {
        const t = a.currentTime == null ? dur + delay : a.currentTime;
        const p = clamp((t - delay) / dur, 0, 1);
        n.textContent = p >= 1 ? target : (to * ease(p)).toFixed(dec);
        if (a.playState === 'running' || a.playState === 'paused') requestAnimationFrame(tick);
        else n.textContent = target;
      };
      n.textContent = (0).toFixed(dec);
      requestAnimationFrame(tick);
      return a;
    });
  }

  /* ── transitions ───────────────────────────────────────────────────── */

  function settle() {
    if (!current) return;
    const t = current;
    t.anims.forEach((a) => { try { a.finish(); } catch { /* infinite or idle */ } });
    t.cleanup?.();
    current = null;
  }

  function track(anims, cleanup) {
    const t = { anims, done: false };
    t.cleanup = () => {
      if (t.done) return;
      t.done = true;
      cleanup?.();
      if (current === t) current = null;
    };
    current = t;
    Promise.all(anims.map((a) => a.finished.catch(() => {}))).then(t.cleanup);
    return t;
  }

  function applyStep(s, k) {
    $$('[data-step]', s).forEach((n) => n.classList.toggle('is-on', +n.dataset.step <= k));
    s.dataset.at = k;
  }

  function enterUnits(s, base, dir, upto) {
    const list = unitsOf(s).filter((u) => !u._morph && stepOf(u) <= upto);
    const gap = list.length > 1 ? Math.min(T.stagger, T.window / (list.length - 1)) : 0;
    return list.flatMap((u, k) => reveal(u, base + k * gap + (+u.dataset.delay || 0), dir));
  }

  function exitUnits(s, dir, upto) {
    return unitsOf(s)
      .filter((u) => !u._morph && stepOf(u) <= upto)
      .map((u) => u.animate([
        { opacity: 1, transform: 'none' },
        { opacity: 0, transform: `translate3d(0, ${-dir * Math.round(34 * unitDepth(u))}px, 0)` },
      ], { duration: T.exit, easing: EASE.in, fill: 'forwards' }));
  }

  function chromeSwap(from, to, dir) {
    const out = [];
    for (const b of $$('.chrome [data-key]', to)) {
      const a = $(`.chrome [data-key="${b.dataset.key}"]`, from);
      if (a && a.innerHTML === b.innerHTML) {
        out.push(a.animate([{ opacity: 0 }, { opacity: 0 }], { duration: 1, fill: 'forwards' }));
        continue;
      }
      if (a) {
        out.push(a.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: `translateY(${-10 * dir}px)` }],
          { duration: 360, easing: EASE.in, fill: 'forwards' }));
      }
      out.push(b.animate([{ opacity: 0, transform: `translateY(${12 * dir}px)` }, { opacity: 1, transform: 'none' }],
        { duration: 820, delay: 240, easing: EASE.out, fill: 'backwards' }));
    }
    return out;
  }

  function rectIn(el) {
    const r = el.getBoundingClientRect();
    const d = deck.getBoundingClientRect();
    return { x: (r.left - d.left) / scale, y: (r.top - d.top) / scale, w: r.width / scale, h: r.height / scale };
  }

  function morphPairs(from, to, upto) {
    const pairs = [];
    for (const b of $$('[data-morph]', to)) {
      if (stepOf(b) > upto) continue;
      const a = $(`[data-morph="${CSS.escape(b.dataset.morph)}"]`, from);
      if (!a || stepOf(a) > step) continue;
      pairs.push({ a, b, ra: rectIn(a), rb: rectIn(b) });
    }
    return pairs;
  }

  function morphAnims(pairs) {
    const out = [];
    for (const { a, b, ra, rb } of pairs) {
      if (!rb.w || !rb.h) continue;
      const stretch = b.hasAttribute('data-morph-stretch');
      let sx = ra.w / rb.w;
      let sy = ra.h / rb.h;
      if (!stretch) sx = sy = Math.sqrt(sx * sy);
      const dx = ra.x + ra.w / 2 - (rb.x + rb.w / 2);
      const dy = ra.y + ra.h / 2 - (rb.y + rb.h / 2);
      const same = a.textContent.trim() === b.textContent.trim() && a.className === b.className;
      const o = { duration: T.morph, easing: EASE.move };
      out.push(b.animate(same
        ? [{ transformOrigin: '50% 50%', transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})` }, { transformOrigin: '50% 50%', transform: 'none' }]
        : [{ transformOrigin: '50% 50%', transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`, opacity: 0 },
          { opacity: 1, offset: 0.55 },
          { transformOrigin: '50% 50%', transform: 'none', opacity: 1 }],
      { ...o, fill: 'backwards' }));
      out.push(a.animate(same
        ? [{ opacity: 0 }, { opacity: 0 }]
        : [{ transformOrigin: '50% 50%', transform: 'none', opacity: 1 },
          { opacity: 0, offset: 0.45 },
          { transformOrigin: '50% 50%', transform: `translate(${-dx}px, ${-dy}px) scale(${1 / sx}, ${1 / sy})`, opacity: 0 }],
      { ...o, fill: 'forwards' }));
    }
    return out;
  }

  const curtainIn = (s, dir) => s.animate(
    [{ clipPath: dir > 0 ? 'inset(100% 0 0 0)' : 'inset(0 0 100% 0)' }, { clipPath: 'inset(0 0 0 0)' }],
    { duration: T.curtain, easing: EASE.move, fill: 'backwards' },
  );

  function go(target, opts = {}) {
    target = clamp(target | 0, 0, N - 1);
    const to = slides[target];
    if (opts.step === 'all') opts.step = maxStep(to);
    if (target === index && !opts.force) {
      if (opts.step != null && opts.step !== step) stepTo(clamp(opts.step, 0, maxStep(to)), opts);
      return;
    }
    settle();
    const from = slides[index];
    const fromStep = step;
    const dir = target >= index ? 1 : -1;
    const toStep = !motionOn() ? maxStep(to) : opts.step != null ? clamp(opts.step, 0, maxStep(to)) : dir < 0 ? maxStep(to) : 0;
    const animate = motionOn() && !opts.instant && from !== to && to.dataset.transition !== 'none'
      && !root.classList.contains('is-overview');

    if (!animate) {
      from.classList.remove('is-active', 'is-leaving', 'is-entering');
      to.classList.add('is-active');
      index = target;
      step = toStep;
      applyStep(to, step);
      if (reducedMQ.matches && root.dataset.motion !== 'off' && !opts.instant && from !== to) {
        track([to.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: 'ease-out', fill: 'backwards' })]);
      }
      announce();
      return;
    }

    const pairs = morphPairs(from, to, toStep);
    pairs.forEach((p) => { p.a._morph = p.b._morph = true; });
    applyStep(to, toStep);
    from.classList.remove('is-active');
    from.classList.add('is-leaving');
    to.classList.add('is-active');
    const toneChange = (from.dataset.tone || '') !== (to.dataset.tone || '');
    const curtain = to.dataset.transition === 'curtain' || (toneChange && to.dataset.transition !== 'fade');
    if (!curtain) to.classList.add('is-entering');

    const anims = [...exitUnits(from, dir, fromStep), ...chromeSwap(from, to, dir)];
    let base = T.base;
    if (curtain) { anims.push(curtainIn(to, dir)); base = 400; }
    anims.push(...morphAnims(pairs), ...enterUnits(to, base, dir, toStep));

    index = target;
    step = toStep;
    track(anims, () => {
      from.classList.remove('is-leaving');
      to.classList.remove('is-entering');
      anims.forEach((a) => a.cancel());
      pairs.forEach((p) => { p.a._morph = p.b._morph = false; });
    });
    announce();
  }

  function stepTo(k) {
    settle();
    const s = slides[index];
    const was = step;
    if (k === was) return;
    const anims = [];
    if (k > was) {
      applyStep(s, k);
      unitsOf(s).filter((u) => { const st = stepOf(u); return st > was && st <= k; })
        .forEach((u, i) => anims.push(...reveal(u, i * T.step, 1)));
      step = k;
      track(anims);
    } else {
      s.dataset.at = k;
      unitsOf(s).filter((u) => { const st = stepOf(u); return st > k && st <= was; })
        .forEach((u) => anims.push(u.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 320, easing: EASE.in, fill: 'forwards' })));
      step = k;
      track(anims, () => { applyStep(s, k); anims.forEach((a) => a.cancel()); });
    }
    announce();
  }

  function next() {
    if (motionOn() && step < maxStep(slides[index])) return stepTo(step + 1);
    if (index < N - 1) go(index + 1);
  }

  function prev() {
    if (motionOn() && step > 0) return stepTo(step - 1);
    if (index > 0) go(index - 1);
  }

  /* ── fit, overview ─────────────────────────────────────────────────── */

  function fit() {
    if (root.classList.contains('is-overview')) return layoutOverview();
    const box = PRESENTER ? $('.presenter__current') : null;
    const w = box ? box.clientWidth : innerWidth;
    const h = box ? box.clientHeight : innerHeight;
    scale = Math.min(w / W, h / H);
    deck.style.setProperty('--scale', scale);
    if (PRESENTER) {
      deck.style.left = `${(w - W * scale) / 2}px`;
      deck.style.top = `${(h - H * scale) / 2}px`;
      fitNext();
    }
  }

  function layoutOverview() {
    const cols = N <= 9 ? 3 : N <= 16 ? 4 : N <= 25 ? 5 : 6;
    const padX = 64;
    const gap = 36;
    const w = (innerWidth - padX * 2 - gap * (cols - 1)) / cols;
    const sc = w / W;
    const h = H * sc;
    slides.forEach((s, i) => {
      const c = i % cols;
      const r = Math.floor(i / cols);
      s.style.transform = `translate(${padX + c * (w + gap)}px, ${padX + r * (h + gap)}px) scale(${sc})`;
      s.classList.toggle('is-current', i === index);
    });
    deck.style.height = `${padX * 2 + Math.ceil(N / cols) * (h + gap)}px`;
  }

  function setOverview(on) {
    settle();
    root.classList.toggle('is-overview', on);
    if (on) {
      layoutOverview();
      $$('[data-step]', deck).forEach((n) => n.classList.add('is-on'));
      slides[index].scrollIntoView?.({ block: 'center' });
    } else {
      slides.forEach((s) => { s.style.transform = ''; s.classList.remove('is-current'); if (!s.getAttribute('style')) s.removeAttribute('style'); });
      deck.style.height = '';
      applyStep(slides[index], step);
      fit();
    }
  }

  /* ── HUD, help, blackout ───────────────────────────────────────────── */

  let hud;
  let hudTimer;
  function toast(html, ms = 1600) {
    if (!hud) return;
    hud.innerHTML = html;
    hud.classList.add('is-shown');
    clearTimeout(hudTimer);
    hudTimer = setTimeout(() => hud.classList.remove('is-shown'), ms);
  }

  let help;
  function toggleHelp(force) {
    if (!help) {
      help = make('div', 'atelier-help', `<div class="atelier-help__card"><h2>快捷鍵 · Shortcuts</h2><dl>
        <dt><kbd>→</kbd> <kbd>Space</kbd></dt><dd>下一步／下一頁（簡報筆的翻頁鍵也可以）</dd>
        <dt><kbd>←</kbd> <kbd>PgUp</kbd></dt><dd>上一步／上一頁</dd>
        <dt><kbd>數字</kbd> <kbd>Enter</kbd></dt><dd>跳到指定頁</dd>
        <dt><kbd>G</kbd> <kbd>Esc</kbd></dt><dd>總覽所有頁面</dd>
        <dt><kbd>F</kbd></dt><dd>全螢幕</dd>
        <dt><kbd>S</kbd></dt><dd>講者模式（講稿、下一頁、計時）</dd>
        <dt><kbd>M</kbd></dt><dd>動態效果 開／關</dd>
        <dt><kbd>T</kbd></dt><dd>淺色／深色</dd>
        <dt><kbd>Y</kbd> <kbd>⇧Y</kbd></dt><dd>切換風格（10 種，下一個／上一個；預覽用，不改檔案）</dd>
        <dt><kbd>E</kbd></dt><dd>編輯文字，<kbd>⌘</kbd><kbd>S</kbd> 儲存</dd>
        <dt><kbd>B</kbd></dt><dd>黑屏暫停</dd>
      </dl></div>`);
      help.addEventListener('click', () => toggleHelp(false));
      document.body.append(help);
      help.getBoundingClientRect();
    }
    help.classList.toggle('is-shown', force ?? !help.classList.contains('is-shown'));
  }

  let black;
  const toggleBlack = () => black?.classList.toggle('is-shown');

  /* ── theme, motion, fullscreen ─────────────────────────────────────── */

  function setTheme(name) {
    const apply = () => { root.dataset.theme = name; };
    if (document.startViewTransition && motionOn()) document.startViewTransition(apply);
    else apply();
    toast(`主題 · ${isDark() ? '深色' : '淺色'}`);
  }

  // A style's typefaces: the deck's own come from its <link data-fonts> (or the build's embedded
  // subsets); any other style previewed with Y or ?style= fetches its families from Google Fonts.
  const fontLoads = {};
  function ensureFonts(name) {
    const spec = STYLE_REGISTRY[name]?.fonts;
    if (!spec) return Promise.resolve();
    const families = [...spec.matchAll(/family=([^:&]+)/g)].map((m) => decodeURIComponent(m[1].replace(/\+/g, ' ')));
    const have = new Set([...document.fonts].map((f) => f.family.replace(/["']/g, '')));
    if (families.every((f) => have.has(f))) return Promise.resolve();
    if (!fontLoads[name]) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = `https://fonts.googleapis.com/css2?${spec}&display=swap`;
      link.dataset.styleFonts = name;
      fontLoads[name] = new Promise((res) => { link.onload = link.onerror = res; setTimeout(res, 5000); })
        .then(() => Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 3000))]));
      document.head.append(link);
    }
    return fontLoads[name];
  }

  function setStyle(name) {
    if (!STYLE_REGISTRY[name]) return;
    ensureFonts(name);
    const apply = () => { root.dataset.style = name; };
    if (document.startViewTransition && motionOn()) document.startViewTransition(apply);
    else apply();
    const k = STYLES.indexOf(name) + 1;
    const hint = STYLE_REGISTRY[name].theme === 'dark' && !isDark() ? '　按 <kbd>T</kbd> 看深色（這個風格的主場）' : '';
    toast(`風格 ${k}/${STYLES.length} · ${STYLE_REGISTRY[name].name}${name === authoredStyle ? '' : '（預覽）'}${hint}`);
  }

  function setMotion(on, opts = {}) {
    settle();
    root.dataset.motion = on ? 'on' : 'off';
    step = maxStep(slides[index]);
    applyStep(slides[index], step);
    if (!opts.quiet) toast(on ? '動態 · 開' : '動態 · 關（靜態簡報）');
    announce();
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else root.requestFullscreen?.().catch(() => {});
  }

  /* ── editing + save ────────────────────────────────────────────────── */

  const EDITABLE = [
    '.kicker', '.title', '.statement', '.lead', '.takeaway', '.note', '.source', '.caption', 'figcaption',
    '.cover__meta > span', '.cover__title .line', '.cover__subtitle', '.cover__foot > span',
    '.chapter__title', '.chapter__sub', '.closing__line', '.quote', 'h3', 'p', '.list > li', '.stat__label',
    '[data-count]', 'td', 'th', '.when', '.what', '.desc', '.token', '.chip', '.label',
  ].join(',');

  function restoreSplits() { [...splitEls].forEach((el) => unsplit(el)); }

  // build.mjs adds phrase breaks (<wbr> + data-phrase) for the text as built. Once an element's
  // text is edited they would be stale, so it falls back to plain wrapping and saves without them.
  function unphrase(n) {
    for (const h of [n.closest('[data-phrase]'), ...n.querySelectorAll('[data-phrase]')]) {
      if (!h) continue;
      h.removeAttribute('data-phrase');
      h.querySelectorAll('wbr').forEach((w) => w.remove());
    }
  }

  function setEditing(on) {
    settle();
    root.classList.toggle('is-editing', on);
    if (on) {
      restoreSplits();
      $$(EDITABLE, deck).forEach((n) => {
        if (n.closest('svg, .chrome, .notes') || n.querySelector(EDITABLE)) return;
        n.contentEditable = 'true';
        n.spellcheck = false;
      });
      toast('編輯模式 · 點文字直接修改　<kbd>⌘</kbd><kbd>S</kbd> 儲存　<kbd>E</kbd> 結束', 4200);
    } else {
      $$('[contenteditable]', deck).forEach((n) => { n.removeAttribute('contenteditable'); n.removeAttribute('spellcheck'); });
      $$('[data-count]', deck).forEach((n) => { n.dataset.count = n.textContent.trim(); });
      slides.forEach((s) => { s._units = null; });
      toast('結束編輯');
    }
  }

  function serialize() {
    restoreSplits();
    $$('[data-count]', deck).forEach((n) => { n.textContent = n.dataset.count; });
    const doc = root.cloneNode(true);
    doc.querySelectorAll('[data-runtime]').forEach((n) => n.remove());
    doc.querySelectorAll('[contenteditable]').forEach((n) => { n.removeAttribute('contenteditable'); n.removeAttribute('spellcheck'); });
    doc.querySelectorAll('.slide').forEach((s) => {
      s.classList.remove('is-active', 'is-leaving', 'is-entering', 'is-current');
      s.removeAttribute('data-at');
      s.style.transform = '';
      if (!s.getAttribute('style')) s.removeAttribute('style');
    });
    doc.querySelectorAll('[data-step]').forEach((n) => n.classList.remove('is-on'));
    doc.querySelectorAll('[class=""]').forEach((n) => n.removeAttribute('class'));
    doc.classList.remove('is-overview', 'is-editing', 'is-booting');
    if (!doc.getAttribute('class')) doc.removeAttribute('class');
    doc.removeAttribute('data-mode');
    const d = doc.querySelector('.deck');
    d?.removeAttribute('style');
    // the presenter view moves the deck; put it back where the body expects it
    return '<!doctype html>\n' + doc.outerHTML;
  }

  async function save() {
    const html = serialize();
    const name = decodeURIComponent(location.pathname.split('/').pop() || 'deck.html');
    if (window.showSaveFilePicker) {
      try {
        const handle = await window.showSaveFilePicker({ suggestedName: name, types: [{ description: 'HTML', accept: { 'text/html': ['.html'] } }] });
        const w = await handle.createWritable();
        await w.write(html);
        await w.close();
        toast('已儲存 · Saved');
        return;
      } catch (e) {
        if (e.name === 'AbortError') return;
      }
    }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast('已下載修改後的檔案');
  }

  /* ── presenter console ─────────────────────────────────────────────── */

  let t0 = Date.now();
  function buildPresenter() {
    root.dataset.mode = 'presenter';
    const ui = make('div', 'presenter', `
      <div class="presenter__current"><span class="presenter__label">現在 · Now</span></div>
      <div class="presenter__side">
        <div class="presenter__next"><span class="presenter__label">下一頁 · Next</span><div class="presenter__frame"></div></div>
        <div class="presenter__notes"></div>
      </div>
      <div class="presenter__bar"><b class="p-pos"></b><span class="p-step"></span><span class="timer">00:00</span><span class="p-clock"></span>
        <span class="hint">← → 翻頁　R 重設計時　視窗可拖到筆電螢幕</span></div>`);
    document.body.append(ui);
    $('.presenter__current', ui).append(deck);
    setInterval(() => {
      const s = Math.floor((Date.now() - t0) / 1000);
      $('.timer', ui).textContent = `${pad2(Math.floor(s / 60))}:${pad2(s % 60)}`;
      $('.p-clock', ui).textContent = new Date().toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', hour12: false });
    }, 500);
  }

  function fitNext() {
    const box = $('.presenter__next');
    const frame = $('.presenter__frame');
    if (!box || !frame) return;
    frame.style.transform = `scale(${Math.min(box.clientWidth / W, box.clientHeight / H)})`;
  }

  function updatePresenter() {
    const frame = $('.presenter__frame');
    if (!frame) return;
    frame.replaceChildren();
    const nx = slides[index + 1];
    if (nx) {
      const c = nx.cloneNode(true);
      c.classList.remove('is-leaving', 'is-entering');
      c.classList.add('is-active');
      $$('[data-step]', c).forEach((n) => n.classList.add('is-on'));
      $$('[id]', c).forEach((n) => n.removeAttribute('id'));
      frame.append(c);
    }
    $('.presenter__notes').innerHTML = $('.notes', slides[index])?.innerHTML || '';
    $('.p-pos').textContent = `${pad2(index + 1)} / ${pad2(N)}`;
    const ms = maxStep(slides[index]);
    $('.p-step').textContent = ms && motionOn() ? `步驟 ${step} / ${ms}` : '';
    fitNext();
  }

  function openPresenter() {
    if (PRESENTER) return;
    const url = location.href.split('#')[0].split('?')[0] + '?presenter' + (root.dataset.motion === 'off' ? '&motion=off' : '') + `&style=${root.dataset.style}&theme=${root.dataset.theme}#${index + 1}`;
    presenterWin = window.open(url, 'atelier-presenter', 'width=1440,height=900');
    if (!presenterWin) toast('瀏覽器擋下了彈出視窗，請允許後再按 S');
  }

  function post(msg) {
    if (syncing) return;
    for (const w of [presenterWin, window.opener]) {
      try { if (w && !w.closed) w.postMessage(msg, '*'); } catch { /* cross-window guard */ }
    }
  }

  addEventListener('message', (e) => {
    const m = e.data;
    if (!m || typeof m !== 'object' || !m.atelier) return;
    if (m.atelier === 'hello') {
      if (!presenterWin && e.source !== window) presenterWin = e.source;
      post({ atelier: 'state', index, step });
      return;
    }
    if (!presenterWin && !PRESENTER && e.source && e.source !== window) presenterWin = e.source;
    if (m.atelier === 'state' && (m.index !== index || m.step !== step)) {
      syncing = true;
      go(m.index, { step: m.step });
      syncing = false;
    }
  });

  /* ── bookkeeping ───────────────────────────────────────────────────── */

  let progress;
  function announce() {
    const h = `#${index + 1}`;
    if (location.hash !== h) history.replaceState(null, '', h);
    progress?.style.setProperty('--progress', (index + 1) / N);
    if (root.classList.contains('is-overview')) slides.forEach((s, i) => s.classList.toggle('is-current', i === index));
    post({ atelier: 'state', index, step });
    if (PRESENTER) updatePresenter();
  }

  const hashIndex = () => {
    const m = location.hash.match(/(\d+)/);
    return m ? clamp(+m[1] - 1, 0, N - 1) : null;
  };

  /* ── input ─────────────────────────────────────────────────────────── */

  let numBuf = '';
  let numTimer;

  addEventListener('keydown', (e) => {
    if (e.defaultPrevented || e.isComposing) return;
    const editing = root.classList.contains('is-editing');
    if (editing && (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); return; }
    if (editing && e.target.closest?.('[contenteditable="true"]')) {
      if (e.key === 'Escape') e.target.blur();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if (/^\d$/.test(k)) {
      numBuf += k;
      clearTimeout(numTimer);
      numTimer = setTimeout(() => { numBuf = ''; }, 1600);
      toast(`跳到第 ${numBuf} 頁 · Enter`);
      return;
    }
    switch (k) {
      case 'Enter':
        if (numBuf) { go(+numBuf - 1, { step: 0 }); numBuf = ''; break; }
        next();
        break;
      case 'ArrowRight': case 'ArrowDown': case 'PageDown': case 'n': case 'N':
        next();
        break;
      case ' ':
        e.shiftKey ? prev() : next();
        break;
      case 'ArrowLeft': case 'ArrowUp': case 'PageUp': case 'Backspace': case 'p': case 'P':
        prev();
        break;
      case 'Home': go(0); break;
      case 'End': go(N - 1); break;
      case 'g': case 'G': setOverview(!root.classList.contains('is-overview')); break;
      case 'Escape':
        if (help?.classList.contains('is-shown')) toggleHelp(false);
        else if (black?.classList.contains('is-shown')) toggleBlack();
        else setOverview(!root.classList.contains('is-overview'));
        break;
      case 'f': case 'F': toggleFullscreen(); break;
      case 's': case 'S': openPresenter(); break;
      case 't': case 'T': setTheme(isDark() ? 'light' : 'dark'); break;
      case 'y': case 'Y': {
        const k = STYLES.indexOf(root.dataset.style);
        setStyle(STYLES[(k + (e.shiftKey ? -1 : 1) + STYLES.length) % STYLES.length]);
        break;
      }
      case 'm': case 'M': setMotion(root.dataset.motion === 'off'); break;
      case 'e': case 'E': if (!PRESENTER) setEditing(!editing); break;
      case 'b': case 'B': case '.': toggleBlack(); break;
      case 'r': case 'R': if (PRESENTER) { t0 = Date.now(); toast('計時重設'); } break;
      case '?': case 'h': case 'H': toggleHelp(); break;
      default: return;
    }
    e.preventDefault();
  });

  deck.addEventListener('click', (e) => {
    if (root.classList.contains('is-overview')) {
      const s = e.target.closest('.slide');
      if (s) { const i = slides.indexOf(s); setOverview(false); go(i, { step: 'all', instant: true }); }
      return;
    }
    if (PRESENTER || root.classList.contains('is-editing')) return;
    if (e.target.closest('a, button, input, textarea, select, [contenteditable="true"]')) return;
    if (getSelection()?.toString()) return;
    const r = deck.getBoundingClientRect();
    if (e.clientX - r.left < r.width * 0.25) prev();
    else next();
  });

  // before the first change lands (composition start covers IME input of Chinese)
  for (const type of ['compositionstart', 'beforeinput', 'input']) {
    deck.addEventListener(type, (e) => { const n = e.target.closest?.('[contenteditable="true"]'); if (n) unphrase(n); });
  }

  let touch = null;
  addEventListener('touchstart', (e) => { const t = e.changedTouches[0]; touch = { x: t.clientX, y: t.clientY }; }, { passive: true });
  addEventListener('touchend', (e) => {
    if (!touch) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - touch.x;
    const dy = t.clientY - touch.y;
    touch = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.4) (dx < 0 ? next() : prev());
  });

  addEventListener('resize', fit);
  addEventListener('hashchange', () => { const i = hashIndex(); if (i != null && i !== index) go(i); });
  addEventListener('beforeprint', () => { settle(); restoreSplits(); });
  reducedMQ.addEventListener?.('change', () => setMotion(root.dataset.motion !== 'off'));

  /* ── boot ──────────────────────────────────────────────────────────── */

  slides.forEach(buildChrome);
  progress = make('div', 'progress');
  hud = make('div', 'atelier-hud');
  black = make('div', 'atelier-black');
  document.body.append(progress, hud, black);
  if (PRESENTER) buildPresenter();

  index = hashIndex() ?? 0;
  root.classList.add('is-booting');

  let readyResolve;
  const ready = new Promise((r) => { readyResolve = r; });
  const start = () => {
    root.classList.remove('is-booting');
    fit();
    slides.forEach((s, i) => s.classList.toggle('is-active', i === index));
    step = motionOn() ? 0 : maxStep(slides[index]);
    applyStep(slides[index], step);
    if (motionOn()) track(enterUnits(slides[index], 280, 1, step));
    announce();
    if (PRESENTER && window.opener) window.opener.postMessage({ atelier: 'hello' }, '*');
    if (!PRESENTER && !params.has('quiet')) setTimeout(() => toast('按 <kbd>?</kbd> 看快捷鍵　<kbd>S</kbd> 講者模式', 2600), 1600);
    readyResolve(true);
  };
  fit();
  // Embedded (bundled) fonts are cheap data: URIs — load every face up front so print,
  // overview and the presenter console never fall back to a system font.
  if (document.querySelector('style[data-fonts-embedded]')) document.fonts.forEach((f) => f.load().catch(() => {}));
  // A style previewed through ?style= waits for its own typefaces (fetched online) before the first reveal.
  const previewing = root.dataset.style !== authoredStyle;
  Promise.race([previewing ? ensureFonts(root.dataset.style) : document.fonts?.ready, new Promise((r) => setTimeout(r, previewing ? 6000 : 2500))])
    .then(() => requestAnimationFrame(start));

  /* ── public API (used by scripts/snapshot.mjs and the console) ─────── */

  window.atelier = {
    go: (i, o) => go(i, o),
    next,
    prev,
    settle,
    get index() { return index; },
    get step() { return step; },
    get count() { return N; },
    maxStep: (i = index) => maxStep(slides[i]),
    setMotion,
    setTheme,
    setStyle,
    styles: STYLE_REGISTRY,
    ready,
    overview: setOverview,
    serialize,
    freezeAt(ms) { document.getAnimations().forEach((a) => { a.pause(); a.currentTime = ms; }); },
    resume() { document.getAnimations().forEach((a) => a.play()); },
  };
})();
