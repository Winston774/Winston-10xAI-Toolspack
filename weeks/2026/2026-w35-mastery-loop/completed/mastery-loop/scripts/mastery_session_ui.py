#!/usr/bin/env python3
"""Serve Mastery Loop v3 phases in one local browser tab per phase.

The browser receives only the current visible surface. Stable identifiers,
correct answers, explanations, future questions, and score calculations stay
on the loopback server until the learner commits an answer.
"""

from __future__ import annotations

import argparse
import hmac
import html
import json
import re
import secrets
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import session_core as core


MAX_BODY_BYTES = 64 * 1024
PHASE_LABELS = {"assessment": "評估", "learning": "學習", "review": "複習"}
BENCHMARK_LABELS = {
    "verified": "已驗證",
    "partially_verified": "部分驗證",
    "provisional": "暫定",
}
DIFFICULTY_LABELS = {
    "foundation": "基礎",
    "core": "核心",
    "advanced": "進階",
}
REQUEST_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
CHOICE_KEYBOARD_JS = """choices.forEach((choice,index)=>{choice.addEventListener('change',()=>button.disabled=false);choice.addEventListener('keydown',event=>{let target=index;if(event.key==='ArrowDown'||event.key==='ArrowRight')target=(index+1)%choices.length;else if(event.key==='ArrowUp'||event.key==='ArrowLeft')target=(index+choices.length-1)%choices.length;else if(event.key!==' '&&event.key!=='Enter')return;event.preventDefault();const next=choices[target];next.checked=true;next.focus();next.dispatchEvent(new Event('change',{bubbles:true}));});});"""


class UiError(RuntimeError):
    """Raised when a browser action violates the current UI state."""


@dataclass(frozen=True)
class SessionBundle:
    workspace: Path
    cycle_dir: Path
    cycle: dict[str, Any]
    phase: str
    phase_dir: Path
    spec: dict[str, Any]
    slices: dict[str, dict[str, Any]] | None = None
    assessment_spec: dict[str, Any] | None = None
    assessment_report: dict[str, Any] | None = None
    learning_report: dict[str, Any] | None = None


def _artifact_path(
    cycle_dir: Path,
    cycle: Mapping[str, Any],
    key: str,
    default: str,
    *,
    required: bool = True,
) -> Path:
    value = cycle.get("artifacts", {}).get(key, default)
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = cycle_dir / candidate
    path = core.resolve_within(cycle_dir, candidate)
    if required and not path.is_file():
        raise core.SpecError(f"Required artifact not found: {path}")
    return path


def _read_optional(path: Path) -> dict[str, Any] | None:
    return core.read_json_object(path) if path.is_file() else None


def _load_slice_files(cycle_dir: Path, path_spec: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    slices_dir = core.resolve_within(cycle_dir, cycle_dir / "learning" / "slices")
    result: dict[str, dict[str, Any]] = {}
    for area in path_spec.get("areas", []):
        for slice_id in area.get("slice_ids", []):
            path = core.resolve_within(slices_dir, slices_dir / f"{slice_id}.json")
            if not path.is_file():
                raise core.SpecError(f"Learning slice not found: {path}")
            result[slice_id] = core.read_json_object(path)
    return result


def load_phase_bundle(workspace: Path, cycle_ref: str, phase: str) -> SessionBundle:
    raw_workspace = Path(workspace).expanduser()
    workspace = core.resolve_within(raw_workspace, raw_workspace)
    cycle_dir, cycle = core.load_cycle(workspace, cycle_ref)
    if phase == "assessment":
        spec_path = _artifact_path(cycle_dir, cycle, "assessment_spec", "assessment/spec.json")
        spec = core.validate_assessment_spec(core.read_json_object(spec_path), cycle)
        core.validate_batch_manifest(spec_path.parent, spec)
        return SessionBundle(workspace, cycle_dir, cycle, phase, spec_path.parent, spec)
    if phase == "learning":
        assessment_spec_file = _artifact_path(
            cycle_dir, cycle, "assessment_spec", "assessment/spec.json"
        )
        assessment_spec = core.validate_assessment_spec(
            core.read_json_object(assessment_spec_file), cycle
        )
        assessment_report = core.build_assessment_report(
            assessment_spec_file.parent,
            assessment_spec,
            require_complete=True,
        )
        path_file = _artifact_path(cycle_dir, cycle, "learning_path", "learning/path.json")
        raw_path = core.read_json_object(path_file)
        slices = _load_slice_files(cycle_dir, raw_path)
        spec = core.validate_learning_path(
            raw_path,
            cycle,
            slices=slices,
            assessment_report=assessment_report,
            assessment_spec=assessment_spec,
        )
        normalized_slices = {
            item_id: core.validate_learning_slice(item, {area["area_id"] for area in cycle["areas"]})
            for item_id, item in slices.items()
        }
        return SessionBundle(
            workspace,
            cycle_dir,
            cycle,
            phase,
            path_file.parent,
            spec,
            normalized_slices,
            assessment_report=assessment_report,
        )
    if phase == "review":
        review_file = _artifact_path(cycle_dir, cycle, "review_spec", "review/spec.json")
        assessment_file = _artifact_path(
            cycle_dir, cycle, "assessment_spec", "assessment/spec.json"
        )
        learning_path_file = _artifact_path(
            cycle_dir, cycle, "learning_path", "learning/path.json"
        )
        assessment_spec = core.validate_assessment_spec(
            core.read_json_object(assessment_file), cycle
        )
        assessment_report = core.build_assessment_report(
            assessment_file.parent,
            assessment_spec,
            require_complete=True,
        )
        learning_raw = core.read_json_object(learning_path_file)
        slices = _load_slice_files(cycle_dir, learning_raw)
        learning_spec = core.validate_learning_path(
            learning_raw,
            cycle,
            slices=slices,
            assessment_report=assessment_report,
            assessment_spec=assessment_spec,
        )
        normalized_slices = {
            item_id: core.validate_learning_slice(
                item, {area["area_id"] for area in cycle["areas"]}
            )
            for item_id, item in slices.items()
        }
        learning_report = core.build_learning_report(
            learning_path_file.parent,
            learning_spec,
            slices=normalized_slices,
            require_complete=True,
        )
        spec = core.validate_review_spec(
            core.read_json_object(review_file),
            cycle,
            assessment_spec=assessment_spec,
            learning_path=learning_spec,
            learning_slices=normalized_slices,
            assessment_report=assessment_report,
            learning_report=learning_report,
        )
        core.validate_batch_manifest(review_file.parent, spec)
        return SessionBundle(
            workspace,
            cycle_dir,
            cycle,
            phase,
            review_file.parent,
            spec,
            normalized_slices,
            assessment_spec,
            assessment_report,
            learning_report,
        )
    raise core.SpecError(f"Unsupported phase: {phase}")


STYLE = """
:root{color-scheme:light;--canvas:#f4f0e7;--paper:#fffdf8;--ink:#202126;--muted:#696870;--rule:#d9d4c9;--purple:#6552d9;--purple-dark:#4c3db1;--lime:#dff28f;--green:#287a50;--green-bg:#edf8f0;--red:#a23b42;--red-bg:#fff0f0;--blue:#1769e0;--shadow:0 18px 55px rgba(42,37,29,.09)}
*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--ink);font-family:Aptos,"Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif;line-height:1.65}
.shell{width:min(100% - 32px,960px);margin:28px auto}.topline{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:12px;color:var(--muted);font-size:.92rem}.brand{font-weight:750;color:var(--ink);letter-spacing:.02em}.phase{padding:4px 9px;border:1px solid var(--rule);border-radius:999px;background:rgba(255,255,255,.5)}
main{background:var(--paper);border-radius:12px;box-shadow:var(--shadow);padding:clamp(24px,5vw,52px);overflow-wrap:anywhere}h1,h2,h3{line-height:1.25;margin:0 0 16px}h1{font-size:clamp(1.7rem,5vw,2.7rem);letter-spacing:-.035em}h2{font-size:1.25rem}p{max-width:75ch}.lede{font-size:1.08rem;color:#45454c;margin-bottom:26px}.eyebrow{font-size:.78rem;font-weight:800;letter-spacing:.11em;text-transform:uppercase;color:var(--purple);margin:0 0 9px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.scope-grid{margin-top:14px}.card{border:1px solid var(--rule);border-radius:8px;padding:17px;background:#fff}.card h3{font-size:1rem;margin-bottom:7px}.card p{margin:0;color:var(--muted)}.scope-list{margin:8px 0 0;padding-left:20px}.scope-list li+li{margin-top:5px}.meta{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}.chip{display:inline-flex;align-items:center;min-height:32px;padding:4px 10px;border-radius:999px;background:#efecfa;color:#41348e;font-size:.88rem;font-weight:650}
.button{appearance:none;border:0;border-radius:4px;min-height:46px;padding:11px 20px;background:var(--purple);color:white;font:inherit;font-weight:750;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;text-decoration:none}.button:hover{background:var(--purple-dark)}.button:disabled{opacity:.52;cursor:not-allowed}.button.secondary{background:#ece9e1;color:var(--ink)}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid var(--blue);outline-offset:3px}.actions{margin-top:28px;display:flex;justify-content:flex-end;gap:10px;flex-wrap:wrap}
.progress-row{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:9px}.progress-copy strong{display:block;font-size:1.05rem}.progress-copy span{color:var(--muted);font-size:.9rem}progress{display:block;width:100%;height:9px;border:0;border-radius:99px;overflow:hidden;background:#e5e0d6;margin-bottom:30px}progress::-webkit-progress-bar{background:#e5e0d6}progress::-webkit-progress-value{background:var(--purple)}progress::-moz-progress-bar{background:var(--purple)}
.scenario{border:1px solid #d8d1ee;border-radius:7px;padding:14px 16px;background:#f7f5fd;color:#4d4c52;margin:20px 0}.prompt{font-size:1.16rem;font-weight:720;max-width:70ch}.choice-fieldset{border:0;padding:0;margin:0}.choices{display:grid;gap:11px;margin-top:22px}.choice{position:relative}.choice input{position:absolute;opacity:0;pointer-events:none}.choice label{display:block;min-height:58px;padding:14px 16px;border:1px solid var(--rule);border-radius:7px;background:white;cursor:pointer;transition:border-color .15s,background .15s}.choice label:hover{border-color:#aaa1d7}.choice input:checked+label{border-color:var(--purple);background:#f5f2ff}.choice input:focus-visible+label{outline:3px solid var(--blue);outline-offset:3px}.choice-title{display:block;font-weight:730}.choice-desc{display:block;color:var(--muted);font-size:.94rem;margin-top:2px}.status{min-height:1.6em;color:var(--red);margin-top:10px}
.result{border-radius:8px;padding:20px;margin:20px 0}.result.correct{background:var(--green-bg);border:1px solid #b9dfc5}.result.wrong{background:var(--red-bg);border:1px solid #efc5c7}.result h2{display:flex;gap:9px;align-items:center}.answer-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:18px 0}.answer{border:1px solid var(--rule);padding:16px;border-radius:8px}.answer strong{display:block;margin-bottom:5px}.answer p{margin:0}.explanation{margin-top:9px;color:#48474d}.live{min-height:1px}
.summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:22px 0}.metric{background:var(--lime);padding:16px;border-radius:8px}.metric strong{display:block;font-size:1.55rem;line-height:1.2}.metric span{font-size:.88rem}.table-wrap{overflow-x:auto;border:1px solid var(--rule);border-radius:8px}table{width:100%;border-collapse:collapse;min-width:720px}th,td{text-align:left;vertical-align:top;padding:13px;border-bottom:1px solid var(--rule)}th{background:#f3f0e9;font-size:.86rem}tr:last-child td{border-bottom:0}.signal{font-weight:750}.signal.stable_signal{color:var(--green)}.signal.needs_support{color:var(--red)}.fine{color:var(--muted);font-size:.9rem}.notice{border:1px solid var(--rule);border-radius:8px;padding:16px;margin-top:20px;background:#faf8f2}
.map{display:grid;gap:14px;margin:22px 0}.map-area{border:1px solid var(--rule);border-radius:8px;padding:16px;background:#fff}.map-area h3{margin-bottom:10px}.nodes{display:flex;gap:8px;flex-wrap:wrap}.node{display:inline-flex;align-items:center;min-height:44px;padding:8px 11px;border:1px solid var(--rule);border-radius:6px;color:var(--ink);text-decoration:none;background:#faf9f5;font-size:.9rem}.node.done{border-color:#9acbad;background:var(--green-bg)}.node.current{border-color:var(--purple);background:#f5f2ff;font-weight:750}.node.locked{color:#69676d;background:#f0eee8}.node.checkpoint{border-style:dashed}.lesson-section{padding:19px 0;border-top:1px solid var(--rule)}.lesson-section:first-of-type{border-top:0}.lesson-section h2{font-size:1.12rem}.callout{padding:16px;border:1px solid #d8d1ee;border-radius:7px;background:#f7f5fd}.takeaways{background:var(--lime);border-radius:8px;padding:18px}.source-list{word-break:break-word}.back{display:inline-flex;align-items:center;min-height:44px;color:var(--purple);font-weight:700}.lock-note{color:var(--muted);font-size:.88rem;margin-top:10px}
footer{text-align:center;color:var(--muted);font-size:.84rem;padding:22px 8px 8px}@media(max-width:700px){.shell{width:min(100% - 20px,960px);margin:10px auto}.grid,.answer-grid,.summary{grid-template-columns:1fr}main{padding:22px 18px}.topline{padding:0 4px}.actions .button{width:100%}.progress-row{align-items:flex-start;flex-direction:column;gap:3px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
"""


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _json_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def _same_token(provided: Any, expected: str) -> bool:
    return isinstance(provided, str) and hmac.compare_digest(provided, expected)


def render_page(title: str, phase: str, body: str, script: str, nonce: str) -> str:
    script_tag = f'<script nonce="{_esc(nonce)}">{script}</script>' if script else ""
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_esc(title)}</title><style nonce="{_esc(nonce)}">{STYLE}</style></head>
<body><div class="shell"><div class="topline"><span class="brand">Mastery Loop</span><span class="phase">{_esc(PHASE_LABELS[phase])}</span></div><main>{body}</main><footer>Created by Winston</footer></div>{script_tag}</body></html>"""


def _button_script(endpoint: str, csrf: str, payload: Mapping[str, Any], button_id: str) -> str:
    return f"""(()=>{{const button=document.getElementById({_json_script(button_id)});const status=document.getElementById('status');if(!button)return;button.addEventListener('click',async()=>{{button.disabled=true;status.textContent='';try{{const response=await fetch({_json_script(endpoint)},{{method:'POST',headers:{{'Content-Type':'application/json','X-Mastery-Token':{_json_script(csrf)}}},body:JSON.stringify({_json_script(payload)})}});const page=await response.text();if(!response.ok)throw new Error(page);document.open();document.write(page);document.close();}}catch(error){{status.textContent='操作失敗，請稍後重試。';button.disabled=false;}}}});}})();"""


def _assessment_intro_script(csrf: str) -> str:
    actions = [
        ("primary", "/start", {"request_id": secrets.token_hex(12)}),
        (
            "adjust-scope",
            "/scope-action",
            {"request_id": secrets.token_hex(12), "action": "adjust_scope"},
        ),
        (
            "pause-cycle",
            "/scope-action",
            {"request_id": secrets.token_hex(12), "action": "pause"},
        ),
    ]
    return "".join(
        _button_script(endpoint, csrf, payload, button_id)
        for button_id, endpoint, payload in actions
    )


def _scope_cards(cycle: Mapping[str, Any]) -> str:
    scope = cycle["knowledge_scope"]
    areas = "".join(
        f'<article class="card"><h3>{_esc(area["title"])}</h3><p>{_esc(area["description"])}</p></article>'
        for area in cycle["areas"]
    )
    includes = "".join(f"<li>{_esc(item)}</li>" for item in scope["includes"])
    excludes = "".join(f"<li>{_esc(item)}</li>" for item in scope["excludes"])
    sources = "".join(f"<li>{_esc(item)}</li>" for item in scope["sources"])
    source_block = sources or "<li>目前沒有可列出的來源；基準維持暫定。</li>"
    return f"""
