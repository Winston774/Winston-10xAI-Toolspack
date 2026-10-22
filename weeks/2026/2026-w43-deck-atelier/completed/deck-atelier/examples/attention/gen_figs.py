"""Generate the computed SVG figures for decks/attention/deck.html (fills <!--gen:x--> regions)."""
import math
import random
import re
import sys
from pathlib import Path

DECK = Path(sys.argv[1])
random.seed(7)
f = lambda v: f"{v:.1f}".rstrip("0").rstrip(".")


def arc(x1, x2, y, ry_ratio, cap):
    a, b = min(x1, x2), max(x1, x2)
    rx = (b - a) / 2
    ry = min(rx * ry_ratio, cap)
    return f"M{f(a)} {f(y)} A {f(rx)} {f(ry)} 0 0 1 {f(b)} {f(y)}"


# ── cover: an attention constellation, its → Law ──────────────────────────
def cover():
    y = 288
    xs = [16 + i * 97.5 for i in range(9)]
    focal, law, app = 6, 1, 7
    w = {0: .04, 1: .59, 2: .02, 3: .02, 4: .015, 5: .05, 7: .17, 8: .02}
    web = [(0, 2), (0, 4), (2, 5), (3, 8), (1, 4), (4, 8), (2, 8), (0, 7), (3, 5), (5, 8), (1, 3), (6, 8)]
    out = ['<g class="line-faint">']
    for k, (i, j) in enumerate(web):
        out.append(f'<path d="{arc(xs[i], xs[j], y, .78, 262)}" data-draw="{k * 45}" data-ambient="breathe" '
                   f'style="animation-delay:-{k * 1.3:.1f}s; --breathe-from:.25"/>')
    out.append("</g>")
    order = sorted(w, key=lambda j: w[j])
    for k, j in enumerate(order):
        if j == law:
            cls, sw, op = "line-accent", 2.4, 1
        elif j == app:
            cls, sw, op = "line", 1.4, .8
        else:
            cls, sw, op = "line-soft", 1, .7
        out.append(f'<path class="{cls}" d="{arc(xs[focal], xs[j], y, 1.0, 268)}" style="stroke-width:{sw}; opacity:{op}" '
                   f'data-draw="{600 + k * 90}"/>')
    for i, x in enumerate(xs):
        if i == focal:
            out.append(f'<circle class="fill-accent" cx="{f(x)}" cy="{y}" r="6.5" data-pop="{500}"/>')
        elif i == law:
            out.append(f'<circle class="fill-ink" cx="{f(x)}" cy="{y}" r="6.5" data-pop="{1400}"/>')
        else:
            out.append(f'<circle class="fill-ink2" cx="{f(x)}" cy="{y}" r="3.6" data-pop="{80 * i}"/>')
    out.append(f'<text x="{f(xs[law])}" y="318" text-anchor="middle" class="t-display t-muted" font-size="22" font-style="italic" data-fade="1600">Law</text>')
    out.append(f'<text x="{f(xs[focal])}" y="318" text-anchor="middle" class="t-display t-accent" font-size="22" font-style="italic" data-fade="700">its</text>')
    return "\n".join(out)


# ── statement slide: every word sees every word ───────────────────────────
def network():
    y = 206
    xs = [32 + i * 200 for i in range(9)]
    out = ['<g class="line-soft">']
    k = 0
    for i in range(9):
        for j in range(i + 1, 9):
            span = j - i
            op = max(.18, .62 - span * .055)
            out.append(f'<path d="{arc(xs[i], xs[j], y, .42, 196)}" style="opacity:{op:.2f}; animation-delay:-{(k * .9) % 7:.1f}s; --breathe-from:.35" '
                       f'data-ambient="breathe" data-draw="{k * 28}"/>')
            k += 1
    out.append("</g>")
    out.append(f'<path class="line-accent" d="{arc(xs[1], xs[7], y, .42, 196)}" data-draw="1150"/>')
    for i, x in enumerate(xs):
        cls = "fill-accent" if i in (1, 7) else "fill-ink2"
        out.append(f'<circle class="{cls}" cx="{x}" cy="{y}" r="{5.5 if i in (1, 7) else 4}" data-pop="{60 * i}"/>')
    return "\n".join(out)


