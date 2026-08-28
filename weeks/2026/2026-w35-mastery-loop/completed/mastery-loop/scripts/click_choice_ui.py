#!/usr/bin/env python3
"""Serve one mouse-first Mastery Loop question with immediate feedback.

The server binds to loopback, records one committed answer without overwrite,
and keeps a wrong-answer page alive until the learner explicitly records the
mistake as a Review seed. It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


QUESTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
KINDS = {"intent", "knowledge", "action", "confirmation"}
MODES = {"learn", "audit", "review"}
QUESTION_FAMILIES = {
    "recognition",
    "explanation",
    "prediction",
    "application",
    "critique",
    "compare",
    "threshold",
    "tradeoff",
    "transfer",
    "counterevidence",
    "postmortem",
    "calibration",
    "sequence",
}
MODE_LABELS = {"learn": "學習", "audit": "評估", "review": "複習"}
KIND_LABELS = {
    "intent": "目標選擇",
    "knowledge": "知識檢核",
    "action": "下一步",
    "confirmation": "確認",
}


class SpecError(ValueError):
    """Raised when a question specification violates the click contract."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def resolve_within(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SpecError(f"Path must stay inside workspace: {resolved}") from exc
    return resolved


def nonempty_string(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise SpecError(f"{field} exceeds {maximum} characters")
    return value


def optional_string(value: Any, field: str, maximum: int) -> str:
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise SpecError(f"{field} must be a string")
    value = value.strip()
    if len(value) > maximum:
        raise SpecError(f"{field} exceeds {maximum} characters")
    return value


def validate_spec(data: dict[str, Any]) -> dict[str, Any]:
    schema_version = data.get("schema_version", 1)
    if schema_version not in {1, 2}:
        raise SpecError("schema_version must be 1 or 2")

    question_id = nonempty_string(data.get("question_id"), "question_id", 128)
    if not QUESTION_ID_RE.fullmatch(question_id):
        raise SpecError("question_id contains unsupported characters")

    kind = data.get("kind")
    if kind not in KINDS:
        raise SpecError(f"kind must be one of: {', '.join(sorted(KINDS))}")
    mode = data.get("mode", "learn")
    if mode not in MODES:
        raise SpecError(f"mode must be one of: {', '.join(sorted(MODES))}")
    if mode == "review" and schema_version < 2:
        raise SpecError("review questions require schema_version 2")

    title = nonempty_string(data.get("title"), "title", 120)
    prompt = nonempty_string(data.get("prompt"), "prompt", 1200)
    concept_id = optional_string(data.get("concept_id"), "concept_id", 128)
    kernel_id = optional_string(
        data.get("knowledge_kernel_id"), "knowledge_kernel_id", 128
    )
    scenario_id = optional_string(data.get("scenario_id"), "scenario_id", 128)
    core_proposition = optional_string(
        data.get("core_proposition"), "core_proposition", 1200
    )
    scenario_context = optional_string(
        data.get("scenario_context"), "scenario_context", 1200
    )
    question_family = optional_string(
        data.get("question_family"), "question_family", 64
    )
    review_of = optional_string(data.get("review_of"), "review_of", 128)

    if question_family and question_family not in QUESTION_FAMILIES:
        raise SpecError(
            f"question_family must be one of: {', '.join(sorted(QUESTION_FAMILIES))}"
        )
    for field_name, field_value in (
        ("concept_id", concept_id),
        ("knowledge_kernel_id", kernel_id),
        ("scenario_id", scenario_id),
        ("review_of", review_of),
    ):
        if field_value and not QUESTION_ID_RE.fullmatch(field_value):
            raise SpecError(f"{field_name} contains unsupported characters")

    if kind == "knowledge" and schema_version >= 2:
        required = {
            "concept_id": concept_id,
            "knowledge_kernel_id": kernel_id,
            "scenario_id": scenario_id,
            "core_proposition": core_proposition,
            "scenario_context": scenario_context,
            "question_family": question_family,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise SpecError(
                "version 2 knowledge questions require: " + ", ".join(missing)
            )
    if kind != "knowledge" and any(
        (concept_id, kernel_id, scenario_id, core_proposition, scenario_context, review_of)
    ):
        raise SpecError("Knowledge metadata is only valid for kind: knowledge")
    if mode == "review" and not review_of:
        raise SpecError("review questions require review_of")
    if mode != "review" and review_of:
        raise SpecError("review_of is only valid in review mode")

    options = data.get("options")
    if not isinstance(options, list):
        raise SpecError("options must be an array")
    if kind == "intent" and len(options) != 3:
        raise SpecError("intent questions require exactly 3 options")
    if kind == "knowledge" and not 3 <= len(options) <= 5:
        raise SpecError("knowledge questions require 3 to 5 options")
    if kind in {"action", "confirmation"} and not 2 <= len(options) <= 5:
        raise SpecError("action and confirmation questions require 2 to 5 options")

    cleaned_options: list[dict[str, str]] = []
    option_ids: set[str] = set()
    for index, option in enumerate(options):
        if not isinstance(option, dict):
            raise SpecError(f"options[{index}] must be an object")
        option_id = nonempty_string(option.get("id"), f"options[{index}].id", 128)
        if not QUESTION_ID_RE.fullmatch(option_id):
            raise SpecError(f"options[{index}].id contains unsupported characters")
        if option_id in option_ids:
            raise SpecError(f"Duplicate option id: {option_id}")
        option_ids.add(option_id)
        explanation = optional_string(
            option.get("explanation"), f"options[{index}].explanation", 1600
        )
        if kind == "knowledge" and schema_version >= 2 and not explanation:
            raise SpecError(
                f"options[{index}].explanation is required for version 2 knowledge questions"
            )
        cleaned_options.append(
            {
                "id": option_id,
                "label": nonempty_string(
                    option.get("label"), f"options[{index}].label", 240
                ),
                "description": optional_string(
                    option.get("description"), f"options[{index}].description", 600
                ),
                "explanation": explanation,
                "misconception_tag": optional_string(
                    option.get("misconception_tag"),
                    f"options[{index}].misconception_tag",
                    120,
                ),
            }
        )

    correct = data.get("correct_option_ids", [])
    if not isinstance(correct, list) or any(not isinstance(item, str) for item in correct):
        raise SpecError("correct_option_ids must be an array of option IDs")
    if len(set(correct)) != len(correct):
        raise SpecError("correct_option_ids contains duplicates")
    unknown_correct = set(correct) - option_ids
    if unknown_correct:
        raise SpecError(f"Unknown correct option IDs: {sorted(unknown_correct)}")
    if kind == "knowledge" and len(correct) != 1:
        raise SpecError("single-select knowledge questions require exactly 1 correct option")
    if kind != "knowledge" and correct:
        raise SpecError("Only knowledge questions may define correct_option_ids")

    return {
        "schema_version": schema_version,
        "question_id": question_id,
        "kind": kind,
        "mode": mode,
        "title": title,
        "prompt": prompt,
        "concept_id": concept_id,
        "knowledge_kernel_id": kernel_id,
        "scenario_id": scenario_id,
        "core_proposition": core_proposition,
        "scenario_context": scenario_context,
        "question_family": question_family,
        "review_of": review_of,
        "options": cleaned_options,
        "correct_option_ids": correct,
    }


def review_record_path_for(workspace: Path, question_id: str) -> Path:
    directory = workspace / "review-records"
    directory.mkdir(parents=True, exist_ok=True)
    return resolve_within(workspace, directory / f"{question_id}.json")


def answer_path_for(workspace: Path, question_id: str) -> Path:
    directory = workspace / "choice-sessions"
    directory.mkdir(parents=True, exist_ok=True)
    return resolve_within(workspace, directory / f"{question_id}.answer.json")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SpecError(f"Expected an object in {path}")
    return data


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_review_source(workspace: Path, spec: dict[str, Any]) -> None:
    if spec["mode"] != "review":
        return
    source_path = review_record_path_for(workspace, spec["review_of"])
    if not source_path.is_file():
        raise SpecError(f"Review source not found: {source_path}")
    try:
        source = read_json(source_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecError(f"Invalid review source: {source_path}") from exc
    if source.get("record_type") != "review_seed":
        raise SpecError("review_of must point to a review_seed record")
    for field in (
        "knowledge_kernel_id",
        "scenario_id",
        "core_proposition",
        "scenario_context",
    ):
        if spec[field] != source.get(field):
            raise SpecError(f"Review must preserve source {field}")
    if spec["question_family"] == source.get("source_question_family"):
        raise SpecError("Review must change question_family")
    if normalize_text(spec["prompt"]) == normalize_text(str(source.get("source_prompt", ""))):
        raise SpecError("Review must change the prompt")
    source_ids = {str(item.get("id")) for item in source.get("source_options", [])}
    new_ids = {item["id"] for item in spec["options"]}
    if source_ids & new_ids:
        raise SpecError("Review must use new option IDs")
    source_labels = {
        normalize_text(str(item.get("label", ""))) for item in source.get("source_options", [])
    }
    new_labels = {normalize_text(item["label"]) for item in spec["options"]}
    if source_labels & new_labels:
        raise SpecError("Review must rewrite every option label")
    source_misconception = str(
        source.get("selected_option", {}).get("misconception_tag") or ""
    )
    if source_misconception:
        new_wrong_tags = {
            item["misconception_tag"]
            for item in spec["options"]
            if item["id"] not in spec["correct_option_ids"]
        }
        if source_misconception not in new_wrong_tags:
            raise SpecError("Review must re-probe the recorded misconception tag")
    source_position = source.get("source_correct_position")
    new_position = spec["correct_option_ids"] and [
        item["id"] for item in spec["options"]
    ].index(spec["correct_option_ids"][0])
    if source_position == new_position:
        raise SpecError("Review must rotate the correct-option position")


def load_spec(workspace: Path, spec_arg: str) -> tuple[Path, dict[str, Any]]:
    candidate = Path(spec_arg)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    spec_path = resolve_within(workspace, candidate)
    if not spec_path.is_file():
        raise SpecError(f"Spec file not found: {spec_path}")
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SpecError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SpecError("Spec root must be an object")
    spec = validate_spec(data)
    validate_review_source(workspace, spec)
    return spec_path, spec


STYLE = """
:root{color-scheme:light;--ivory:#F1EFE7;--ink:#111111;--purple:#7432FF;--purple-dark:#5B20E6;--lime:#DFF813;--white:#FFFFFF;--gray-100:#EAE9E2;--gray-300:#C9C8C1;--gray-600:#6B6B68;--focus:#1877F2;--success:#18A76B;--error:#DB1B1B;--shadow:0 8px 24px rgba(17,17,17,.12);--display:"Italiana","Iowan Old Style",Georgia,serif;--body:"Noto Sans TC","PingFang TC","Microsoft JhengHei","Segoe UI",sans-serif;--signal:"Roboto Condensed","Arial Narrow","Noto Sans TC",sans-serif}
*{box-sizing:border-box}html{background:var(--ivory)}body{margin:0;min-height:100vh;background:var(--ivory);color:var(--ink);font-family:var(--body);-webkit-font-smoothing:antialiased}.page{min-height:100vh;display:flex;flex-direction:column}.masthead{width:min(960px,calc(100% - 32px));margin:0 auto;padding:24px 0 16px;display:flex;align-items:baseline;justify-content:space-between;gap:16px;border-bottom:1px solid var(--gray-300)}.brand{margin:0;font-family:var(--display);font-size:28px;line-height:1;letter-spacing:-.025em}.mode{font-family:var(--signal);font-size:13px;font-weight:700;letter-spacing:.04em;color:var(--gray-600)}.stage{width:min(760px,calc(100% - 32px));margin:auto;padding:48px 0 64px}.sheet{background:var(--white);border:1px solid var(--gray-300);border-radius:12px;padding:clamp(24px,5vw,48px);box-shadow:var(--shadow)}.kicker{margin:0 0 8px;color:var(--purple);font-family:var(--signal);font-size:14px;font-weight:800;letter-spacing:.025em}h1{margin:0 0 16px;max-width:18ch;font-size:clamp(30px,6vw,52px);line-height:1.05;letter-spacing:-.03em;text-wrap:balance}h2{margin:0 0 8px;font-size:20px;line-height:1.3;letter-spacing:-.015em}.prompt{margin:0 0 32px;max-width:72ch;color:#3e3e3b;font-size:18px;line-height:1.7}.choice-list{border:1px solid var(--gray-300);border-radius:7px;overflow:hidden;background:var(--white)}.option{appearance:none;width:100%;min-height:72px;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px;text-align:left;color:var(--ink);background:var(--white);border:0;border-bottom:1px solid var(--gray-100);border-radius:0;cursor:pointer;transition:background-color 180ms ease-out,box-shadow 180ms ease-out}.option:last-child{border-bottom:0}.option:hover{background:#faf8ff}.option[aria-pressed="true"]{color:var(--ink);background:#f3eeff;box-shadow:inset 0 0 0 2px var(--purple)}.choice-copy{display:grid;gap:4px}.label{font-size:17px;font-weight:760;line-height:1.4}.description{color:var(--gray-600);font-size:14px;line-height:1.55}.option[aria-pressed="true"] .description{color:#3e3e3b}.choice-mark{flex:0 0 24px;width:24px;height:24px;display:grid;place-items:center;border:1px solid currentColor;border-radius:50%;opacity:.36;font-weight:900}.option[aria-pressed="true"] .choice-mark{color:var(--ink);background:var(--lime);border-color:var(--purple);opacity:1}.actions{display:flex;justify-content:flex-end;margin-top:24px}.primary{min-height:48px;padding:12px 20px;border:0;border-radius:4px;background:var(--purple);color:var(--white);font-family:var(--body);font-size:15px;font-weight:800;cursor:pointer;transition:background-color 180ms ease-out,transform 180ms ease-out,box-shadow 180ms ease-out}.primary:hover{background:var(--purple-dark);transform:translateY(-1px);box-shadow:0 6px 16px rgba(91,32,230,.2)}.primary:disabled{cursor:not-allowed;opacity:.45;transform:none;box-shadow:none}.primary.record{width:100%}.status{min-height:24px;margin:12px 0 0;color:var(--gray-600);font-size:14px;line-height:1.5}.result-band{margin:-48px -48px 32px;padding:32px 48px 28px;border-radius:12px 12px 0 0;background:var(--lime);color:var(--ink)}.result-band.error{background:#fff4f4;color:var(--ink);border-bottom:1px solid var(--error)}.result-band.error .result-label{color:var(--error)}.result-label{margin:0 0 8px;font-family:var(--signal);font-size:14px;font-weight:800}.result-band h1{margin:0;max-width:none}.answer-section{display:grid;gap:0;margin:24px 0;border-top:1px solid var(--gray-300);border-bottom:1px solid var(--gray-300)}.answer-row{padding:20px 0}.answer-row+.answer-row{border-top:1px solid var(--gray-100)}.answer-tag{margin:0 0 8px;color:var(--gray-600);font-family:var(--signal);font-size:13px;font-weight:800}.answer-row.wrong .answer-tag{color:var(--error)}.answer-row.correct .answer-tag{color:var(--success)}.answer-title{margin:0 0 8px;font-size:18px;font-weight:800;line-height:1.45}.explanation{margin:0;max-width:72ch;color:#3e3e3b;font-size:16px;line-height:1.75}.core{margin:24px 0;padding:16px;background:var(--ivory);border-radius:7px;color:#343431;font-size:14px;line-height:1.65}.next{margin:24px 0 0;padding-top:20px;border-top:1px solid var(--gray-300);color:var(--gray-600);font-size:15px;line-height:1.65}.record-copy{margin:0 0 16px;color:#3e3e3b;font-size:15px;line-height:1.65}.footer{width:min(960px,calc(100% - 32px));margin:0 auto;padding:24px 16px;border-top:1px solid var(--gray-300);color:var(--gray-600);font-size:12px;text-align:center}.wordmark{font-family:var(--display);font-size:14px;color:var(--ink)}button:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
@media(max-width:640px){.masthead{padding-top:18px}.stage{padding:28px 0 40px}.sheet{padding:24px 20px}.result-band{margin:-24px -20px 24px;padding:24px 20px 22px}.prompt{font-size:16px}.option{min-height:68px;padding:14px}.actions,.primary{width:100%}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition-duration:.01ms!important;animation-duration:.01ms!important;animation-iteration-count:1!important}}
"""


def render_page(title: str, mode: str, body: str, script: str = "") -> str:
    script_markup = "<script>(()=>{" + script + "})();</script>" if script else ""
    return (
        '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>"
        '<div class="page"><header class="masthead"><p class="brand">Mastery Loop</p>'
        f'<span class="mode">{html.escape(MODE_LABELS.get(mode, mode))}</span></header>'
        f'<div class="stage">{body}</div>'
        '<footer class="footer" aria-label="Created by Winston"><span>Created by </span><span class="wordmark">Winston</span></footer></div>'
        f"{script_markup}</body></html>"
    )


def render_question(
    spec: dict[str, Any], csrf_token: str, browser_options: dict[str, dict[str, str]]
) -> str:
    option_markup = []
    for token, option in browser_options.items():
        description = ""
        if option["description"]:
            description = f'<span class="description">{html.escape(option["description"])}</span>'
        option_markup.append(
            '<button class="option" type="button" aria-pressed="false" '
            f'data-option-token="{html.escape(token, quote=True)}">'
            '<span class="choice-copy">'
            f'<span class="label">{html.escape(option["label"])}</span>{description}'
            '</span><span class="choice-mark" aria-hidden="true">✓</span></button>'
        )
    body = (
        '<main class="sheet">'
        f'<p class="kicker">{html.escape(KIND_LABELS[spec["kind"]])}</p>'
        f'<h1>{html.escape(spec["title"])}</h1>'
        f'<p class="prompt">{html.escape(spec["prompt"])}</p>'
        f'<section class="choice-list" aria-label="可選項目">{"".join(option_markup)}</section>'
        '<div class="actions"><button class="primary" id="commit" type="button" disabled>提交答案</button></div>'
        '<p class="status" id="status" role="status" aria-live="polite"></p></main>'
    )
    script = """
const token=__TOKEN__;const buttons=[...document.querySelectorAll('.option')];
const commit=document.querySelector('#commit');const status=document.querySelector('#status');let selected=null;
for(const button of buttons){button.addEventListener('click',()=>{selected=button.dataset.optionToken;for(const item of buttons)item.setAttribute('aria-pressed',String(item===button));commit.disabled=false;status.textContent='';});}
commit.addEventListener('click',async()=>{if(!selected)return;commit.disabled=true;status.textContent='正在提交並整理解析…';try{const response=await fetch('/answer',{method:'POST',headers:{'Content-Type':'application/json','X-Choice-Token':token},body:JSON.stringify({option_token:selected})});if(!response.ok)throw new Error(await response.text());const nextPage=await response.text();document.open();document.write(nextPage);document.close();}catch(error){status.textContent='提交失敗。請保留此頁，回到 Codex 後再試一次。';commit.disabled=false;}});
""".replace("__TOKEN__", json.dumps(csrf_token))
    return render_page(spec["title"], spec["mode"], body, script)


def feedback_text(option: dict[str, str], is_correct: bool) -> str:
    if option["explanation"]:
        return option["explanation"]
    if is_correct:
        return "這個選項符合此題目前採用的判準。回到 Codex 後可查看完整來源與推理。"
    return "這個選項未通過此題目前採用的判準。記錄後，系統會安排後續複習。"


def render_feedback(spec: dict[str, Any], selected_id: str, csrf_token: str) -> str:
    option_map = {option["id"]: option for option in spec["options"]}
    selected = option_map[selected_id]
    correct = option_map[spec["correct_option_ids"][0]]
    is_correct = selected_id == correct["id"]
    if is_correct:
        band_class, result_label, result_title = (
            "result-band",
            "回答正確",
            "這個判斷站得住腳",
        )
        rows = (
            '<section class="answer-section"><div class="answer-row correct">'
            '<p class="answer-tag">你的答案・正確</p>'
            f'<p class="answer-title">{html.escape(correct["label"])}</p>'
            f'<p class="explanation">{html.escape(feedback_text(correct, True))}</p>'
            "</div></section>"
        )
        action = (
            '<p class="next"><strong>這一題已完成。</strong><br>'
            "可以關閉此頁，回到 Codex 進入下一步。</p>"
        )
        script = "document.querySelector('#result-title')?.focus();"
    else:
        band_class, result_label, result_title = (
            "result-band error",
            "需要再校準",
            "先把這個錯誤留下來",
        )
        rows = (
            '<section class="answer-section"><div class="answer-row wrong">'
            '<p class="answer-tag">你的答案・錯誤</p>'
            f'<p class="answer-title">{html.escape(selected["label"])}</p>'
            f'<p class="explanation">{html.escape(feedback_text(selected, False))}</p></div>'
            '<div class="answer-row correct"><p class="answer-tag">正確答案</p>'
            f'<p class="answer-title">{html.escape(correct["label"])}</p>'
            f'<p class="explanation">{html.escape(feedback_text(correct, True))}</p>'
            "</div></section>"
        )
        action = (
            '<p class="record-copy">按下「記錄這個錯誤」，系統會把核心命題、情境與誤解加入複習佇列。</p>'
            '<button class="primary record" id="record" type="button">記錄這個錯誤</button>'
            '<p class="status" id="status" role="status" aria-live="polite"></p>'
        )
        script = """
document.querySelector('#result-title')?.focus();const token=__TOKEN__;const record=document.querySelector('#record');const status=document.querySelector('#status');
record.addEventListener('click',async()=>{record.disabled=true;status.textContent='正在加入複習佇列…';try{const response=await fetch('/record',{method:'POST',headers:{'Content-Type':'application/json','X-Choice-Token':token},body:'{}'});if(!response.ok)throw new Error(await response.text());const nextPage=await response.text();document.open();document.write(nextPage);document.close();}catch(error){status.textContent='記錄失敗。請保留此頁，回到 Codex 後再試一次。';record.disabled=false;}});
""".replace("__TOKEN__", json.dumps(csrf_token))
    core = ""
    if spec["core_proposition"]:
        core = (
            '<p class="core"><strong>這題在檢查：</strong> '
            + html.escape(spec["core_proposition"])
            + "</p>"
        )
    body = (
        f'<main class="sheet"><header class="{band_class}">'
        f'<p class="result-label">{result_label}</p><h1 id="result-title" tabindex="-1">{result_title}</h1></header>'
        f"{rows}{core}{action}</main>"
    )
    return render_page(result_label, spec["mode"], body, script)


def render_selection_recorded(spec: dict[str, Any], selected: dict[str, str]) -> str:
    body = (
        '<main class="sheet"><header class="result-band"><p class="result-label">選擇已記錄</p>'
        '<h1>已收到你的決定</h1></header><section class="answer-section">'
        '<div class="answer-row correct"><p class="answer-tag">已選擇</p>'
        f'<p class="answer-title">{html.escape(selected["label"])}</p></div></section>'
        '<p class="next">可以關閉此頁，回到 Codex 進入下一步。</p></main>'
    )
    return render_page("選擇已記錄", spec["mode"], body)


def render_review_recorded(spec: dict[str, Any]) -> str:
    body = (
        '<main class="sheet"><header class="result-band"><p class="result-label">已加入複習</p>'
        '<h1>錯誤已記錄</h1></header>'
        '<p class="prompt">下一次複習會保留同一個核心命題與情境，並改用新的題型、問法與選項重新檢核。</p>'
        '<p class="next"><strong>記錄完成。</strong><br>可以關閉此頁，回到 Codex 進入下一步。</p></main>'
    )
    return render_page("錯誤已記錄", spec["mode"], body)


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def build_answer(spec: dict[str, Any], selected: dict[str, str]) -> dict[str, Any]:
    is_correct = (
        selected["id"] in spec["correct_option_ids"]
        if spec["kind"] == "knowledge"
        else None
    )
    answered_at = utc_now()
    feedback_exposed = spec["mode"] in {"learn", "review"}
    return {
        "schema_version": 2,
        "question_id": spec["question_id"],
        "kind": spec["kind"],
        "mode": spec["mode"],
        "concept_id": spec["concept_id"] or None,
        "knowledge_kernel_id": spec["knowledge_kernel_id"] or None,
        "scenario_id": spec["scenario_id"] or None,
        "question_family": spec["question_family"] or None,
        "review_of": spec["review_of"] or None,
        "displayed_option_order": [option["id"] for option in spec["options"]],
        "selected_option_id": selected["id"],
        "selected_misconception_tag": selected["misconception_tag"] or None,
        "is_correct": is_correct,
        "independence": "feedback_exposed" if feedback_exposed else "independent",
        "feedback_exposed": feedback_exposed,
        "feedback_available": spec["kind"] == "knowledge",
        "feedback_timing": (
            "immediate_after_commit" if spec["kind"] == "knowledge" else "not_scored"
        ),
        "requires_review_record": is_correct is False,
        "answered_at": answered_at,
    }


def build_review_record(
    spec: dict[str, Any], selected: dict[str, str], correct: dict[str, str]
) -> dict[str, Any]:
    correct_position = [item["id"] for item in spec["options"]].index(correct["id"])
    return {
        "schema_version": 1,
        "record_type": "review_seed",
        "status": "due",
        "question_id": spec["question_id"],
        "root_question_id": spec["review_of"] or spec["question_id"],
        "source_mode": spec["mode"],
        "concept_id": spec["concept_id"] or None,
        "knowledge_kernel_id": spec["knowledge_kernel_id"] or None,
        "scenario_id": spec["scenario_id"] or None,
        "core_proposition": spec["core_proposition"] or None,
        "scenario_context": spec["scenario_context"] or None,
        "source_question_family": spec["question_family"] or None,
        "source_prompt": spec["prompt"],
        "source_correct_position": correct_position,
        "source_options": [
            {
                "id": item["id"],
                "label": item["label"],
                "description": item["description"],
                "misconception_tag": item["misconception_tag"] or None,
            }
            for item in spec["options"]
        ],
        "selected_option": {
            "id": selected["id"],
            "label": selected["label"],
            "explanation": feedback_text(selected, False),
            "misconception_tag": selected["misconception_tag"] or None,
        },
        "correct_option": {
            "id": correct["id"],
            "label": correct["label"],
            "explanation": feedback_text(correct, True),
        },
        "review_contract": {
            "preserve": [
                "knowledge_kernel_id",
                "core_proposition",
                "scenario_id",
                "scenario_context",
            ],
            "change": [
                "question_family",
                "prompt",
                "option_ids",
                "option_wording",
                "distractors",
                "correct_option_position",
            ],
        },
        "recorded_at": utc_now(),
    }


def make_handler(
    spec: dict[str, Any], answer_path: Path, review_record_path: Path, csrf_token: str
) -> type[BaseHTTPRequestHandler]:
    option_map = {option["id"]: option for option in spec["options"]}
    browser_options = {secrets.token_urlsafe(18): option for option in spec["options"]}
    question_html = render_question(spec, csrf_token, browser_options).encode("utf-8")

    class ChoiceHandler(BaseHTTPRequestHandler):
        server_version = "MasteryChoice/2.0"

        def log_message(self, format_string: str, *args: object) -> None:
            return

        def send_payload(
            self, status: int, payload: bytes, content_type: str = "text/html; charset=utf-8"
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def current_answer(self) -> dict[str, Any] | None:
            if not answer_path.exists():
                return None
            try:
                return read_json(answer_path)
            except (OSError, json.JSONDecodeError, SpecError):
                return None

        def do_GET(self) -> None:
            if self.path == "/":
                answer = self.current_answer()
                if answer and answer.get("selected_option_id") in option_map:
                    if answer.get("is_correct") is False and review_record_path.exists():
                        page = render_review_recorded(spec)
                    elif spec["kind"] == "knowledge":
                        page = render_feedback(spec, answer["selected_option_id"], csrf_token)
                    else:
                        page = render_selection_recorded(
                            spec, option_map[answer["selected_option_id"]]
                        )
                    self.send_payload(200, page.encode("utf-8"))
                    return
                self.send_payload(200, question_html)
                return
            if self.path == "/health":
                self.send_payload(200, b'{"ok":true}', "application/json")
                return
            self.send_payload(404, b"Not found", "text/plain; charset=utf-8")

        def parse_post(self) -> dict[str, Any] | None:
            if self.headers.get("X-Choice-Token") != csrf_token:
                self.send_payload(403, b"Invalid choice token", "text/plain; charset=utf-8")
                return None
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 2 or length > 4096:
                self.send_payload(400, b"Invalid request size", "text/plain; charset=utf-8")
                return None
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_payload(400, b"Invalid JSON", "text/plain; charset=utf-8")
                return None
            if not isinstance(body, dict):
                self.send_payload(400, b"Invalid JSON object", "text/plain; charset=utf-8")
                return None
            return body

        def do_POST(self) -> None:
            if self.path == "/answer":
                self.handle_answer()
            elif self.path == "/record":
                self.handle_record()
            else:
                self.send_payload(404, b"Not found", "text/plain; charset=utf-8")

        def handle_answer(self) -> None:
            body = self.parse_post()
            if body is None:
                return
            selected = browser_options.get(body.get("option_token"))
            if selected is None:
                self.send_payload(400, b"Unknown option", "text/plain; charset=utf-8")
                return
            try:
                write_json_once(answer_path, build_answer(spec, selected))
            except FileExistsError:
                self.send_payload(409, b"Answer already exists", "text/plain; charset=utf-8")
                return
            if spec["kind"] == "knowledge":
                page = render_feedback(spec, selected["id"], csrf_token)
                waits_for_record = selected["id"] not in spec["correct_option_ids"]
            else:
                page = render_selection_recorded(spec, selected)
                waits_for_record = False
            self.send_payload(200, page.encode("utf-8"))
            if not waits_for_record:
                threading.Thread(target=self.server.shutdown, daemon=True).start()

        def handle_record(self) -> None:
            body = self.parse_post()
            if body is None:
                return
            if body:
                self.send_payload(400, b"Record body must be empty", "text/plain; charset=utf-8")
                return
            answer = self.current_answer()
            if not answer or answer.get("is_correct") is not False:
                self.send_payload(409, b"No wrong answer to record", "text/plain; charset=utf-8")
                return
            selected_id = answer.get("selected_option_id")
            if selected_id not in option_map or not spec["correct_option_ids"]:
                self.send_payload(409, b"Answer state is incomplete", "text/plain; charset=utf-8")
                return
            selected = option_map[selected_id]
            correct = option_map[spec["correct_option_ids"][0]]
            try:
                write_json_once(
                    review_record_path, build_review_record(spec, selected, correct)
                )
            except FileExistsError:
                pass
            self.send_payload(200, render_review_recorded(spec).encode("utf-8"))
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    return ChoiceHandler


def command_validate(workspace: Path, spec_arg: str) -> int:
    spec_path, spec = load_spec(workspace, spec_arg)
    print(
        json.dumps(
            {
                "valid": True,
                "schema_version": spec["schema_version"],
                "spec": str(spec_path),
                "question_id": spec["question_id"],
                "kind": spec["kind"],
                "mode": spec["mode"],
                "options": len(spec["options"]),
                "correct_options": len(spec["correct_option_ids"]),
                "immediate_feedback": spec["kind"] == "knowledge",
                "review_of": spec["review_of"] or None,
            },
            ensure_ascii=False,
        )
    )
    return 0


def command_serve(workspace: Path, spec_arg: str, port: int, idle_timeout: int) -> int:
    _, spec = load_spec(workspace, spec_arg)
    answer_path = answer_path_for(workspace, spec["question_id"])
    review_path = review_record_path_for(workspace, spec["question_id"])
    status = "ready"
    if answer_path.exists():
        answer = read_json(answer_path)
        pending_record = answer.get("is_correct") is False and not review_path.exists()
        if not pending_record:
            raise SpecError(f"Question is already complete; use a new question_id: {answer_path}")
        status = "resume_record"
    csrf_token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(
        ("127.0.0.1", port), make_handler(spec, answer_path, review_path, csrf_token)
    )
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(
        json.dumps(
            {
                "status": status,
                "url": url,
                "question_id": spec["question_id"],
                "answer_path": str(answer_path),
                "review_record_path": str(review_path),
                "idle_timeout_seconds": idle_timeout,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    timer = None
    if idle_timeout > 0:
        timer = threading.Timer(idle_timeout, server.shutdown)
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if timer is not None:
            timer.cancel()
        server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mastery Loop local click-choice UI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "serve"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--workspace", required=True, help="Learning workspace root")
        sub.add_argument("--spec", required=True, help="Spec JSON inside the workspace")
        if name == "serve":
            sub.add_argument("--port", type=int, default=0, help="Loopback port")
            sub.add_argument(
                "--idle-timeout",
                type=int,
                default=900,
                help="Seconds before an abandoned page shuts down; 0 disables",
            )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise SpecError(f"Workspace directory not found: {workspace}")
    if args.command == "validate":
        return command_validate(workspace, args.spec)
    if args.idle_timeout < 0:
        raise SpecError("idle-timeout must be 0 or greater")
    return command_serve(workspace, args.spec, args.port, args.idle_timeout)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SpecError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