<h2>知識範圍</h2><p>{_esc(scope['direction'])}</p>
<div class="grid">{areas}</div>
<div class="grid scope-grid"><section class="card"><h3>涵蓋內容</h3><ul class="scope-list">{includes}</ul></section><section class="card"><h3>本輪排除</h3><ul class="scope-list">{excludes or '<li>未列出額外排除項目。</li>'}</ul></section></div>
<section class="notice"><strong>Benchmark：{_esc(BENCHMARK_LABELS[scope['benchmark_status']])}</strong><ul class="scope-list">{source_block}</ul></section>"""


def _cycle_visible_choice_context(
    cycle: Mapping[str, Any],
) -> list[tuple[str, str]]:
    scope = cycle["knowledge_scope"]
    entries = [
        ("cycle.mission.ultimate_outcome", cycle["mission"]["ultimate_outcome"]),
        ("cycle.mission.audience", cycle["mission"]["audience"]),
        ("cycle.knowledge_scope.title", scope["title"]),
        ("cycle.knowledge_scope.direction", scope["direction"]),
    ]
    for field in ("includes", "excludes", "sources"):
        entries.extend(
            (f"cycle.knowledge_scope.{field}[{index}]", value)
            for index, value in enumerate(scope[field])
        )
    for index, area in enumerate(cycle["areas"]):
        entries.extend(
            (
                (f"cycle.areas[{index}].title", area["title"]),
                (f"cycle.areas[{index}].description", area["description"]),
            )
        )
    return entries


def _learning_visible_choice_context(
    bundle: SessionBundle,
) -> list[tuple[str, str]]:
    entries = [("learning.title", bundle.spec["title"])]
    entries.extend(
        (f"learning.areas[{index}].title", area["title"])
        for index, area in enumerate(bundle.spec["areas"])
    )
    for slice_id, item in (bundle.slices or {}).items():
        entries.append((f"learning.slices[{slice_id}].title", item["title"]))
    return entries


def render_assessment_intro(bundle: SessionBundle, csrf: str, nonce: str) -> str:
    spec = bundle.spec
    core.validate_visible_context_contract(
        spec,
        _cycle_visible_choice_context(bundle.cycle),
        allow_plain_option_labels=True,
    )
    distribution = "".join(
        f'<span class="chip">{_esc(area["title"])} · {sum(1 for question in spec["questions"] if question["area_id"] == area["area_id"])} 題</span>'
        for area in bundle.cycle["areas"]
    )
    body = f"""