# ── slide 7: arcs from "its", weights hanging below the words ─────────────
def its():
    tokens = [("The", 95, .04), ("Law", 214, .59), ("will", 329, .015), ("never", 459, .02), ("be", 580, .015),
              ("perfect,", 712, .05), ("but", 863, .015), ("its", 967, None), ("application", 1142, .17),
              ("should", 1353, .03), ("be", 1484, .01), ("just", 1589, .02)]
    fx, base_y, bar_y, bar_max, top = 967, 220, 322, 76, .59
    out = [f'<path class="axis" d="M40 {bar_y} H1624" data-draw="0"/>']
    arcs, bars = [], []
    for k, (t, x, w) in enumerate(tokens):
        if w is None:
            continue
        r = w / top
        if t == "Law":
            cls, sw = "line-accent", 5.2
        elif t == "application":
            cls, sw = "line", 2.2
        else:
            cls, sw = "line-soft", 1.1 + 1.6 * r
        op = 1 if t in ("Law", "application") else .55 + .4 * r
        d = arc(fx, x, base_y, .6, 196)
        delay = 300 + int((1 - r) * 0) + k * 40 if t not in ("Law", "application") else (1000 if t == "Law" else 820)
        extra = ' data-ambient="pulse" style="animation-delay:2.4s; stroke-width:5.2"' if False else f' style="stroke-width:{sw:.1f}; opacity:{op:.2f}"'
        arcs.append((r, f'<path class="{cls}" d="{d}"{extra} data-draw="{delay}"/>'))
        h = max(3, bar_max * r)
        fill = "fill-accent" if t == "Law" else "fill-ink2" if t == "application" else "fill-muted"
        bars.append(f'<path class="{fill}" d="M{x - 6} {bar_y + 1} H{x + 6} V{bar_y + h - 4:.1f} Q{x + 6} {bar_y + h:.1f} {x + 2} {bar_y + h:.1f} '
                    f'H{x - 2} Q{x - 6} {bar_y + h:.1f} {x - 6} {bar_y + h - 4:.1f} Z" data-pop="{1300 + k * 30}"><title>{t} · {round(w * 100)}%</title></path>')
    arcs.sort(key=lambda a: a[0])
    out += [a for _, a in arcs]
    out += bars
    out.append(f'<text x="214" y="{bar_y + bar_max + 34}" text-anchor="middle" class="t-display t-ink" font-size="34" data-fade="1700">59%</text>')
    out.append(f'<text x="1142" y="{bar_y + round(bar_max * .17 / .59) + 34}" text-anchor="middle" class="t-display t-ink" font-size="30" data-fade="1700">17%</text>')
    out.append(f'<circle class="fill-accent" cx="{fx}" cy="{base_y}" r="5" data-pop="250"/>')
    return "\n".join(out)


# ── slide 10: eight heads, eight patterns ─────────────────────────────────
def heads():
    n, cell, step = 8, 12, 14
    pats = []
    def mat(fn):
        return [[max(0.0, min(1.0, fn(r, c))) for c in range(n)] for r in range(n)]
    pats.append(("前一個字", mat(lambda r, c: .88 if c == max(r - 1, 0) else .05)))
    pats.append(("後一個字", mat(lambda r, c: .88 if c == min(r + 1, n - 1) else .05)))
    pats.append(("自己", mat(lambda r, c: .9 if c == r else .06)))
    pats.append(("句首", mat(lambda r, c: .74 if c == 0 else .07 + .04 * random.random())))
    coref = mat(lambda r, c: .22 if c == r else .04)
    coref[6][1], coref[7][1], coref[6][6] = .95, .5, .1
    pats.append(("指代", coref))
    pats.append(("廣泛", mat(lambda r, c: .16 + .22 * random.random())))
    pats.append(("鄰近", mat(lambda r, c: .58 if abs(r - c) <= 1 else .04)))
    pats.append(("遠距", mat(lambda r, c: (.45 + .4 * random.random()) if abs(r - c) >= 5 else .05)))
    out = []
    for i, (role, m) in enumerate(pats):
        x0, y0 = 10 + i * 138, 70
        key = i == 4
        out.append(f'<g data-pop="{i * 80}">')
        out.append(f'<text x="{x0 + 55}" y="50" text-anchor="middle" class="t-label">頭 {i + 1}</text>')
        out.append(f'<rect x="{x0 - 4}" y="{y0 - 4}" width="{n * step + 6}" height="{n * step + 6}" rx="6" class="{"box-accent" if key else "box-soft"}" style="fill:none"/>')
        for r in range(n):
            for c in range(n):
                v = m[r][c]
                cls = "fill-accent" if key else "fill-ink"
                out.append(f'<rect x="{x0 + c * step}" y="{y0 + r * step}" width="{cell}" height="{cell}" rx="2" class="{cls}" style="opacity:{.06 + .94 * v:.2f}"/>')
        out.append(f'<text x="{x0 + 55}" y="212" text-anchor="middle" font-size="18" class="{"t-accent" if key else "t-muted"}">{role}</text>')
        out.append("</g>")
    for i in range(n):
        x_from, x_to = 10 + i * 138 + 55, 148 + i * 100 + 49
        out.append(f'<path class="line-soft" d="M{x_from} 232 C {x_from} 262, {x_to} 262, {x_to} 290" data-draw="{800 + i * 40}"/>')
    for i in range(n):
        cls = "box-accent" if i == 4 else "box-soft"
        out.append(f'<rect class="{cls}" x="{148 + i * 100}" y="294" width="98" height="30" rx="4" data-pop="{1150 + i * 30}"/>')
    out.append('<text x="964" y="315" font-size="18" class="t-muted" data-fade="1300">串接 Concat</text>')
    out.append('<text x="548" y="352" text-anchor="middle" font-size="16" class="t-muted" data-fade="1350">8 × 64 = 512 維</text>')
    out.append('<path class="line" d="M548 362 V384" data-draw="1400"/><path class="head" d="M543 380 L548 390 L553 380 Z" data-fade="1650"/>')
    out.append('<rect class="box" x="438" y="394" width="220" height="46" rx="8" data-pop="1500"/>')
    out.append('<text x="548" y="424" text-anchor="middle" font-size="19" class="t-ink" data-fade="1550">線性轉換 Linear</text>')
    out.append('<path class="line" d="M548 444 V470" data-draw="1650"/><path class="head" d="M543 466 L548 476 L553 466 Z" data-fade="1900"/>')
    out.append('<text x="548" y="506" text-anchor="middle" font-size="20" class="t-ink" data-fade="1900">多頭注意力的輸出</text>')
    return "\n".join(out)