<p class="eyebrow">開始前確認</p><h1>{_esc(spec['title'])}</h1>
<p class="lede">目標：{_esc(bundle.cycle['mission']['ultimate_outcome'])}</p>
{_scope_cards(bundle.cycle)}
<div class="meta"><span class="chip">{len(spec['questions'])} 題</span><span class="chip">約 {spec['estimated_minutes']} 分鐘</span><span class="chip">{len(bundle.cycle['areas'])} 個主要領域</span></div>
<section class="notice"><strong>題數分布</strong><div class="meta">{distribution}</div></section>
<p>{_esc(spec['instructions'])}</p>
<div class="actions"><button class="button secondary" id="pause-cycle" type="button">暫停</button><button class="button secondary" id="adjust-scope" type="button">調整範圍</button><button class="button" id="primary" type="button">確認範圍並開始</button></div><p id="status" class="status" role="status" aria-live="polite"></p>"""
    script = _assessment_intro_script(csrf)
    return render_page(spec["title"], "assessment", body, script, nonce)


def render_scope_exit(bundle: SessionBundle, action: str, nonce: str) -> str:
    if action == "adjust_scope":
        title = "返回 Codex 調整範圍"
        copy = "目前尚未開始評估，也沒有建立作答證據。請關閉此頁並回到 Codex 修改學習目標、涵蓋內容或排除內容。"
    else:
        title = "本輪已暫停"
        copy = "目前進度保留在評估開始前。需要繼續時，重新啟動同一個 Assessment phase 即可。"
    body = f"""<p class="eyebrow">開始前確認</p><h1>{_esc(title)}</h1><section class="notice"><p>{_esc(copy)}</p></section><section class="notice"><strong>下一步</strong><p>請關閉此頁並回到 Codex。</p></section>"""
    return render_page(title, "assessment", body, "", nonce)


def render_review_intro(bundle: SessionBundle, csrf: str, nonce: str) -> str:
    spec = bundle.spec
    core.validate_visible_context_contract(
        spec,
        _cycle_visible_choice_context(bundle.cycle),
        allow_plain_option_labels=True,
    )
    prior_gaps = len((bundle.assessment_report or {}).get("gaps", [])) + len(
        (bundle.learning_report or {}).get("gaps", [])
    )
    body = f"""
<p class="eyebrow">整合複習</p><h1>{_esc(spec['title'])}</h1>
<p class="lede">每題保留核心命題，並改用全新情境、題型、提示與選項，檢查你能否轉用剛完成的知識。</p>
{_scope_cards(bundle.cycle)}
<div class="meta"><span class="chip">{len(spec['questions'])} 題</span><span class="chip">{prior_gaps} 個先前缺口訊號</span><span class="chip">包含跨領域整合</span></div>
<p>{_esc(spec['instructions'])}</p>
<div class="actions"><button class="button" id="primary" type="button">開始複習</button></div><p id="status" class="status" role="status" aria-live="polite"></p>"""
    script = _button_script("/start", csrf, {"request_id": secrets.token_hex(12)}, "primary")
    return render_page(spec["title"], "review", body, script, nonce)


def _progress(index: int, total: int, *, feedback: bool = False, noun: str = "題") -> str:
    completed = index + (1 if feedback else 0)
    remaining = total - completed
    return f"""<div class="progress-row"><div class="progress-copy"><strong>第 {index + 1} / {total} {noun}</strong><span>已完成 {completed} {noun} · 剩餘 {remaining} {noun}</span></div></div><progress value="{completed}" max="{total}" aria-label="進度">{completed}/{total}</progress>"""


def _render_choice_options(
    option_tokens: list[tuple[str, Mapping[str, Any]]],
    *,
    descriptions_allowed: bool = True,
) -> str:
    """Render balanced choices without leaking correctness from legacy copy."""

    show_descriptions = descriptions_allowed and all(
        core.choice_description_is_safe(
            option.get("label"), option.get("description")
        )
        for _, option in option_tokens
    )
    rendered: list[str] = []
    for position, (token, option) in enumerate(option_tokens):
        description = (
            f'<span class="choice-desc">{_esc(option["description"])}</span>'
            if show_descriptions
            else ""
        )
        rendered.append(
            f'<div class="choice"><input type="radio" name="answer" id="choice-{position}" value="{_esc(token)}"><label for="choice-{position}"><span class="choice-title">{_esc(option["label"])}</span>{description}</label></div>'
        )
    return "".join(rendered)


def _choice_descriptions_allowed(spec: Mapping[str, Any]) -> bool:
    try:
        core.validate_choice_description_contract(spec)
    except core.SpecError:
        return False
    return True


def render_batch_question(
    bundle: SessionBundle,
    question: Mapping[str, Any],
    index: int,
    csrf: str,
    question_token: str,
    option_tokens: list[tuple[str, Mapping[str, Any]]],
    nonce: str,
) -> str:
    core.validate_choice_label_contract(
        bundle.spec, check_future_surfaces=False
    )
    total = len(bundle.spec["questions"])
    area = next(item for item in bundle.cycle["areas"] if item["area_id"] == question["area_id"])
    options = _render_choice_options(
        option_tokens,
        descriptions_allowed=_choice_descriptions_allowed(bundle.spec),
    )
    body = f"""
{_progress(index,total)}<p class="eyebrow">{_esc(area['title'])}</p><h1>{_esc(question['title'])}</h1>
<div class="scenario">{_esc(question['scenario_context'])}</div><p class="prompt">{_esc(question['prompt'])}</p>
<fieldset class="choice-fieldset"><legend class="fine">選擇一個最符合目前情境的答案</legend><div class="choices">{options}</div></fieldset>
<div class="actions"><button class="button" id="primary" type="button" disabled>提交答案</button></div><p id="status" class="status" role="status" aria-live="polite"></p>"""
    script = f"""(()=>{{const button=document.getElementById('primary');const choices=[...document.querySelectorAll('input[name="answer"]')];const status=document.getElementById('status');{CHOICE_KEYBOARD_JS}button.addEventListener('click',async()=>{{const selected=choices.find(choice=>choice.checked);if(!selected)return;button.disabled=true;choices.forEach(choice=>choice.disabled=true);status.textContent='正在提交…';const payload={{request_id:{_json_script(secrets.token_hex(12))},question_token:{_json_script(question_token)},option_token:selected.value}};try{{const response=await fetch('/answer',{{method:'POST',headers:{{'Content-Type':'application/json','X-Mastery-Token':{_json_script(csrf)}}},body:JSON.stringify(payload)}});const page=await response.text();if(!response.ok)throw new Error(page);document.open();document.write(page);document.close();}}catch(error){{status.textContent='提交失敗，請重試。';button.disabled=false;choices.forEach(choice=>choice.disabled=false);}}}});}})();"""
    return render_page(question["title"], bundle.phase, body, script, nonce)


def render_batch_feedback(
    bundle: SessionBundle,
    question: Mapping[str, Any],
    record: Mapping[str, Any],
    index: int,
    csrf: str,
    next_token: str,
    nonce: str,
) -> str:
    options = {item["id"]: item for item in question["options"]}
    selected = options[record["selected_option_id"]]
    correct = options[question["correct_option_id"]]
    is_correct = bool(record["is_correct"])
    if is_correct:
        answer_cards = f'<section class="answer"><strong>你的答案 · 正確答案</strong><p>{_esc(correct["label"])}</p><p class="explanation">{_esc(correct["explanation"])}</p></section>'
        answer_grid_class = ""
    else:
        answer_cards = f'<section class="answer"><strong>你的答案</strong><p>{_esc(selected["label"])}</p><p class="explanation">{_esc(selected["explanation"])}</p></section><section class="answer"><strong>正確答案</strong><p>{_esc(correct["label"])}</p><p class="explanation">{_esc(correct["explanation"])}</p></section>'
        answer_grid_class = " answer-grid"
    total = len(bundle.spec["questions"])
    label = "回答正確" if is_correct else "這題需要補強"
    sources = "".join(f"<li>{_esc(value)}</li>" for value in question["sources"])
    body = f"""
{_progress(index,total,feedback=True)}<div class="result {'correct' if is_correct else 'wrong'}" role="status" aria-live="polite"><h2>{'✓' if is_correct else '↗'} {label}</h2><p>{'你辨識出這個核心判準。' if is_correct else '先對齊判準，再繼續下一題。'}</p></div>
<div class="{answer_grid_class.strip()}">{answer_cards}</div>
<section class="notice"><strong>判準來源</strong><ul class="scope-list">{sources}</ul></section>
<div class="actions"><button class="button" id="primary" type="button">{'查看總表' if index + 1 == total else '下一題'}</button></div><p id="status" class="status" role="status" aria-live="polite"></p>"""
    script = _button_script(
        "/next",
        csrf,
        {"request_id": secrets.token_hex(12), "next_token": next_token},
        "primary",
    )
    return render_page(label, bundle.phase, body, script, nonce)


def render_assessment_report(bundle: SessionBundle, report: Mapping[str, Any], nonce: str) -> str:
    area_titles = {item["area_id"]: item["title"] for item in bundle.cycle["areas"]}
    question_results = {item["question_id"]: item for item in report["question_results"]}
    critical_gap_ids = set(report["critical_gap_ids"])
    rows = []
    for area in report["area_results"]:
        questions = [item for item in bundle.spec["questions"] if item["area_id"] == area["area_id"]]
        misses = [item for item in questions if not question_results[item["question_id"]]["is_correct"]]
        gap_lines: list[str] = []
        for item in misses:
            prefix = "關鍵 · " if f"assessment.{item['question_id']}" in critical_gap_ids else ""
            misconception = question_results[item["question_id"]].get("misconception_tag")
            gap_lines.append(
                f'<span>{prefix}{_esc(item["core_proposition"])}</span><br><span class="fine">{_esc(item["knowledge_kernel_id"])} · {_esc(misconception or "尚無 misconception 標籤")}</span>'
            )
        gap_copy = "<br>".join(gap_lines) or '<span class="fine">本輪沒有答錯題。</span>'
        trace = ", ".join(item["question_id"] for item in questions)
        rows.append(
            f'<tr><td><strong>{_esc(area_titles[area["area_id"]])}</strong></td><td>{area["correct"]} / {area["total"]}</td><td><span class="signal {_esc(area["signal"])}">{_esc(area["signal_label"])}</span><br><span class="fine">信心：{_esc(area["confidence"])}</span></td><td>{gap_copy}</td><td>{area["suggested_slice_count"]} slices</td><td class="fine">{_esc(trace)}</td></tr>'
        )
    limitations = "".join(f"<li>{_esc(item)}</li>" for item in report["evidence_limitations"])
    body = f"""
<p class="eyebrow">評估完成</p><h1>你的知識訊號總表</h1><p class="lede">結果依主要領域聚合，供下一階段生成由簡到難的 Learning Slices。</p>
<div class="summary"><div class="metric"><strong>{report['answered']}</strong><span>完成題數</span></div><div class="metric"><strong>{report['correct']}</strong><span>答對題數</span></div><div class="metric"><strong>{len(report['gaps'])}</strong><span>待補強核心</span></div></div>
<div class="table-wrap"><table><thead><tr><th>領域</th><th>答對</th><th>訊號</th><th>關鍵缺口</th><th>建議學習量</th><th>題目追溯</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<section class="notice"><h2>證據限制</h2><ul class="scope-list">{limitations}</ul></section><section class="notice"><strong>下一步</strong><p>請關閉此頁並回到 Codex。下一階段會依這份總表生成知識地圖。</p></section>"""
    return render_page("評估總表", "assessment", body, "", nonce)


def _flatten_slices(bundle: SessionBundle) -> list[str]:
    return [slice_id for area in bundle.spec["areas"] for slice_id in area["slice_ids"]]


def _learning_progress(bundle: SessionBundle) -> dict[str, Any]:
    if bundle.slices is None:
        raise core.SpecError("Learning Slice files are required")
    return core.learning_completion_state(
        bundle.phase_dir, bundle.spec, slices=bundle.slices
    )


def _assessment_status(bundle: SessionBundle, question_id: str) -> str:
    report = bundle.assessment_report or {}
    result = next(
        (item for item in report.get("question_results", []) if item.get("question_id") == question_id),
        None,
    )
    if result is None:
        return "未出現在評估報告"
    return "評估答對" if result.get("is_correct") else "評估待補強"


def render_learning_map(
    bundle: SessionBundle,
    state: Mapping[str, Any],
    *,
    current_slice_id: str = "",
    current_area_id: str = "",
    current_clickable: bool = True,
) -> str:
    assert bundle.slices is not None
    completed_slices = set(state["completed_slice_ids"])
    completed_checks = set(state["completed_checkpoint_area_ids"])
    areas_html: list[str] = []
    for area in bundle.spec["areas"]:
        nodes: list[str] = []
        for position, slice_id in enumerate(area["slice_ids"], start=1):
            item = bundle.slices[slice_id]
            title = f"{position}. {item['title']}"
            if slice_id in completed_slices:
                nodes.append(
                    f'<a class="node done" href="/slice/{_esc(slice_id)}" aria-label="已完成：{_esc(item["title"])}">✓ {_esc(title)}</a>'
                )
            elif slice_id == current_slice_id:
                if current_clickable:
                    nodes.append(
                        f'<a class="node current" href="/slice/{_esc(slice_id)}" aria-current="step">{_esc(title)}</a>'
                    )
                else:
                    nodes.append(
                        f'<span class="node current" aria-current="step">{_esc(title)}</span>'
                    )
            else:
                nodes.append(
                    f'<span class="node locked" aria-label="尚未解鎖：{_esc(item["title"])}">鎖定 · {_esc(title)}</span>'
                )
        check_class = "done" if area["area_id"] in completed_checks else (
            "current" if area["area_id"] == current_area_id else "locked"
        )
        check_prefix = "✓" if check_class == "done" else ("現在" if check_class == "current" else "鎖定")
        nodes.append(
            f'<span class="node checkpoint {check_class}">{check_prefix} · 領域檢核</span>'
        )
        areas_html.append(
            f'<section class="map-area"><h3>{_esc(area["title"])}</h3><div class="nodes">{"".join(nodes)}</div></section>'
        )
    return f'<div class="map" aria-label="知識地圖">{"".join(areas_html)}</div>'


def render_learning_intro(bundle: SessionBundle, csrf: str, nonce: str) -> str:
    core.validate_visible_context_contract(
        bundle.spec,
        _learning_visible_choice_context(bundle),
        allow_plain_option_labels=True,
    )
    state = _learning_progress(bundle)
    first_slice = _flatten_slices(bundle)[0]
    body = f"""
<p class="eyebrow">知識地圖</p><h1>{_esc(bundle.spec['title'])}</h1>
<p class="lede">依前置關係由簡到難前進；完成節點可以回看，後續節點會顯示位置並保持鎖定。</p>
{render_learning_map(bundle,state,current_slice_id=first_slice,current_clickable=False)}
<div class="meta"><span class="chip">{state['total_slices']} 個 Learning Slices</span><span class="chip">{state['total_checkpoints']} 次領域檢核</span><span class="chip">完成閱讀只計學習進度</span></div>
<div class="actions"><button class="button" id="primary" type="button">開始學習</button></div><p id="status" class="status" role="status" aria-live="polite"></p>"""
    script = _button_script("/start", csrf, {"request_id": secrets.token_hex(12)}, "primary")
    return render_page(bundle.spec["title"], "learning", body, script, nonce)


def render_learning_slice(
    bundle: SessionBundle,
    slice_id: str,
    csrf: str,
    slice_token: str,
    nonce: str,
    *,
    reviewing: bool = False,
) -> str:
    assert bundle.slices is not None
    item = bundle.slices[slice_id]
    state = _learning_progress(bundle)
    completed = slice_id in set(state["completed_slice_ids"])
    flat = _flatten_slices(bundle)
    index = flat.index(slice_id)
    prerequisites = "".join(
        f"<li>{_esc(bundle.slices[value]['title'])}</li>" for value in item["prerequisites"]
    ) or "<li>無</li>"
    links = "".join(
        f"<li>{_esc(question_id)} · {_esc(_assessment_status(bundle, question_id))}</li>"
        for question_id in item["assessment_question_ids"]
    ) or "<li>本 slice 用於建立必要的基礎或跨領域連結。</li>"
    boundaries = "".join(f"<li>{_esc(value)}</li>" for value in item["boundaries"])
    mistakes = "".join(f"<li>{_esc(value)}</li>" for value in item["common_mistakes"])
    takeaways = "".join(f"<li>{_esc(value)}</li>" for value in item["key_takeaways"])
    sources = "".join(f"<li>{_esc(value)}</li>" for value in item["sources"])
    controls = '<a class="back" href="/">← 回到目前進度</a>' if reviewing or completed else f'<div class="actions"><button class="button" id="primary" type="button">完成並繼續</button></div><p id="status" class="status" role="status" aria-live="polite"></p>'
    script = ""
    if not reviewing and not completed:
        script = _button_script(
            "/complete",
            csrf,
            {
                "request_id": secrets.token_hex(12),
                "slice_token": slice_token,
            },
            "primary",
        )
    completed_count = state["completed_slices"]
    progress_html = f"""<div class="progress-row"><div class="progress-copy"><strong>知識地圖 · {index + 1} / {len(flat)}</strong><span>已完成 {completed_count} 個 slice · 剩餘 {len(flat) - completed_count} 個 slice</span></div></div><progress value="{completed_count}" max="{len(flat)}" aria-label="學習進度">{completed_count}/{len(flat)}</progress>"""
    body = f"""
{progress_html}
<p class="eyebrow">{_esc(next(area['title'] for area in bundle.spec['areas'] if area['area_id'] == item['area_id']))} · {DIFFICULTY_LABELS[item['difficulty']]}</p><h1>{_esc(item['title'])}</h1>
{render_learning_map(bundle,state,current_slice_id=slice_id)}
<section class="lesson-section"><h2>你將能做到</h2><p>{_esc(item['learning_objective'])}</p><h3>前置知識</h3><ul>{prerequisites}</ul><h3>對應評估</h3><ul>{links}</ul></section>
<section class="lesson-section"><h2>核心解釋</h2><p>{_esc(item['core_explanation'])}</p><h3>運作機制</h3><p>{_esc(item['mechanism'])}</p><h3>適用邊界</h3><ul>{boundaries}</ul></section>
<section class="lesson-section"><h2>Worked example</h2><div class="callout"><strong>{_esc(item['worked_example']['scenario_context'])}</strong><p>{_esc(item['worked_example']['walkthrough'])}</p></div></section>
<section class="lesson-section"><h2>常見錯誤</h2><ul>{mistakes}</ul></section>
<section class="lesson-section takeaways"><h2>重點摘要</h2><ul>{takeaways}</ul></section>
<section class="lesson-section source-list"><h2>來源</h2><ul>{sources}</ul></section>{controls}"""
    return render_page(item["title"], "learning", body, script, nonce)


def render_learning_checkpoint(
    bundle: SessionBundle,
    area_index: int,
    csrf: str,
    question_token: str,
    option_tokens: list[tuple[str, Mapping[str, Any]]],
    nonce: str,
) -> str:
    core.validate_choice_label_contract(
        bundle.spec, check_future_surfaces=False
    )
    area = bundle.spec["areas"][area_index]
    question = area["checkpoint"]
    state = _learning_progress(bundle)
    options = _render_choice_options(
        option_tokens,
        descriptions_allowed=_choice_descriptions_allowed(bundle.spec),
    )
    body = f"""