# ── slide 11: sinusoidal position stamps ──────────────────────────────────
def waves():
    x0, x1, n_pos = 112, 920, 50
    px = (x1 - x0) / n_pos
    pos = 26
    xp = x0 + pos * px
    rows = []
    out = []
    for i in range(5):
        yc, amp = 62 + i * 98, 32
        lam = 58 * 1.86 ** i
        phase = 0 if i % 2 == 0 else math.pi / 2
        pts = []
        x = x0
        while x <= x1 + .01:
            y = yc - amp * math.sin(2 * math.pi * (x - x0) / lam + phase)
            pts.append(f"{x:.1f} {y:.1f}")
            x += 3
        d = "M" + " L".join(pts)
        out.append(f'<path class="line-faint" d="M{x0} {yc} H{x1}"/>')
        out.append(f'<path class="line" d="{d}" data-draw="{i * 160}" data-dur="1700" style="stroke-width:1.6"/>')
        out.append(f'<text x="0" y="{yc + 8}" class="t-display t-muted" font-size="24" font-style="italic">{"sin" if i % 2 == 0 else "cos"}<tspan font-size="16" dy="5">{i}</tspan></text>')
        v = math.sin(2 * math.pi * (xp - x0) / lam + phase)
        rows.append((yc - amp * v, v))
    out.append(f'<path class="line-accent" d="M{xp:.1f} 14 V500" data-draw="1100"/>')
    out.append(f'<text x="{xp + 12:.1f}" y="22" class="t-display t-accent" font-size="26" font-style="italic" data-fade="1300">pos = {pos}</text>')
    for k, (y, v) in enumerate(rows):
        out.append(f'<circle class="fill-accent" cx="{xp:.1f}" cy="{y:.1f}" r="6.5" style="stroke:var(--paper); stroke-width:2.5" data-pop="{1350 + k * 70}"/>')
        out.append(f'<text x="{xp + 16:.1f}" y="{y - 12:.1f}" font-size="18" class="t-ink halo-text" style="font-variant-numeric:tabular-nums" data-fade="{1450 + k * 70}">{("+" if v >= 0 else "−") + f"{abs(v):.2f}"}</text>')
    out.append(f'<path class="axis" d="M{x0} 508 H{x1}"/>')
    for p in range(0, 51, 10):
        x = x0 + p * px
        out.append(f'<path class="axis" d="M{x:.1f} 508 V516"/><text x="{x:.1f}" y="540" text-anchor="middle" font-size="16" class="t-muted">{p}</text>')
    out.append(f'<text x="{x0}" y="540" text-anchor="end" dx="-14" font-size="16" class="t-muted">pos</text>')
    return "\n".join(out)


# ── slide 13: cost vs quality ─────────────────────────────────────────────
def scatter():
    X = lambda lf: 96 + (lf - 18.3) * 438.18
    Y = lambda b: 470 - (b - 24) * 86
    out = []
    for b in range(24, 30):
        out.append(f'<path class="grid-line" d="M96 {Y(b):.1f} H1060"/>')
        out.append(f'<text x="80" y="{Y(b) + 6:.1f}" text-anchor="end" class="tick">{b}</text>')
    for lf, lab in [(18.4771, "3×10¹⁸"), (19, "10¹⁹"), (19.4771, "3×10¹⁹"), (20, "10²⁰"), (20.4771, "3×10²⁰")]:
        out.append(f'<path class="axis" d="M{X(lf):.1f} 470 V478"/><text x="{X(lf):.1f}" y="504" text-anchor="middle" class="tick">{lab}</text>')
    out.append('<path class="axis" d="M96 470 H1060"/>')
    out.append('<text x="96" y="20" class="ax-label">BLEU · 英→德（越高越準）</text>')
    out.append('<text x="1060" y="546" text-anchor="end" class="ax-label">訓練成本 · FLOPs，對數刻度（越右越貴）</text>')
    pts = [
        ("GNMT + RL", 2.3e19, 24.6, "r"), ("ConvS2S", 9.6e18, 25.16, "r"), ("MoE", 2.0e19, 26.03, "l"),
        ("GNMT + RL 集成", 1.8e20, 26.30, "b"), ("ConvS2S 集成", 7.7e19, 26.36, "t"),
    ]
    keys = [("Transformer (base)", 3.3e18, 27.3), ("Transformer (big)", 2.3e19, 28.4)]
    # the +3.8 bracket: same cost, GNMT + RL vs Transformer (big)
    xb = X(math.log10(2.3e19))
    out.append(f'<path class="line-soft" d="M{xb + 14:.1f} {Y(24.6):.1f} H{xb + 22:.1f} V{Y(28.4):.1f} H{xb + 14:.1f}" data-draw="1500"/>')
    out.append(f'<text x="{xb + 36:.1f}" y="{(Y(24.6) + Y(28.4)) / 2 - 4:.1f}" class="lbl-key" data-fade="1800">同樣成本</text>')
    out.append(f'<text x="{xb + 36:.1f}" y="{(Y(24.6) + Y(28.4)) / 2 + 24:.1f}" class="lbl-val" data-fade="1800">BLEU 高出 3.8</text>')
    for k, (name, flops, bleu, side) in enumerate(pts):
        x, y = X(math.log10(flops)), Y(bleu)
        out.append(f'<g data-pop="{300 + k * 90}"><title>{name}：BLEU {bleu}，{flops:.1e} FLOPs</title>'
                   f'<circle class="pt" cx="{x:.1f}" cy="{y:.1f}" r="7.5"/></g>')
        dx, dy, anchor = {"r": (16, 7, "start"), "l": (-16, 7, "end"), "b": (0, 36, "middle"), "t": (0, -20, "middle")}[side]
        if name == "GNMT + RL":
            dx = 36
        out.append(f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}" class="lbl" data-fade="{700 + k * 90}">{name}</text>')
    for k, (name, flops, bleu) in enumerate(keys):
        x, y = X(math.log10(flops)), Y(bleu)
        out.append(f'<circle class="halo" cx="{x:.1f}" cy="{y:.1f}" r="11"/>')
        out.append(f'<g data-pop="{1000 + k * 200}"><title>{name}：BLEU {bleu}，{flops:.1e} FLOPs</title>'
                   f'<circle class="pt-key" cx="{x:.1f}" cy="{y:.1f}" r="10"/></g>')
        lx = x + (36 if "big" in name else 22)
        out.append(f'<text x="{lx:.1f}" y="{y - 2:.1f}" class="lbl-key" data-fade="{1200 + k * 200}">{name}</text>')
        out.append(f'<text x="{lx:.1f}" y="{y + 25:.1f}" class="lbl-val" data-fade="{1250 + k * 200}">BLEU {bleu}</text>')
    out.append('<g data-fade="1900"><circle class="pt-key" cx="806" cy="14" r="8"/><text x="822" y="21" class="lbl">Transformer</text>'
               '<circle class="pt" cx="958" cy="14" r="7"/><text x="972" y="21" class="lbl">先前模型</text></g>')
    out.append(f'<text x="1052" y="{Y(24.35):.1f}" text-anchor="end" class="ax-label" data-fade="2000">越往左上 · 越準也越省</text>')
    return "\n".join(out)


GEN = {"cover": cover, "network": network, "its": its, "heads": heads, "waves": waves, "scatter": scatter}
html = DECK.read_text()
for name, fn in GEN.items():
    pat = re.compile(rf"(<!--gen:{name}-->)(.*?)(<!--/gen-->)", re.S)
    if not pat.search(html):
        print("missing marker", name)
        continue
    body = fn()
    html = pat.sub(lambda m: m.group(1) + "\n" + body + "\n" + m.group(3), html, count=1)
DECK.write_text(html)
print("ok", {k: len(v()) for k, v in GEN.items()})