<p class="eyebrow">形成性檢核 · {area_index + 1}/{len(bundle.spec['areas'])}</p><h1>{_esc(area['title'])}</h1>
{render_learning_map(bundle,state,current_area_id=area['area_id'])}
<div class="scenario">{_esc(question['scenario_context'])}</div><p class="prompt">{_esc(question['prompt'])}</p>
<fieldset class="choice-fieldset"><legend class="fine">必須完成作答；答錯仍可前往下一領域</legend><div class="choices">{options}</div></fieldset>
<div class="actions"><button class="button" id="primary" type="button" disabled>提交檢核</button></div><p id="status" class="status" role="status" aria-live="polite"></p>"""
    script = f"""(()=>{{const button=document.getElementById('primary');const choices=[...document.querySelectorAll('input[name="answer"]')];const status=document.getElementById('status');{CHOICE_KEYBOARD_JS}button.addEventListener('click',async()=>{{const selected=choices.find(choice=>choice.checked);if(!selected)return;button.disabled=true;choices.forEach(choice=>choice.disabled=true);try{{const response=await fetch('/checkpoint-answer',{{method:'POST',headers:{{'Content-Type':'application/json','X-Mastery-Token':{_json_script(csrf)}}},body:JSON.stringify({{request_id:{_json_script(secrets.token_hex(12))},question_token:{_json_script(question_token)},option_token:selected.value}})}});const page=await response.text();if(!response.ok)throw new Error(page);document.open();document.write(page);document.close();}}catch(error){{status.textContent='提交失敗，請重試。';button.disabled=false;choices.forEach(choice=>choice.disabled=false);}}}});}})();"""
    return render_page(question["title"], "learning", body, script, nonce)


def render_learning_checkpoint_feedback(
    bundle: SessionBundle,
    area_index: int,
    record: Mapping[str, Any],
    csrf: str,
    next_token: str,
    nonce: str,
) -> str:
    area = bundle.spec["areas"][area_index]
    question = area["checkpoint"]
    options = {item["id"]: item for item in question["options"]}
    selected = options[record["selected_option_id"]]
    correct = options[question["correct_option_id"]]
    is_correct = bool(record["is_correct"])
    if is_correct:
        cards = f'<section class="answer"><strong>你的答案 · 正確答案</strong><p>{_esc(correct["label"])}</p><p class="explanation">{_esc(correct["explanation"])}</p></section>'
        card_class = ""
    else:
        cards = f'<section class="answer"><strong>你的答案</strong><p>{_esc(selected["label"])}</p><p class="explanation">{_esc(selected["explanation"])}</p></section><section class="answer"><strong>正確答案</strong><p>{_esc(correct["label"])}</p><p class="explanation">{_esc(correct["explanation"])}</p></section>'
        card_class = "answer-grid"
    last = area_index + 1 == len(bundle.spec["areas"])
    sources = "".join(f"<li>{_esc(value)}</li>" for value in question["sources"])
    body = f"""
<p class="eyebrow">{_esc(area['title'])} · 檢核結果</p><div class="result {'correct' if is_correct else 'wrong'}" role="status" aria-live="polite"><h1>{'已掌握本次整合' if is_correct else '已找到一個複習重點'}</h1><p>{'這個結果會加入最終學習報告。' if is_correct else '答案已保存；你仍可繼續下一個領域。'}</p></div>
<div class="{card_class}">{cards}</div><section class="notice"><strong>判準來源</strong><ul class="scope-list">{sources}</ul></section><div class="actions"><button class="button" id="primary" type="button">{'查看學習報告' if last else '下一領域'}</button></div><p id="status" class="status" role="status" aria-live="polite"></p>"""
    script = _button_script(
        "/checkpoint-next",
        csrf,
        {"request_id": secrets.token_hex(12), "next_token": next_token},
        "primary",
    )
    return render_page("形成性檢核結果", "learning", body, script, nonce)


def render_learning_report(bundle: SessionBundle, report: Mapping[str, Any], nonce: str) -> str:
    area_titles = {item["area_id"]: item["title"] for item in bundle.cycle["areas"]}
    results = {item["area_id"]: item for item in report["checkpoint_results"]}
    rows = "".join(
        f'<tr><td><strong>{_esc(area_titles[area["area_id"]])}</strong></td><td>{len(area["slice_ids"])} / {len(area["slice_ids"])}</td><td>{"通過" if results[area["area_id"]]["is_correct"] else "納入複習"}</td><td class="fine">{_esc(results[area["area_id"]].get("misconception_tag") or "—")}</td></tr>'
        for area in bundle.spec["areas"]
    )
    body = f"""
<p class="eyebrow">學習完成</p><h1>知識地圖已走完</h1><p class="lede">所有 slice 與領域檢核均已完成；下一份複習會融合評估缺口、檢核結果與重要正確觀念。</p>
<div class="summary"><div class="metric"><strong>{report['completed_slices']}</strong><span>完成 Slices</span></div><div class="metric"><strong>{report['completed_checkpoints']}</strong><span>完成領域檢核</span></div><div class="metric"><strong>{len(report['gaps'])}</strong><span>檢核待複習</span></div></div>
<div class="table-wrap"><table><thead><tr><th>領域</th><th>Slice 進度</th><th>檢核狀態</th><th>訊號</th></tr></thead><tbody>{rows}</tbody></table></div>
<section class="notice"><strong>證據規則</strong><p>完成閱讀只更新學習進度；mastery 等級會依評估與新情境複習的可觀察證據判定。</p></section><section class="notice"><strong>下一步</strong><p>請關閉此頁並回到 Codex，使用這份報告產生全新情境的複習問答集。</p></section>"""
    return render_page("學習報告", "learning", body, "", nonce)


def render_review_report(bundle: SessionBundle, report: Mapping[str, Any], nonce: str) -> str:
    corrected = report["corrected_gap_ids"]
    remaining = report["remaining_gap_ids"]
    new_errors = report["new_errors"]
    reinforced = report["reinforced_concepts"]
    delayed = report["delayed_review"]
    not_directly_reviewed = report.get("not_directly_reviewed_gap_ids", [])
    gap_map = {
        item["gap_id"]: item
        for source in (bundle.assessment_report or {}, bundle.learning_report or {})
        for item in source.get("gaps", [])
    }
    new_gap_map = {f"review.{item['question_id']}": item for item in new_errors}

    def gap_item(gap_id: str) -> str:
        item = gap_map.get(gap_id, {})
        proposition = item.get("core_proposition") or gap_id
        return f'<li>{_esc(proposition)}<br><span class="fine">{_esc(gap_id)}</span></li>'

    corrected_items = "".join(gap_item(value) for value in corrected) or "<li>本輪沒有可確認的修正訊號。</li>"
    remaining_items = "".join(gap_item(value) for value in remaining) or "<li>沒有殘餘的既有缺口。</li>"
    new_items = "".join(
        f'<li>{_esc(item["core_proposition"])}<br><span class="fine">{_esc(item["knowledge_kernel_id"])} · {_esc(item.get("misconception_tag") or "新錯誤訊號")}</span></li>'
        for item in new_errors
    ) or "<li>沒有新暴露的錯誤。</li>"
    reinforced_items = "".join(
        f'<li>{_esc(item["core_proposition"])}<br><span class="fine">{_esc(item["knowledge_kernel_id"])} · 題目 {_esc(item["question_id"])}</span></li>'
        for item in reinforced
    ) or "<li>本輪未另列重要正確觀念。</li>"
    coverage_notice = ""
    if not_directly_reviewed:
        coverage_items = "".join(
            gap_item(value) for value in not_directly_reviewed
        )
        coverage_notice = f'<section class="notice"><h2>本輪未直接計分的缺口</h2><p>題數已達 15 題上限；以下核心已作為整合條件納入，但不據此宣稱已修正，並保留在延遲複習清單。</p><ul class="scope-list">{coverage_items}</ul></section>'
    delayed_rows = "".join(
        f'<tr><td>{_esc((gap_map.get(item["gap_id"]) or new_gap_map.get(item["gap_id"]) or {}).get("core_proposition") or item["gap_id"])}<br><span class="fine">{_esc(item["gap_id"])}</span></td><td>{_esc(item["due_date"])}</td><td>無提示</td></tr>'
        for item in delayed
    ) or '<tr><td colspan="3">沒有需要排入延遲複習的缺口。</td></tr>'
    body = f"""
<p class="eyebrow">複習完成</p><h1>修正、殘餘與新訊號</h1><p class="lede">這份報告將評估錯誤與複習表現逐一比較；本輪到此結束。</p>
<div class="summary"><div class="metric"><strong>{len(corrected)}</strong><span>已修正缺口</span></div><div class="metric"><strong>{len(remaining)}</strong><span>殘餘缺口</span></div><div class="metric"><strong>{len(new_errors)}</strong><span>新暴露錯誤</span></div></div>
<div class="grid"><section class="card"><h2>評估錯誤 → 複習修正</h2><ul class="scope-list">{corrected_items}</ul></section><section class="card"><h2>仍存在的缺口</h2><ul class="scope-list">{remaining_items}</ul></section><section class="card"><h2>新暴露的錯誤</h2><ul class="scope-list">{new_items}</ul></section><section class="card"><h2>已加深的重要觀念</h2><ul class="scope-list">{reinforced_items}</ul></section></div>
{coverage_notice}
<section class="notice"><h2>延遲複習清單</h2><div class="table-wrap"><table><thead><tr><th>缺口</th><th>日期</th><th>方式</th></tr></thead><tbody>{delayed_rows}</tbody></table></div><p class="fine">殘餘缺口預設排在完成日後三天；不在同一輪無限重考。</p></section>
<section class="notice"><strong>本輪完成</strong><p>請關閉此頁並回到 Codex。報告與不可變作答紀錄已保留在 cycle workspace。</p></section>"""
    return render_page("複習報告", "review", body, "", nonce)


class SessionRuntime:
    """Stateful UI shell over immutable v3 evidence files."""

    def __init__(self, bundle: SessionBundle):
        self.bundle = bundle
        self.stop_requested = False
        self.csrf = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(18)
        self._mutex = threading.RLock()
        self._question_tokens = {
            item["question_id"]: secrets.token_urlsafe(24)
            for item in bundle.spec.get("questions", [])
        }
        self._option_tokens: dict[str, list[tuple[str, Mapping[str, Any]]]] = {
            item["question_id"]: [
                (secrets.token_urlsafe(18), option) for option in item["options"]
            ]
            for item in bundle.spec.get("questions", [])
        }
        self._next_tokens = {
            item["question_id"]: secrets.token_urlsafe(24)
            for item in bundle.spec.get("questions", [])
        }
        self._slice_tokens = {
            slice_id: secrets.token_urlsafe(24)
            for slice_id in (bundle.slices or {})
        }
        self._learning_question_tokens = {
            area["area_id"]: secrets.token_urlsafe(24)
            for area in bundle.spec.get("areas", [])
        }
        self._learning_option_tokens: dict[str, list[tuple[str, Mapping[str, Any]]]] = {
            area["area_id"]: [
                (secrets.token_urlsafe(18), option)
                for option in area["checkpoint"]["options"]
            ]
            for area in bundle.spec.get("areas", [])
        }
        self._learning_next_tokens = {
            area["area_id"]: secrets.token_urlsafe(24)
            for area in bundle.spec.get("areas", [])
        }
        self.checkpoint_path = core.resolve_within(
            bundle.cycle_dir, bundle.cycle_dir / "checkpoint.json"
        )

    def _save_checkpoint(self, screen: str, index: int = 0, subject_id: str = "") -> None:
        core.atomic_write_json(
            self.checkpoint_path,
            {
                "schema_version": 3,
                "cycle_id": self.bundle.cycle["cycle_id"],
                "phase": self.bundle.phase,
                "screen": screen,
                "index": index,
                "subject_id": subject_id,
                "updated_at": core.utc_now(),
                "evidence_source": False,
            },
        )

    @staticmethod
    def _subject_for_token(tokens: Mapping[str, str], provided: Any) -> str | None:
        for subject_id, expected in tokens.items():
            if _same_token(provided, expected):
                return subject_id
        return None

    @staticmethod
    def _option_for_token(
        options: list[tuple[str, Mapping[str, Any]]], provided: Any
    ) -> Mapping[str, Any] | None:
        for expected, option in options:
            if _same_token(provided, expected):
                return option
        return None

    def _checkpoint_consistent(self, value: Mapping[str, Any]) -> bool:
        screen = value["screen"]
        index = value["index"]
        subject_id = value.get("subject_id", "")
        if not isinstance(subject_id, str):
            return False
        if self.bundle.phase in {"assessment", "review"}:
            questions = self.bundle.spec["questions"]
            progress = core.response_completion_state(
                self.bundle.phase_dir, self.bundle.spec
            )
            completed = progress["completed"]
            sealed = (
                core.validate_batch_manifest(
                    self.bundle.phase_dir, self.bundle.spec
                )
                is not None
            )
            if screen == "intro":
                return index == 0 and completed == 0 and not sealed
            if screen == "question":
                return (
                    sealed
                    and 0 <= index < len(questions)
                    and completed == index
                    and subject_id == questions[index]["question_id"]
                )
            if screen == "feedback":
                return (
                    sealed
                    and 0 <= index < len(questions)
                    and completed == index + 1
                    and subject_id == questions[index]["question_id"]
                )
            if screen == "report":
                return (
                    sealed
                    and progress["complete"]
                    and index == len(questions) - 1
                    and subject_id == questions[-1]["question_id"]
                    and (self.bundle.phase_dir / "report.json").is_file()
                )
            return False

        progress = _learning_progress(self.bundle)
        completed_keys = progress["completed_event_keys"]
        next_key = progress["next_event_key"]
        areas = self.bundle.spec["areas"]
        flat = _flatten_slices(self.bundle)
        if screen == "intro":
            return index == 0 and not completed_keys
        if screen == "slice":
            return (
                0 <= index < len(flat)
                and subject_id == flat[index]
                and next_key == f"slice_completed:{flat[index]}"
            )
        if screen == "checkpoint":
            return (
                0 <= index < len(areas)
                and subject_id == areas[index]["area_id"]
                and next_key == f"checkpoint_answered:{areas[index]['area_id']}"
            )
        if screen == "checkpoint_feedback":
            return (
                0 <= index < len(areas)
                and subject_id == areas[index]["area_id"]
                and bool(completed_keys)
                and completed_keys[-1]
                == f"checkpoint_answered:{areas[index]['area_id']}"
            )
        if screen == "report":
            return (
                progress["complete"]
                and index == len(areas) - 1
                and subject_id == areas[-1]["area_id"]
                and (self.bundle.phase_dir / "report.json").is_file()
            )
        return False

    def _rebuild_checkpoint(self) -> dict[str, Any]:
        if self.bundle.phase in {"assessment", "review"}:
            questions = self.bundle.spec["questions"]
            progress = core.response_completion_state(
                self.bundle.phase_dir, self.bundle.spec
            )
            completed = progress["completed"]
            sealed = (
                core.validate_batch_manifest(
                    self.bundle.phase_dir, self.bundle.spec
                )
                is not None
            )
            if completed == 0:
                if sealed:
                    return {
                        "screen": "question",
                        "index": 0,
                        "subject_id": questions[0]["question_id"],
                    }
                return {"screen": "intro", "index": 0}
            if progress["complete"]:
                if (self.bundle.phase_dir / "report.json").is_file():
                    return {
                        "screen": "report",
                        "index": len(questions) - 1,
                        "subject_id": questions[-1]["question_id"],
                    }
                return {
                    "screen": "feedback",
                    "index": len(questions) - 1,
                    "subject_id": questions[-1]["question_id"],
                }
            previous = questions[completed - 1]
            return {
                "screen": "feedback",
                "index": completed - 1,
                "subject_id": previous["question_id"],
            }

        progress = _learning_progress(self.bundle)
        areas = self.bundle.spec["areas"]
        flat = _flatten_slices(self.bundle)
        completed_keys = progress["completed_event_keys"]
        if not completed_keys:
            return {"screen": "intro", "index": 0}
        if progress["complete"]:
            last_area = areas[-1]
            if (self.bundle.phase_dir / "report.json").is_file():
                return {
                    "screen": "report",
                    "index": len(areas) - 1,
                    "subject_id": last_area["area_id"],
                }
            return {
                "screen": "checkpoint_feedback",
                "index": len(areas) - 1,
                "subject_id": last_area["area_id"],
            }
        last_key = completed_keys[-1]
        if last_key.startswith("checkpoint_answered:"):
            area_id = last_key.split(":", 1)[1]
            area_index = next(
                index for index, area in enumerate(areas) if area["area_id"] == area_id
            )
            return {
                "screen": "checkpoint_feedback",
                "index": area_index,
                "subject_id": area_id,
            }
        next_key = progress["next_event_key"]
        if next_key and next_key.startswith("slice_completed:"):
            slice_id = next_key.split(":", 1)[1]
            return {
                "screen": "slice",
                "index": flat.index(slice_id),
                "subject_id": slice_id,
            }
        if next_key and next_key.startswith("checkpoint_answered:"):
            area_id = next_key.split(":", 1)[1]
            area_index = next(
                index for index, area in enumerate(areas) if area["area_id"] == area_id
            )
            return {
                "screen": "checkpoint",
                "index": area_index,
                "subject_id": area_id,
            }
        raise UiError("Unable to reconstruct Learning position")

    def _checkpoint(self) -> dict[str, Any]:
        if self.checkpoint_path.is_file():
            try:
                value = core.read_json_object(self.checkpoint_path)
            except core.SpecError:
                value = {}
            allowed_screens = {
                "assessment": {"intro", "question", "feedback", "report"},
                "review": {"intro", "question", "feedback", "report"},
                "learning": {
                    "intro",
                    "slice",
                    "checkpoint",
                    "checkpoint_feedback",
                    "report",
                },
            }[self.bundle.phase]
            if (
                value.get("schema_version") == 3
                and value.get("cycle_id") == self.bundle.cycle["cycle_id"]
                and value.get("phase") == self.bundle.phase
                and value.get("screen") in allowed_screens
                and isinstance(value.get("index"), int)
                and not isinstance(value.get("index"), bool)
                and self._checkpoint_consistent(value)
            ):
                return value
        return self._rebuild_checkpoint()

    def start(self, payload: Mapping[str, Any]) -> str:
        self._require_request_id(payload)
        with self._mutex:
            state = self._checkpoint()
            if state["screen"] == "intro":
                if self.bundle.phase == "learning":
                    core.validate_choice_description_contract(self.bundle.spec)
                    first = _flatten_slices(self.bundle)[0]
                    self._save_checkpoint("slice", 0, first)
                else:
                    core.ensure_batch_manifest(
                        self.bundle.phase_dir, self.bundle.spec
                    )
                    self._save_checkpoint("question", 0, self.bundle.spec["questions"][0]["question_id"])
            return self.render()

    def scope_action(self, payload: Mapping[str, Any]) -> str:
        self._require_request_id(payload)
        action = payload.get("action")
        if action not in {"adjust_scope", "pause"}:
            raise UiError("Unknown scope action")
        with self._mutex:
            if self.bundle.phase != "assessment" or self._checkpoint()["screen"] != "intro":
                raise UiError("Scope actions are available only before Assessment starts")
            self.stop_requested = True
            return render_scope_exit(self.bundle, str(action), self.nonce)

    def answer(self, payload: Mapping[str, Any]) -> str:
        request_id = self._require_request_id(payload)
        with self._mutex:
            question_id = self._subject_for_token(
                self._question_tokens, payload.get("question_token")
            )
            if question_id is None:
                raise UiError("Stale or future question token")
            question = next(
                item for item in self.bundle.spec["questions"] if item["question_id"] == question_id
            )
            selected = self._option_for_token(
                self._option_tokens[question_id], payload.get("option_token")
            )
            if selected is None:
                raise UiError("Unknown option token")
            displayed_order = [
                option["id"] for _, option in self._option_tokens[question_id]
            ]
            response_path = (
                self.bundle.phase_dir / "responses" / f"{question_id}.json"
            )
            if response_path.is_file():
                core.record_response(
                    self.bundle.phase_dir,
                    self.bundle.spec,
                    question_id,
                    selected["id"],
                    displayed_order,
                    request_id,
                )
                return self.render()
            state = self._checkpoint()
            if state.get("screen") != "question":
                raise UiError("Answer is not available in the current state")
            index = int(state.get("index", 0))
            if self.bundle.spec["questions"][index]["question_id"] != question_id:
                raise UiError("Stale or future question token")
            core.record_response(
                self.bundle.phase_dir,
                self.bundle.spec,
                question["question_id"],
                selected["id"],
                displayed_order,
                request_id,
            )
            self._save_checkpoint("feedback", index, question["question_id"])
            return self.render()

    def next(self, payload: Mapping[str, Any]) -> str:
        self._require_request_id(payload)
        with self._mutex:
            question_id = self._subject_for_token(
                self._next_tokens, payload.get("next_token")
            )
            if question_id is None:
                raise UiError("Stale or future next token")
            questions = self.bundle.spec["questions"]
            token_index = next(
                index for index, item in enumerate(questions) if item["question_id"] == question_id
            )
            response_path = self.bundle.phase_dir / "responses" / f"{question_id}.json"
            if not response_path.is_file():
                raise UiError("Committed answer is missing")
            state = self._checkpoint()
            if state.get("screen") in {"question", "report"} and int(
                state.get("index", 0)
            ) > token_index:
                return self.render()
            if state.get("screen") == "report" and token_index == len(questions) - 1:
                return self.render()
            if state.get("screen") != "feedback":
                raise UiError("Next is not available in the current state")
            index = int(state.get("index", 0))
            question = questions[index]
            if question["question_id"] != question_id:
                raise UiError("Stale or future next token")
            if index + 1 < len(questions):
                next_question = questions[index + 1]
                self._save_checkpoint("question", index + 1, next_question["question_id"])
            else:
                self._persist_batch_report()
                self._save_checkpoint("report", index, question["question_id"])
            return self.render()

    def complete_slice(self, payload: Mapping[str, Any]) -> str:
        request_id = self._require_request_id(payload)
        with self._mutex:
            if self.bundle.phase != "learning" or self.bundle.slices is None:
                raise UiError("Slice completion is unavailable")
            slice_id = self._subject_for_token(
                self._slice_tokens, payload.get("slice_token")
            )
            if slice_id is None:
                raise UiError("Stale or future slice token")
            event_path = (
                self.bundle.phase_dir
                / "events"
                / f"slice_completed.{slice_id}.json"
            )
            if event_path.is_file():
                core.record_slice_completion(
                    self.bundle.phase_dir,
                    self.bundle.spec,
                    self.bundle.slices,
                    slice_id,
                    request_id,
                )
                return self.render()
            state = self._checkpoint()
            if state.get("screen") != "slice":
                raise UiError("Slice completion is not available in the current state")
            flat = _flatten_slices(self.bundle)
            index = int(state.get("index", 0))
            if flat[index] != slice_id:
                raise UiError("Stale or future slice token")
            core.record_slice_completion(
                self.bundle.phase_dir,
                self.bundle.spec,
                self.bundle.slices,
                slice_id,
                request_id,
            )
            area_index = next(
                position
                for position, area in enumerate(self.bundle.spec["areas"])
                if slice_id in area["slice_ids"]
            )
            area = self.bundle.spec["areas"][area_index]
            if slice_id == area["slice_ids"][-1]:
                self._save_checkpoint("checkpoint", area_index, area["area_id"])
            else:
                next_slice = flat[index + 1]
                self._save_checkpoint("slice", index + 1, next_slice)
            return self.render()

    def answer_checkpoint(self, payload: Mapping[str, Any]) -> str:
        request_id = self._require_request_id(payload)
        with self._mutex:
            if self.bundle.phase != "learning":
                raise UiError("Learning checkpoint is unavailable")
            area_id = self._subject_for_token(
                self._learning_question_tokens, payload.get("question_token")
            )
            if area_id is None:
                raise UiError("Stale or future checkpoint token")
            area = next(
                item for item in self.bundle.spec["areas"] if item["area_id"] == area_id
            )
            selected = self._option_for_token(
                self._learning_option_tokens[area_id], payload.get("option_token")
            )
            if selected is None:
                raise UiError("Unknown checkpoint option token")
            displayed_order = [
                option["id"] for _, option in self._learning_option_tokens[area_id]
            ]
            event_path = (
                self.bundle.phase_dir
                / "events"
                / f"checkpoint_answered.{area_id}.json"
            )
            if event_path.is_file():
                core.record_checkpoint_response(
                    self.bundle.phase_dir,
                    self.bundle.spec,
                    area_id,
                    selected["id"],
                    displayed_order,
                    request_id,
                    slices=self.bundle.slices or {},
                )
                return self.render()
            state = self._checkpoint()
            if state.get("screen") != "checkpoint":
                raise UiError("Checkpoint answer is not available in the current state")
            area_index = int(state.get("index", 0))
            if self.bundle.spec["areas"][area_index]["area_id"] != area_id:
                raise UiError("Stale or future checkpoint token")
            core.record_checkpoint_response(
                self.bundle.phase_dir,
                self.bundle.spec,
                area_id,
                selected["id"],
                displayed_order,
                request_id,
                slices=self.bundle.slices or {},
            )
            self._save_checkpoint("checkpoint_feedback", area_index, area_id)
            return self.render()

    def next_checkpoint(self, payload: Mapping[str, Any]) -> str:
        self._require_request_id(payload)
        with self._mutex:
            if self.bundle.phase != "learning":
                raise UiError("Learning checkpoint is unavailable")
            area_id = self._subject_for_token(
                self._learning_next_tokens, payload.get("next_token")
            )
            if area_id is None:
                raise UiError("Stale or future checkpoint-next token")
            area_index = next(
                index
                for index, area in enumerate(self.bundle.spec["areas"])
                if area["area_id"] == area_id
            )
            event_path = self.bundle.phase_dir / "events" / f"checkpoint_answered.{area_id}.json"
            if not event_path.is_file():
                raise UiError("Committed checkpoint answer is missing")
            state = self._checkpoint()
            if state.get("screen") in {"slice", "report"} and int(
                state.get("index", 0)
            ) > area_index:
                return self.render()
            if state.get("screen") == "report" and area_index == len(
                self.bundle.spec["areas"]
            ) - 1:
                return self.render()
            if state.get("screen") != "checkpoint_feedback":
                raise UiError("Checkpoint next is not available in the current state")
            area = self.bundle.spec["areas"][area_index]
            if state.get("subject_id") != area_id:
                raise UiError("Stale or future checkpoint-next token")
            if area_index + 1 < len(self.bundle.spec["areas"]):
                next_area = self.bundle.spec["areas"][area_index + 1]
                next_slice = next_area["slice_ids"][0]
                flat_index = _flatten_slices(self.bundle).index(next_slice)
                self._save_checkpoint("slice", flat_index, next_slice)
            else:
                core.build_learning_report(
                    self.bundle.phase_dir,
                    self.bundle.spec,
                    slices=self.bundle.slices or {},
                    persist=True,
                )
                self._save_checkpoint("report", area_index, area["area_id"])
            return self.render()

    def view_slice(self, slice_id: str) -> str:
        with self._mutex:
            if self.bundle.phase != "learning" or self.bundle.slices is None:
                raise UiError("Learning slice is unavailable")
            if not core.ID_RE.fullmatch(slice_id) or slice_id not in self.bundle.slices:
                raise UiError("Unknown learning slice")
            state = _learning_progress(self.bundle)
            completed = set(state["completed_slice_ids"])
            current = self._checkpoint().get("subject_id", "")
            if slice_id not in completed and slice_id != current:
                raise UiError("Learning slice is still locked")
            return render_learning_slice(
                self.bundle,
                slice_id,
                self.csrf,
                self._slice_tokens[slice_id],
                self.nonce,
                reviewing=slice_id in completed or slice_id != current,
            )

    def _persist_batch_report(self) -> dict[str, Any]:
        if self.bundle.phase == "assessment":
            return core.build_assessment_report(
                self.bundle.phase_dir, self.bundle.spec, persist=True
            )
        if self.bundle.phase == "review":
            assert self.bundle.assessment_report is not None
            return core.build_review_report(
                self.bundle.phase_dir,
                self.bundle.spec,
                self.bundle.assessment_report,
                self.bundle.learning_report,
                persist=True,
            )
        raise UiError("Batch report is unavailable for this phase")

    @staticmethod
    def _require_request_id(payload: Mapping[str, Any]) -> str:
        value = payload.get("request_id")
        if not isinstance(value, str) or not REQUEST_ID_RE.fullmatch(value):
            raise UiError("Invalid request_id")
        return value

    def render(self) -> str:
        with self._mutex:
            state = self._checkpoint()
            if self.bundle.phase == "assessment" and state["screen"] == "intro":
                return render_assessment_intro(self.bundle, self.csrf, self.nonce)
            if self.bundle.phase == "review" and state["screen"] == "intro":
                return render_review_intro(self.bundle, self.csrf, self.nonce)
            if self.bundle.phase == "learning":
                if state["screen"] == "intro":
                    return render_learning_intro(self.bundle, self.csrf, self.nonce)
                if state["screen"] == "slice":
                    flat = _flatten_slices(self.bundle)
                    index = max(0, min(int(state.get("index", 0)), len(flat) - 1))
                    slice_id = flat[index]
                    return render_learning_slice(
                        self.bundle,
                        slice_id,
                        self.csrf,
                        self._slice_tokens[slice_id],
                        self.nonce,
                    )
                if state["screen"] == "checkpoint":
                    area_index = max(
                        0,
                        min(int(state.get("index", 0)), len(self.bundle.spec["areas"]) - 1),
                    )
                    area = self.bundle.spec["areas"][area_index]
                    return render_learning_checkpoint(
                        self.bundle,
                        area_index,
                        self.csrf,
                        self._learning_question_tokens[area["area_id"]],
                        self._learning_option_tokens[area["area_id"]],
                        self.nonce,
                    )
                if state["screen"] == "checkpoint_feedback":
                    area_index = max(
                        0,
                        min(int(state.get("index", 0)), len(self.bundle.spec["areas"]) - 1),
                    )
                    area = self.bundle.spec["areas"][area_index]
                    path = self.bundle.phase_dir / "events" / f"checkpoint_answered.{area['area_id']}.json"
                    return render_learning_checkpoint_feedback(
                        self.bundle,
                        area_index,
                        core.read_json_object(path),
                        self.csrf,
                        self._learning_next_tokens[area["area_id"]],
                        self.nonce,
                    )
                if state["screen"] == "report":
                    report = core.build_learning_report(
                        self.bundle.phase_dir,
                        self.bundle.spec,
                        slices=self.bundle.slices or {},
                        persist=True,
                    )
                    return render_learning_report(self.bundle, report, self.nonce)
                raise UiError(f"Unsupported learning UI state: {state['screen']}")
            if self.bundle.phase not in {"assessment", "review"}:
                raise UiError("Unsupported phase")
            questions = self.bundle.spec["questions"]
            index = max(0, min(int(state.get("index", 0)), len(questions) - 1))
            question = questions[index]
            if state["screen"] == "question":
                return render_batch_question(
                    self.bundle,
                    question,
                    index,
                    self.csrf,
                    self._question_tokens[question["question_id"]],
                    self._option_tokens[question["question_id"]],
                    self.nonce,
                )
            if state["screen"] == "feedback":
                path = self.bundle.phase_dir / "responses" / f"{question['question_id']}.json"
                record = core.read_json_object(path)
                return render_batch_feedback(
                    self.bundle,
                    question,
                    record,
                    index,
                    self.csrf,
                    self._next_tokens[question["question_id"]],
                    self.nonce,
                )
            if state["screen"] == "report":
                report = self._persist_batch_report()
                if self.bundle.phase == "assessment":
                    return render_assessment_report(self.bundle, report, self.nonce)
                return render_review_report(self.bundle, report, self.nonce)
            raise UiError(f"Unsupported UI state: {state['screen']}")


def make_handler(runtime: SessionRuntime) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "MasterySession/3.0"

        def _headers(self, status: int, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", f"default-src 'none'; style-src 'nonce-{runtime.nonce}'; script-src 'nonce-{runtime.nonce}'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()

        def _send(self, body: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
            encoded = body.encode("utf-8")
            self._headers(status, content_type, len(encoded))
            self.wfile.write(encoded)

        def _host_allowed(self) -> bool:
            host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]").lower()
            return host in {"127.0.0.1", "localhost", "::1"}

        def _origin_allowed(self) -> bool:
            if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
                return False
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            expected = f"http://{self.headers.get('Host', '').lower()}"
            return hmac.compare_digest(origin.rstrip("/").lower(), expected)

        def _touch_activity(self) -> None:
            tracker = getattr(self.server, "activity_timeout", None)
            if tracker is not None:
                tracker.touch()

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_allowed():
                self._send("Host rejected", 403, "text/plain; charset=utf-8")
                return
            self._touch_activity()
            if self.path.startswith("/slice/"):
                try:
                    self._send(runtime.view_slice(self.path[len("/slice/") :]))
                except (core.SpecError, core.IncompletePhaseError, UiError) as exc:
                    self._send(f"無法載入學習節點：{_esc(exc)}", 409)
                return
            if self.path != "/":
                self._send("Not found", 404, "text/plain; charset=utf-8")
                return
            try:
                self._send(runtime.render())
            except (core.SpecError, core.IncompletePhaseError, UiError) as exc:
                self._send(f"無法載入目前階段：{_esc(exc)}", 409)
            except OSError as exc:
                self._send(f"儲存系統暫時無法使用：{_esc(exc)}", 500)

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_allowed():
                self._send("Host rejected", 403, "text/plain; charset=utf-8")
                return
            if not self._origin_allowed():
                self._send("Origin rejected", 403, "text/plain; charset=utf-8")
                return
            if not _same_token(self.headers.get("X-Mastery-Token"), runtime.csrf):
                self._send("CSRF rejected", 403, "text/plain; charset=utf-8")
                return
            self._touch_activity()
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._send("JSON required", 415, "text/plain; charset=utf-8")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send("Invalid body length", 400, "text/plain; charset=utf-8")
                return
            if size < 0 or size > MAX_BODY_BYTES:
                self._send("Body too large", 413, "text/plain; charset=utf-8")
                return
            try:
                payload = json.loads(self.rfile.read(size).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
                actions: dict[str, Callable[[Mapping[str, Any]], str]] = {
                    "/start": runtime.start,
                    "/scope-action": runtime.scope_action,
                    "/answer": runtime.answer,
                    "/next": runtime.next,
                    "/complete": runtime.complete_slice,
                    "/checkpoint-answer": runtime.answer_checkpoint,
                    "/checkpoint-next": runtime.next_checkpoint,
                }
                action = actions.get(self.path)
                if action is None:
                    self._send("Not found", 404, "text/plain; charset=utf-8")
                    return
                page = action(payload)
                self._send(page)
                if runtime.stop_requested or runtime._checkpoint().get("screen") == "report":
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
            except core.ConflictError as exc:
                self._send(f"Conflict: {_esc(exc)}", 409, "text/plain; charset=utf-8")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, core.SpecError, core.IncompletePhaseError, UiError) as exc:
                self._send(f"Request rejected: {_esc(exc)}", 400, "text/plain; charset=utf-8")
            except OSError as exc:
                self._send(
                    f"Storage unavailable: {_esc(exc)}",
                    500,
                    "text/plain; charset=utf-8",
                )

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


class ActivityTimeout:
    """Reset a server shutdown deadline after every accepted local request."""

    def __init__(self, server: ThreadingHTTPServer, seconds: int):
        self.server = server
        self.seconds = seconds
        self._timer: threading.Timer | None = None
        self._mutex = threading.Lock()

    def touch(self) -> None:
        if self.seconds <= 0:
            return
        with self._mutex:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.seconds, self.server.shutdown)
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        with self._mutex:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


def _validate_phase_state(bundle: SessionBundle) -> dict[str, Any]:
    core.validate_phase_write_surface(
        bundle.cycle_dir, bundle.phase_dir, bundle.phase
    )
    if bundle.phase in {"assessment", "review"}:
        manifest = core.validate_batch_manifest(bundle.phase_dir, bundle.spec)
        progress = core.response_completion_state(bundle.phase_dir, bundle.spec)
        if progress["complete"]:
            return progress
        core.validate_visible_context_contract(
            bundle.spec,
            _cycle_visible_choice_context(bundle.cycle),
            allow_plain_option_labels=True,
        )
        if manifest is None:
            core.validate_choice_description_contract(bundle.spec)
        else:
            core.validate_choice_label_contract(
                bundle.spec, check_future_surfaces=False
            )
        return progress
    progress = core.learning_completion_state(
        bundle.phase_dir,
        bundle.spec,
        slices=bundle.slices or {},
    )
    if not progress["complete"]:
        core.validate_visible_context_contract(
            bundle.spec,
            _learning_visible_choice_context(bundle),
            allow_plain_option_labels=True,
        )
    if not progress["completed_event_keys"]:
        core.validate_choice_description_contract(bundle.spec)
    elif not progress["complete"]:
        core.validate_choice_label_contract(
            bundle.spec, check_future_surfaces=False
        )
    return progress


def command_validate(workspace: Path, cycle_ref: str, phase: str) -> int:
    bundle = load_phase_bundle(workspace, cycle_ref, phase)
    progress = _validate_phase_state(bundle)
    result = {
        "ok": True,
        "schema_version": 3,
        "cycle_id": bundle.cycle["cycle_id"],
        "phase": phase,
    }
    if phase in {"assessment", "review"}:
        result["questions"] = len(bundle.spec["questions"])
        result["answered"] = progress["completed"]
        result["complete"] = progress["complete"]
    if phase == "learning":
        result["areas"] = len(bundle.spec["areas"])
        result["slices"] = sum(len(area["slice_ids"]) for area in bundle.spec["areas"])
        result["completed_slices"] = progress["completed_slices"]
        result["complete"] = progress["complete"]
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _create_server(runtime: SessionRuntime, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(runtime))
    # server_close() must join live request handlers before the PhaseLock exits.
    server.daemon_threads = False
    server.block_on_close = True
    return server


def command_serve(
    workspace: Path,
    cycle_ref: str,
    phase: str,
    port: int,
    idle_timeout: int,
) -> int:
    bundle = load_phase_bundle(workspace, cycle_ref, phase)
    with core.PhaseLock(bundle.cycle_dir, phase):
        _validate_phase_state(bundle)
        runtime = SessionRuntime(bundle)
        server = _create_server(runtime, port)
        activity_timeout = ActivityTimeout(server, idle_timeout)
        setattr(server, "activity_timeout", activity_timeout)
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        print(
            json.dumps(
                {
                    "ready": True,
                    "schema_version": 3,
                    "cycle_id": bundle.cycle["cycle_id"],
                    "phase": phase,
                    "url": url,
                    "idle_timeout_seconds": idle_timeout,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        activity_timeout.touch()
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass
        finally:
            activity_timeout.cancel()
            server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate or serve a Mastery Loop v3 phase.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "serve"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--workspace", required=True)
        subparser.add_argument("--cycle", required=True)
        subparser.add_argument("--phase", required=True, choices=sorted(core.PHASES))
        if name == "serve":
            subparser.add_argument("--port", type=int, default=0)
            subparser.add_argument("--idle-timeout", type=int, default=1800)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        raw_workspace = Path(args.workspace).expanduser()
        workspace = core.resolve_within(raw_workspace, raw_workspace)
        if args.command == "validate":
            return command_validate(workspace, args.cycle, args.phase)
        return command_serve(
            workspace,
            args.cycle,
            args.phase,
            args.port,
            args.idle_timeout,
        )
    except (core.SpecError, core.ConflictError, core.IncompletePhaseError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
