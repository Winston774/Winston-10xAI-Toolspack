#!/usr/bin/env python3
"""Pure-data core for Mastery Loop v3 sessions.

This module owns validation, immutable evidence records, derived reports, and
the learning-completion gate.  It intentionally contains no HTTP or HTML code
so the local UI can be tested independently from the evidence model.
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import os
import re
import secrets
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
PHASES = {"assessment", "learning", "review"}
GOAL_INTENTS = {"end_to_end_delivery", "diagnose_improve", "review_teach"}
BENCHMARK_STATUSES = {"verified", "partially_verified", "provisional"}
V3_ARTIFACT_PATHS = {
    "assessment_spec": "assessment/spec.json",
    "assessment_report": "assessment/report.json",
    "learning_path": "learning/path.json",
    "learning_report": "learning/report.json",
    "review_spec": "review/spec.json",
    "review_report": "review/report.json",
}
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
DIFFICULTIES = {"foundation", "core", "advanced"}
SIGNAL_LABELS = {
    "stable_signal": "穩定訊號",
    "mixed_signal": "混合訊號",
    "needs_support": "待補強",
}
ANSWER_REVEAL_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:正確|正解|最佳|標準)(?:的)?\s*(?:答案|選項|作法|做法|方案|策略)",
        r"(?:這|此)(?:一|個)?選項.{0,16}(?:正確|最佳|最符合)",
        r"符合.{0,16}(?:本題|這一題|題意|核心命題|正確判準)",
        r"(?:完整|完全)(?:回答|符合|滿足).{0,16}(?:本題|這一題|題目|問題|命題)",
        r"(?:首選|推薦|建議採用|最合適|最恰當)(?:的)?\s*(?:答案|選項|作法|做法|方案|策略)",
        r"(?:這|此)(?:個|一個)?(?:答案|選項|作法|做法|方案|策略)?.{0,8}(?:應|該|應該)(?:被)?(?:選擇|選取|採用)",
        r"(?:應|該|應該)(?:選擇|選取|採用).{0,8}(?:這|此)(?:個|一個)?(?:答案|選項|作法|做法|方案|策略)?",
        r"(?:請|直接)(?:選|選擇|選取|採用)(?:這|此)(?:個|一個|項)?(?:答案|選項|作法|做法|方案|策略)?",
        r"答案.{0,4}(?:就在|就是|位於)(?:這|此)(?:個|一個|項)?(?:答案|選項|作法|做法|方案|策略)?",
        r"(?:它|這|此).{0,4}(?:就是|即為)(?:正確)?答案(?:[。！!；;]|$)",
        r"唯一.{0,8}(?:合理|可行|有效|安全|符合).{0,8}(?:答案|選項|作法|做法|方案|策略)",
        r"\b(?:correct|right|best|ideal|preferred|recommended)\s+(?:answer|option|choice|approach|action|response|solution|strategy)\b",
        r"\bthis\s+one\s+is\s+(?:correct|right|best|preferred)\b",
        r"\b(?:correct|right|best|preferred)\s+one\b",
        r"(?:這|此)(?:一)?個才?(?:對|正確|最好)",
        r"\bthis\s+(?:answer|option|choice|approach|action|response|solution|strategy)\s+(?:is|should\s+be|must\s+be)\s+(?:correct|right|best|preferred|recommended|selected|chosen|used)\b",
        r"\bshould\s+be\s+(?:selected|chosen)\b",
        r"\b(?:select|choose)\s+(?:this|the)\s+(?:answer|option|choice|approach|action|response|solution|strategy)\b",
        r"\b(?:select|choose|pick)\s+(?:this|the)(?:\s+(?:answer|option|choice|approach|action|response|solution|strategy))?\b",
        r"\b(?:select|choose|pick)\s+me\b",
        r"(?:選|選擇|選取|採用)我(?:[。！!；;]|$)",
        r"\bthis\s+is\s+(?:the\s+)?(?:(?:correct|right|best|preferred|recommended)\s+)?(?:answer|option|choice)\b",
        r"\b(?:only|uniquely)\s+(?:defensible|valid|acceptable|safe)\s+(?:answer|option|choice|approach|action|response|solution|strategy)\b",
        r"\bmatches?\s+(?:this|the)\s+(?:question|prompt|core proposition|answer key)\b",
        r"\bfully\s+(?:answers|satisfies)\s+(?:this|the)\s+(?:question|prompt|proposition)\b",
        r"\b(?:meets?|satisfies|fulfills?|matches?|answers?|aligns?\s+with).{0,24}(?:prompt|question|stated\s+(?:condition|criterion|requirement))\b",
        r"(?:符合|滿足|回答|對齊).{0,16}(?:本題|題目|問題|題述|所述)(?:條件|判準|要求)?",
        r"\bthe\s+answer\b|^\s*answer\s*[.!;:]?\s*$",
        r"^\s*(?:答案|正解)\s*[。！!；;]?\s*$",
        r"\b(?:status|result|grade|score|verdict)\s*[:=\-]\s*(?:pass(?:ed)?|fail(?:ed)?|correct|incorrect|right|wrong|full\s+credit|perfect(?:\s+score)?)\b",
        r"\b(?:earns?|gets?|receives?|deserves?)\s+(?:full\s+credit|a\s+perfect\s+score)\b",
        r"\b(?:meets?|satisfies?)\s+(?:all|every)\s+(?:stated\s+)?(?:requirement|requirements|condition|conditions|criterion|criteria|prerequisite|prerequisites|gate|gates)\b",
        r"\b(?:all|every)\s+(?:stated\s+)?(?:requirement|requirements|condition|conditions|criterion|criteria|prerequisite|prerequisites|gate|gates)\s+(?:is|are|has\s+been|have\s+been)?\s*(?:met|satisfied|passed)\b",
        r"\b(?:no|without)\s+(?:remaining\s+|unresolved\s+)?(?:gap|gaps|omission|omissions)\b",
        r"^\s*(?:pass(?:ed)?|fail(?:ed)?|full\s+credit|perfect\s+score)\s*[.!]?\s*$",
        r"\b(?:earns?|gets?|receives?|deserves?)\s+(?:the\s+)?(?:maximum|highest|perfect)\s+(?:score|grade|credit)\b",
        r"\b(?:guaranteed|certain|sure)\s+to\s+pass\b",
        r"(?:狀態|結果|評分|成績|判定)\s*[:：=—-]?\s*(?:通過|合格|不合格|正確|錯誤|滿分|零分)",
        r"(?:可|會|應)?(?:得|獲得|拿到)\s*(?:滿分|完整分數|全分)",
        r"(?:保證|必定|肯定|一定)(?:可以|會)?(?:通過|合格|得分)",
        r"(?:獲得|拿到|得到)(?:最高|最佳)(?:分數|評分|成績)",
        r"(?:全部|所有|每個).{0,8}(?:條件|要求|判準|前提|門檻).{0,8}(?:皆|均|都)?(?:已)?(?:滿足|符合|通過|成立)",
        r"(?:沒有|無)(?:任何)?(?:未解決|尚未處理|剩餘)?(?:的)?(?:缺口|遺漏)",
        r"(?:這|此)(?:個)?(?:說法|選項|答案|作法|做法|方案|策略)?.{0,8}(?:已)?(?:涵蓋|包含).{0,12}(?:題目|問題)?.{0,8}(?:所有|全部)(?:必要)?(?:機制|要點|條件|要求|面向)",
        r"(?:已)?(?:全面|完整地|完全|綜合地)(?:涵蓋|包含|回答|滿足).{0,16}(?:題目|問題|要求|機制|要點|條件)",
        r"\b(?:covers?|includes?)\s+(?:all|every)\s+(?:required\s+|necessary\s+)?(?:mechanism|mechanisms|point|points|condition|conditions|requirement|requirements|aspect|aspects)\b",
        r"\b(?:comprehensively|completely|fully)\s+(?:covers?|includes?|answers?|satisfies?)\b",
        r"^\s*(?:通過|合格|不合格|滿分|零分)\s*[。！!]?\s*$",
        r"[✅✔☑⭐🌟🏆💯👍🎯❌✗✘🚫]",
    )
)
QUESTION_ANSWER_REVEAL_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:the\s+)?(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|[a-e])\s+(?:answer|option|choice|response|approach)\s+(?:is|would\s+be|must\s+be)\s+(?:the\s+)?(?:correct|right|best|preferred|recommended)\b",
        r"\b(?:correct|right|best|preferred|recommended)\s+(?:answer|option|choice|response|approach)\s+(?:is|would\s+be)\s+(?:the\s+)?(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|[a-e])\b",
        r"\b(?:answer|option|choice|response|approach)\s*(?:[a-e]|[1-5])\s+(?:is|would\s+be|must\s+be)\s+(?:the\s+)?(?:correct|right|best|preferred|recommended)\b",
        r"\b(?:answer|option|choice|response|approach)\s*(?:[a-e]|[1-5])\b.{0,32}\b(?:answer|correct|right|best|preferred|recommended|full\s+credit|pass(?:ed)?)\b",
        r"第\s*[一二三四五1-5]\s*(?:個|項)?\s*(?:答案|選項|作法|做法|方案|策略).{0,8}(?:是|為|即為).{0,4}(?:正確|正解|最佳|首選|推薦)",
        r"(?:正確|正解|最佳|首選|推薦)(?:的)?\s*(?:答案|選項|作法|做法|方案|策略).{0,8}(?:是|為|即為)\s*第\s*[一二三四五1-5]",
        r"(?:答案|選項|作法|做法|方案|策略)\s*[A-Ea-e1-5].{0,8}(?:是|為|即為).{0,4}(?:正確|正解|最佳|首選|推薦)",
        r"(?:答案|選項|作法|做法|方案|策略)\s*[A-Ea-e1-5].{0,24}(?:答案|正確|正解|最佳|首選|推薦|滿分|通過)",
        r"\b(?:answer|option|choice|response|approach)\s+(?:shown\s+|listed\s+|presented\s+|displayed\s+)?(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+(?:earns?|gets?|receives?|deserves?|is)\s+(?:the\s+)?(?:correct|right|best|preferred|recommended|full\s+credit)\b",
        r"\b(?:the\s+)?(?:top|uppermost|bottom|last|leftmost|rightmost)\s+(?:answer|option|choice|response|approach)\s+(?:is|contains?|earns?|gets?|receives?)\s+(?:the\s+)?(?:answer|correct|right|best|preferred|recommended|full\s+credit)\b",
        r"(?:最上方|最下方|最左側|最右側|最後)(?:的)?(?:答案|選項|作法|做法|方案|策略).{0,8}(?:是|為|即為|包含).{0,4}(?:答案|正確|正解|最佳|首選|推薦)",
    )
)
BOUNDARY_SIGNAL_PATTERN = re.compile(
    r"\b(?:only|but|unless|except|without|before|after|requires?|depends?|remains?|unresolved|outside|separate|excludes?|omits?|limited|boundary|prerequisite|tradeoff|condition|scope)\b|"
    r"(?:只|僅|但|尚未|未涵蓋|不含|除非|需要|必須|前提|條件|取捨|代價|限制|邊界|遺漏|仍|才|若|依賴|適用範圍|另行|之外)",
    re.IGNORECASE,
)
VISIBLE_CONTEXT_ANSWER_CUE_PATTERN = re.compile(
    r"\b(?:answer\s+key|correct\s+answer|right\s+answer|best\s+(?:answer|option)|preferred\s+choice|select\s+this|choose\s+this)\b|"
    r"\b(?:correct|right|best)\s*[:=\-]|"
    r"(?:答案\s*(?:是|為|[:：])|(?:正確|正解|最佳)\s*[:：=]|正確答案|正確選項|最佳答案|最佳選項|請選這個)",
    re.IGNORECASE,
)
OWN_LABEL_CUE_PATTERN = re.compile(
    r"\b(?:required\s+next\s+action|proceed\s+with|use|select|choose|pick|avoid|reject|exclude|do\s+not\s+choose)\b|"
    r"(?:下一步|採用|選擇|選取|避免|不要選|排除|拒絕)",
    re.IGNORECASE,
)
ANSWER_LIKE_LABEL_PATTERN = re.compile(
    r"\b(?:use|validate|verify|block|inspect|continue|infer|apply|run|stop|choose|select|calculate|compare|confirm|publish|retry)\b|"
    r"(?:先|應|必須|需要|檢查|驗證|阻擋|執行|採用|選擇|推論|判斷|依據|比較|計算|確認|發布|重試)",
    re.IGNORECASE,
)
SHORT_STABLE_TOKEN_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
}


class SpecError(ValueError):
    """Raised when a v3 specification violates the session contract."""


class ConflictError(RuntimeError):
    """Raised when immutable state already exists with different intent."""


class IncompletePhaseError(RuntimeError):
    """Raised when a derived report requires a phase that is not complete."""


class IncompleteLearningError(IncompletePhaseError):
    """Raised when Review is requested before every learning gate is complete."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _nonempty(value: Any, field: str, maximum: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{field} must be a non-empty string")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise SpecError(f"{field} exceeds {maximum} characters")
    return cleaned


def _optional(value: Any, field: str, maximum: int = 2000) -> str:
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise SpecError(f"{field} must be a string")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise SpecError(f"{field} exceeds {maximum} characters")
    return cleaned


def _rfc3339(value: Any, field: str) -> str:
    cleaned = _nonempty(value, field, 100)
    try:
        parsed = dt.datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SpecError(f"{field} must be an RFC-3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SpecError(f"{field} must include a timezone")
    return cleaned


def _identifier(value: Any, field: str) -> str:
    cleaned = _nonempty(value, field, 128)
    if not ID_RE.fullmatch(cleaned):
        raise SpecError(f"{field} contains unsupported characters")
    return cleaned


def _string_list(
    value: Any,
    field: str,
    *,
    minimum: int = 0,
    maximum: int = 100,
    item_maximum: int = 2000,
) -> list[str]:
    if not isinstance(value, list):
        raise SpecError(f"{field} must be an array")
    if not minimum <= len(value) <= maximum:
        raise SpecError(f"{field} must contain {minimum} to {maximum} items")
    result = [_nonempty(item, f"{field}[{index}]", item_maximum) for index, item in enumerate(value)]
    if len(set(result)) != len(result):
        raise SpecError(f"{field} contains duplicates")
    return result


def _id_list(
    value: Any, field: str, *, minimum: int = 0, maximum: int = 100
) -> list[str]:
    result = _string_list(value, field, minimum=minimum, maximum=maximum, item_maximum=128)
    for item in result:
        if not ID_RE.fullmatch(item):
            raise SpecError(f"{field} contains an invalid ID: {item}")
    return result


def _security_normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    )


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalize_security_text(value: str) -> str:
    return " ".join(_security_normalize(value).casefold().split())


def _normalize_choice_surface(value: str) -> str:
    return re.sub(
        r"[\W_]+", "", _security_normalize(value).casefold(), flags=re.UNICODE
    )


def _normalize_phrase(value: str) -> str:
    return " ".join(
        part
        for part in re.split(
            r"[^\w]+", _security_normalize(value).casefold(), flags=re.UNICODE
        )
        if part
    )


def choice_description_leaks_answer(value: Any) -> bool:
    """Return True when visible option copy evaluates its own correctness."""

    if not isinstance(value, str) or not value.strip():
        return False
    normalized = _normalize_security_text(value)
    return any(pattern.search(normalized) for pattern in ANSWER_REVEAL_PATTERNS)


def _choice_description_has_boundary(value: str) -> bool:
    return BOUNDARY_SIGNAL_PATTERN.search(_normalize_security_text(value)) is not None


def choice_description_is_safe(label: Any, description: Any) -> bool:
    """Return True for present, non-repeated copy without correctness cues."""

    if not isinstance(label, str) or not label.strip():
        return False
    if not isinstance(description, str) or not description.strip():
        return False
    return (
        len(_normalize_choice_surface(description)) >= 4
        and _normalize_choice_surface(label) != _normalize_choice_surface(description)
        and not choice_description_leaks_answer(description)
        and _choice_description_has_boundary(description)
    )


def _question_surface_leaks_answer(value: str, question: Mapping[str, Any]) -> bool:
    """Detect pre-commit copy that points at the current scored choice."""

    normalized = _normalize_security_text(value)
    if any(pattern.search(normalized) for pattern in QUESTION_ANSWER_REVEAL_PATTERNS):
        return True

    correct_option_id = question.get("correct_option_id")
    correct_label = next(
        (
            option.get("label", "")
            for option in question.get("options", [])
            if option.get("id") == correct_option_id
        ),
        "",
    )
    if not isinstance(correct_label, str) or not correct_label.strip():
        return False
    visible_surface = _normalize_choice_surface(value)
    correct_surface = _normalize_choice_surface(correct_label)
    if visible_surface == correct_surface:
        return True
    meaningful_label = (
        len(correct_surface) >= 5
        or bool(re.search(r"[\u3400-\u9fff]", correct_label))
        and len(correct_surface) >= 4
    )
    if meaningful_label and _contains_hidden_choice_surface(value, [correct_label]):
        return True
    if not _contains_hidden_choice_surface(value, [correct_label]):
        return False
    return bool(
        re.search(
            r"\b(?:select|choose|pick|adopt)\b|"
            r"\b(?:correct|right|best|preferred|recommended)\s+"
            r"(?:answer|option|choice|response|approach)\b|"
            r"(?:選擇|選取|採用|正確答案|正解|最佳選項|首選)",
            normalized,
            re.IGNORECASE,
        )
    )


def _contains_stable_choice_token(
    value: str,
    tokens: Iterable[str],
    *,
    strict_tokens: Iterable[str] = (),
) -> str | None:
    folded = _security_normalize(value).casefold()
    strict = {_security_normalize(token).casefold() for token in strict_tokens}
    for token in tokens:
        normalized_token = _security_normalize(token).casefold()
        if len(normalized_token) <= 3 and normalized_token.isalpha():
            token_pattern = (
                rf"(?<![a-z0-9]){re.escape(normalized_token)}(?![a-z0-9])"
            )
            strong_context = (
                r"(?:\b(?:internal|identifier|id|key|token)\b|"
                r"(?:內部|識別碼|代碼))"
            )
            entity_context = (
                r"(?:\b(?:option|choice|answer|question|kernel|concept|scenario|tag)\b|"
                r"(?:選項|答案|題目|核心|概念|情境|標籤))"
            )
            relation_context = (
                r"(?:\s*(?:is|means|denotes|identifies|maps\s+to|=|:)\s*|"
                r".{0,4}(?:是|為|代表|對應).{0,4})"
            )
            if (
                normalized_token in strict
                and normalized_token not in SHORT_STABLE_TOKEN_STOPWORDS
            ):
                matched = re.search(token_pattern, folded) is not None
            else:
                matched = (
                    re.search(rf"{strong_context}.{{0,20}}{token_pattern}", folded)
                    is not None
                    or re.search(
                        rf"{token_pattern}{relation_context}.{{0,16}}{strong_context}",
                        folded,
                    )
                    is not None
                    or re.search(
                        rf"{entity_context}\s*[:=#-]?\s*{token_pattern}", folded
                    )
                    is not None
                    or re.search(
                        rf"{token_pattern}{relation_context}.{{0,16}}{entity_context}",
                        folded,
                    )
                    is not None
                )
        else:
            token_pattern = (
                rf"(?<![a-z0-9]){re.escape(normalized_token)}(?![a-z0-9])"
            )
            matched = re.search(token_pattern, folded) is not None
        if matched:
            return token
    return None


def _contains_hidden_choice_surface(value: str, hidden_values: Iterable[str]) -> bool:
    visible_phrase = _normalize_phrase(value)
    visible_compact = _normalize_choice_surface(value)
    for hidden_value in hidden_values:
        hidden_phrase = _normalize_phrase(hidden_value)
        if not hidden_phrase:
            continue
        if re.search(r"[\u3400-\u9fff]", hidden_phrase):
            hidden_compact = _normalize_choice_surface(hidden_value)
            matched = hidden_compact in visible_compact
        else:
            matched = f" {hidden_phrase} " in f" {visible_phrase} "
        if matched:
            return True
    return False


def validate_visible_context_contract(
    spec: Mapping[str, Any],
    visible_entries: Iterable[tuple[str, Any]],
    *,
    allow_plain_option_labels: bool = False,
) -> None:
    """Reject answer material embedded in phase-level visible context."""

    phase = spec.get("phase")
    if phase in {"assessment", "review"}:
        questions = list(spec.get("questions", []))
    elif phase == "learning":
        questions = [
            area.get("checkpoint", {}) for area in spec.get("areas", [])
        ]
    else:
        raise SpecError("Visible context validation requires a v3 phase spec")

    stable_tokens: set[str] = set()
    strict_tokens: set[str] = set()
    always_hidden_surfaces: list[str] = []
    plain_topic_surfaces: list[str] = []
    correct_label_surfaces: list[str] = []
    for question in questions:
        for field in (
            "question_id",
            "concept_id",
            "knowledge_kernel_id",
            "primary_kernel_id",
            "scenario_id",
            "source_question_id",
            "correct_option_id",
        ):
            value = question.get(field)
            if isinstance(value, str) and value:
                stable_tokens.add(value)
                if field == "correct_option_id":
                    strict_tokens.add(value)
        integrated = question.get("integrated_kernel_ids", [])
        if isinstance(integrated, list):
            stable_tokens.update(
                value for value in integrated if isinstance(value, str)
            )
        lineage = question.get("lineage", {})
        if isinstance(lineage, Mapping):
            for values in lineage.values():
                if isinstance(values, list):
                    stable_tokens.update(
                        value for value in values if isinstance(value, str)
                    )
        always_hidden_surfaces.extend(
            question.get(field, "")
            for field in (
                "scenario_context",
                "prompt",
                "core_proposition",
            )
        )
        plain_topic_surfaces.append(question.get("title", ""))
        for option in question.get("options", []):
            option_id = option.get("id")
            if isinstance(option_id, str) and option_id:
                stable_tokens.add(option_id)
                strict_tokens.add(option_id)
            misconception_tag = option.get("misconception_tag")
            if isinstance(misconception_tag, str) and misconception_tag:
                stable_tokens.add(misconception_tag)
                strict_tokens.add(misconception_tag)
            option_label = option.get("label", "")
            if option.get("id") == question.get("correct_option_id"):
                correct_label_surfaces.append(option_label)
            else:
                plain_topic_surfaces.append(option_label)
            always_hidden_surfaces.extend(
                option.get(field, "")
                for field in ("description", "explanation")
            )

    for field, raw_value in visible_entries:
        value = _nonempty(raw_value, field, 4000)
        if _contains_stable_choice_token(
            value, stable_tokens, strict_tokens=strict_tokens
        ) is not None:
            raise SpecError(f"{field} exposes a stable internal token")
        normalized = _normalize_security_text(value)
        if any(
            pattern.search(normalized)
            for pattern in QUESTION_ANSWER_REVEAL_PATTERNS
        ):
            raise SpecError(f"{field} reveals correctness or points to an answer")
        if _contains_hidden_choice_surface(value, always_hidden_surfaces):
            raise SpecError(f"{field} exposes hidden or future question content")
        exposes_plain_surface = _contains_hidden_choice_surface(
            value, plain_topic_surfaces
        )
        exposes_correct_label = _contains_hidden_choice_surface(
            value, correct_label_surfaces
        )
        value_surface = _normalize_choice_surface(value)
        equals_correct_label = any(
            value_surface == _normalize_choice_surface(label)
            for label in correct_label_surfaces
            if isinstance(label, str) and label.strip()
        )
        has_answer_cue = VISIBLE_CONTEXT_ANSWER_CUE_PATTERN.search(normalized)
        exposes_answer_like_label = any(
            ANSWER_LIKE_LABEL_PATTERN.search(_normalize_security_text(label))
            and _contains_hidden_choice_surface(value, [label])
            for label in correct_label_surfaces
        )
        if equals_correct_label or (
            exposes_correct_label and (has_answer_cue or exposes_answer_like_label)
        ):
            raise SpecError(f"{field} exposes hidden or future question content")
        if exposes_plain_surface and (
            not allow_plain_option_labels
            or has_answer_cue
        ):
            raise SpecError(f"{field} exposes hidden or future question content")
        if has_answer_cue and any(
            _question_surface_leaks_answer(value, question)
            for question in questions
        ):
            raise SpecError(f"{field} reveals correctness or points to an answer")


def scenario_fingerprint(value: str) -> str:
    """Return a stable semantic-surface fingerprint for scenario reuse checks."""

    normalized = _normalize_text(_nonempty(value, "scenario_context", 4000))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _content_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cycle_contract_digest(cycle: Mapping[str, Any]) -> str:
    """Bind evidence to the confirmed mission, scope, and area semantics."""

    return _content_digest(
        {
            "schema_version": cycle["schema_version"],
            "cycle_id": cycle["cycle_id"],
            "mission": cycle["mission"],
            "knowledge_scope": cycle["knowledge_scope"],
            "areas": cycle["areas"],
        }
    )


def _question_digest(question: Mapping[str, Any]) -> str:
    """Bind an evidence record to the exact normalized server-side question."""

    return _content_digest(question)


def _slice_digest(item: Mapping[str, Any]) -> str:
    """Bind completion evidence to the exact normalized Learning Slice."""

    return _content_digest(item)


def _near_duplicate(left: str, right: str, *, threshold: float = 0.84) -> bool:
    """Detect trivial scenario rewrites in addition to exact fingerprints.

    This intentionally stays conservative and deterministic. Generators remain
    responsible for semantic novelty that lexical similarity cannot detect.
    """

    return (
        difflib.SequenceMatcher(
            None, _normalize_text(left), _normalize_text(right), autojunk=False
        ).ratio()
        >= threshold
    )


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def resolve_within(root: Path, candidate: Path) -> Path:
    try:
        root = Path(root).resolve()
        resolved = Path(candidate).resolve()
    except (OSError, RuntimeError) as exc:
        raise SpecError(f"Unable to resolve contained path: {candidate}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SpecError(f"Path must stay inside workspace: {resolved}") from exc
    return resolved


def _contained_child(root: Path, *parts: str) -> Path:
    """Resolve a mutable child while following existing links safely."""

    raw_root = Path(root)
    return resolve_within(raw_root, raw_root.joinpath(*parts))


def _require_regular_or_absent(root: Path, relative: str, label: str) -> Path:
    raw = Path(root) / relative
    if raw.is_symlink():
        raise SpecError(f"{label} cannot be a symbolic link: {raw}")
    path = _contained_child(root, relative)
    if path.exists() and not path.is_file():
        raise SpecError(f"{label} must be a regular file or absent: {path}")
    return path


def _require_directory_or_absent(root: Path, relative: str, label: str) -> Path:
    raw = Path(root) / relative
    if raw.is_symlink():
        raise SpecError(f"{label} cannot be a symbolic link: {raw}")
    path = _contained_child(root, relative)
    if path.exists() and not path.is_dir():
        raise SpecError(f"{label} must be a directory or absent: {path}")
    return path


def validate_phase_write_surface(
    cycle_dir: Path, phase_dir: Path, phase: str
) -> dict[str, Path]:
    """Preflight every reserved mutable target before a server says ready."""

    if phase not in PHASES:
        raise SpecError(f"Unknown phase: {phase}")
    cycle_root = resolve_within(cycle_dir, cycle_dir)
    phase_root = resolve_within(cycle_root, phase_dir)
    if not phase_root.is_dir():
        raise SpecError(f"Phase directory not found: {phase_root}")

    result = {
        "checkpoint": _require_regular_or_absent(
            cycle_root, "checkpoint.json", "Checkpoint path"
        ),
        "lock": _require_regular_or_absent(
            cycle_root, ".cycle.lock", "Cycle lock path"
        ),
        "report": _require_regular_or_absent(
            phase_root, "report.json", "Phase report path"
        ),
    }
    if phase in {"assessment", "review"}:
        result["manifest"] = _require_regular_or_absent(
            phase_root, "batch-manifest.json", "Batch manifest path"
        )
        result["evidence_dir"] = _require_directory_or_absent(
            phase_root, "responses", "Responses path"
        )
    else:
        result["evidence_dir"] = _require_directory_or_absent(
            phase_root, "events", "Learning events path"
        )
    return result


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SpecError(f"Invalid JSON object at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SpecError(f"Expected a JSON object at {path}")
    return data


def _encoded_json(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _fsync_parent(path: Path) -> None:
    """Best-effort directory sync; Windows may reject directory descriptors."""

    try:
        descriptor = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically publish JSON through a same-directory, flushed temp file."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_encoded_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_parent(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically publish flushed JSON without ever overwriting evidence."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_encoded_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        # A same-directory hard-link publish is atomic and refuses an existing
        # destination on both Windows and POSIX. A crash can leave only a
        # complete temp file or a complete final record, never a partial final.
        os.link(temporary, path)
        _fsync_parent(path)
    finally:
        temporary.unlink(missing_ok=True)


class PhaseLock:
    """Cycle-wide OS lock that the operating system releases after a crash."""

    def __init__(self, cycle_dir: Path, phase: str):
        if phase not in PHASES:
            raise SpecError(f"Unknown phase: {phase}")
        self.phase = phase
        cycle_root = resolve_within(cycle_dir, cycle_dir)
        raw_path = Path(cycle_dir) / ".cycle.lock"
        if raw_path.is_symlink():
            raise ConflictError(f"Cycle lock cannot be a symbolic link: {raw_path}")
        self.path = resolve_within(cycle_root, raw_path)
        if self.path.exists() and not self.path.is_file():
            raise ConflictError(f"Cycle lock path is not a file: {self.path}")
        self.token = secrets.token_urlsafe(24)
        self._owned = False
        self._handle: Any = None

    @staticmethod
    def _lock(handle: Any) -> None:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(handle: Any) -> None:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _write_lock_state(handle: Any, payload: Mapping[str, Any]) -> None:
        handle.seek(0)
        handle.truncate()
        handle.write(_encoded_json(payload))
        handle.flush()
        os.fsync(handle.fileno())

    def __enter__(self) -> "PhaseLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = self.path.open("a+b")
        except OSError as exc:
            raise ConflictError(f"Phase is already locked: {self.path}") from exc
        if self.path.stat().st_size == 0:
            handle.write(b"\0")
            handle.flush()
        try:
            self._lock(handle)
        except OSError as exc:
            handle.close()
            raise ConflictError(f"Phase is already locked: {self.path}") from exc
        payload = {
            "schema_version": 3,
            "phase": self.phase,
            "token": self.token,
            "pid": os.getpid(),
            "acquired_at": utc_now(),
            "active": True,
        }
        try:
            self._write_lock_state(handle, payload)
        except Exception:
            self._unlock(handle)
            handle.close()
            raise
        self._handle = handle
        self._owned = True
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if not self._owned:
            return
        handle = self._handle
        if handle is None:
            return
        try:
            self._write_lock_state(
                handle,
                {
                    "schema_version": 3,
                    "phase": self.phase,
                    "token": self.token,
                    "pid": os.getpid(),
                    "active": False,
                    "released_at": utc_now(),
                },
            )
        finally:
            try:
                self._unlock(handle)
            finally:
                handle.close()
                self._handle = None
                self._owned = False


def validate_cycle(data: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise SpecError("cycle must be an object")
    if data.get("schema_version") != 3:
        raise SpecError("cycle schema_version must be 3")
    cycle_id = _identifier(data.get("cycle_id"), "cycle_id")

    mission = data.get("mission")
    if not isinstance(mission, Mapping):
        raise SpecError("mission must be an object")
    intent_id = _identifier(mission.get("intent_id"), "mission.intent_id")
    if intent_id not in GOAL_INTENTS:
        raise SpecError(f"mission.intent_id must be one of: {sorted(GOAL_INTENTS)}")
    normalized_mission = {
        "intent_id": intent_id,
        "ultimate_outcome": _nonempty(
            mission.get("ultimate_outcome"), "mission.ultimate_outcome", 2000
        ),
        "audience": _optional(mission.get("audience"), "mission.audience", 240),
    }

    scope = data.get("knowledge_scope")
    if not isinstance(scope, Mapping):
        raise SpecError("knowledge_scope must be an object")
    status = scope.get("benchmark_status")
    if status not in BENCHMARK_STATUSES:
        raise SpecError(
            "knowledge_scope.benchmark_status must be verified, partially_verified, or provisional"
        )
    sources = _string_list(scope.get("sources", []), "knowledge_scope.sources", maximum=100)
    if status == "verified" and not sources:
        raise SpecError("verified knowledge_scope requires at least one source")
    normalized_scope = {
        "title": _nonempty(scope.get("title"), "knowledge_scope.title", 240),
        "direction": _nonempty(scope.get("direction"), "knowledge_scope.direction", 2000),
        "includes": _string_list(
            scope.get("includes"), "knowledge_scope.includes", minimum=1, maximum=50
        ),
        "excludes": _string_list(
            scope.get("excludes"), "knowledge_scope.excludes", maximum=50
        ),
        "benchmark_status": status,
        "sources": sources,
    }

    areas = data.get("areas")
    if not isinstance(areas, list) or not 3 <= len(areas) <= 6:
        raise SpecError("cycle.areas must contain 3 to 6 areas")
    normalized_areas: list[dict[str, Any]] = []
    area_ids: set[str] = set()
    for index, area in enumerate(areas):
        if not isinstance(area, Mapping):
            raise SpecError(f"areas[{index}] must be an object")
        area_id = _identifier(area.get("area_id"), f"areas[{index}].area_id")
        if area_id in area_ids:
            raise SpecError(f"Duplicate area_id: {area_id}")
        area_ids.add(area_id)
        normalized_areas.append(
            {
                "area_id": area_id,
                "title": _nonempty(area.get("title"), f"areas[{index}].title", 240),
                "description": _nonempty(
                    area.get("description"), f"areas[{index}].description", 1200
                ),
                "weight": _bounded_number(area.get("weight", 1), f"areas[{index}].weight", 0, 10),
                "failure_cost": _bounded_number(
                    area.get("failure_cost", 1), f"areas[{index}].failure_cost", 0, 10
                ),
                "uncertainty": _bounded_number(
                    area.get("uncertainty", 1), f"areas[{index}].uncertainty", 0, 10
                ),
            }
        )

    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, Mapping):
        raise SpecError("artifacts must be an object")
    unknown_artifacts = sorted(set(artifacts) - set(V3_ARTIFACT_PATHS))
    if unknown_artifacts:
        raise SpecError(f"Unsupported version 3 artifact keys: {unknown_artifacts}")
    normalized_artifacts: dict[str, str] = dict(V3_ARTIFACT_PATHS)
    for key, value in artifacts.items():
        safe_key = _identifier(key, f"artifacts.{key}")
        normalized_value = _nonempty(value, f"artifacts.{key}", 500)
        if normalized_value != V3_ARTIFACT_PATHS[safe_key]:
            raise SpecError(
                f"Version 3 artifact {safe_key} must be {V3_ARTIFACT_PATHS[safe_key]}"
            )

    return {
        "schema_version": 3,
        "cycle_id": cycle_id,
        "mission": normalized_mission,
        "knowledge_scope": normalized_scope,
        "areas": normalized_areas,
        "artifacts": normalized_artifacts,
    }


def _bounded_number(value: Any, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecError(f"{field} must be a number")
    number = float(value)
    if not minimum <= number <= maximum:
        raise SpecError(f"{field} must be between {minimum} and {maximum}")
    return number


def resolve_cycle(workspace: Path, cycle_ref: str | Path) -> Path:
    workspace = Path(workspace).resolve()
    candidate = Path(cycle_ref)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    cycle_dir = resolve_within(workspace, candidate)
    if not cycle_dir.is_dir():
        raise SpecError(f"Cycle directory not found: {cycle_dir}")
    return cycle_dir


def load_cycle(workspace: Path, cycle_ref: str | Path) -> tuple[Path, dict[str, Any]]:
    cycle_dir = resolve_cycle(workspace, cycle_ref)
    cycle_path = cycle_dir / "cycle.json"
    if not cycle_path.is_file():
        raise SpecError(f"cycle.json not found: {cycle_path}")
    return cycle_dir, validate_cycle(read_json_object(cycle_path))


def _validate_option(option: Any, field: str) -> dict[str, str]:
    if not isinstance(option, Mapping):
        raise SpecError(f"{field} must be an object")
    return {
        "id": _identifier(option.get("id"), f"{field}.id"),
        "label": _nonempty(option.get("label"), f"{field}.label", 300),
        "description": _optional(option.get("description"), f"{field}.description", 800),
        "explanation": _nonempty(option.get("explanation"), f"{field}.explanation", 2400),
        "misconception_tag": _optional(
            option.get("misconception_tag"), f"{field}.misconception_tag", 160
        ),
    }


def validate_choice_description_contract(
    spec: Mapping[str, Any], *, check_descriptions: bool = True,
    check_future_surfaces: bool = True
) -> None:
    """Require neutral, informative pre-commit option subdescriptions.

    This gate runs before a new batch or Learning contract is sealed. Existing
    sealed v3 evidence can still resume; the UI suppresses an unsafe legacy
    description set rather than changing immutable question content.
    """

    phase = spec.get("phase")
    if phase in {"assessment", "review"}:
        question_entries = [
            (f"questions[{index}]", question)
            for index, question in enumerate(spec.get("questions", []))
        ]
    elif phase == "learning":
        question_entries = [
            (f"areas[{index}].checkpoint", area.get("checkpoint", {}))
            for index, area in enumerate(spec.get("areas", []))
        ]
    else:
        raise SpecError("Choice description validation requires a v3 phase spec")

    stable_tokens: set[str] = set()
    strict_tokens: set[str] = set()
    for _, question in question_entries:
        for field in (
            "question_id",
            "concept_id",
            "knowledge_kernel_id",
            "primary_kernel_id",
            "scenario_id",
            "source_question_id",
            "correct_option_id",
        ):
            value = question.get(field)
            if isinstance(value, str) and value:
                stable_tokens.add(value)
                if field == "correct_option_id":
                    strict_tokens.add(value)
        for field in ("integrated_kernel_ids",):
            values = question.get(field, [])
            if isinstance(values, list):
                stable_tokens.update(value for value in values if isinstance(value, str))
        lineage = question.get("lineage", {})
        if isinstance(lineage, Mapping):
            for values in lineage.values():
                if isinstance(values, list):
                    stable_tokens.update(
                        value for value in values if isinstance(value, str)
                    )
        for option in question.get("options", []):
            option_id = option.get("id")
            if isinstance(option_id, str) and option_id:
                stable_tokens.add(option_id)
                strict_tokens.add(option_id)
            misconception_tag = option.get("misconception_tag")
            if isinstance(misconception_tag, str) and misconception_tag:
                stable_tokens.add(misconception_tag)
                strict_tokens.add(misconception_tag)

    question_surface_counts = {
        field: Counter(
            _normalize_choice_surface(str(question.get(field, "")))
            for _, question in question_entries
            if question.get(field)
        )
        for field in ("title", "scenario_context", "prompt")
    }
    intro_entries: list[tuple[str, str]] = []
    for field in ("title", "instructions"):
        value = spec.get(field)
        if isinstance(value, str) and value.strip():
            intro_entries.append((field, value))
    if phase == "learning":
        intro_entries.extend(
            (f"areas[{index}].title", str(area.get("title", "")))
            for index, area in enumerate(spec.get("areas", []))
            if area.get("title")
        )
    intro_hidden_surfaces = [
        surface
        for _, question in question_entries
        for surface in [
            question.get("title", ""),
            question.get("scenario_context", ""),
            question.get("prompt", ""),
            question.get("core_proposition", ""),
            *(
                option.get(field, "")
                for option in question.get("options", [])
                for field in ("label", "description", "explanation")
            ),
        ]
    ]
    for field, value in intro_entries:
        leaked_token = _contains_stable_choice_token(
            value, stable_tokens, strict_tokens=strict_tokens
        )
        if leaked_token is not None:
            raise SpecError(f"{field} exposes a stable internal token")
        if _contains_hidden_choice_surface(value, intro_hidden_surfaces):
            raise SpecError(f"{field} exposes hidden or future question content")
        if any(
            _question_surface_leaks_answer(value, question)
            for _, question in question_entries
        ):
            raise SpecError(f"{field} reveals correctness or points to an answer")

    for question_index, (question_field, question) in enumerate(question_entries):
        current_hidden_surfaces = [
            question.get("core_proposition", ""),
            *(
                option.get("explanation", "")
                for option in question.get("options", [])
            ),
        ]
        current_question_hidden_surfaces = [
            *current_hidden_surfaces,
            *(
                option.get(field, "")
                for option in question.get("options", [])
                for field in ("label", "description")
            ),
        ]
        future_question_surfaces: list[str] = []
        future_question_surfaces_by_field: dict[str, list[str]] = {
            "title": [],
            "scenario_context": [],
            "prompt": [],
        }
        future_core_surfaces: list[str] = []
        future_option_surfaces: list[str] = []
        future_option_labels: list[str] = []
        future_option_support_surfaces: list[str] = []
        future_correct_surfaces: list[str] = []
        for _, future_question in question_entries[question_index + 1 :]:
            future_question_surfaces.extend(
                future_question.get(field, "")
                for field in (
                    "title",
                    "scenario_context",
                    "prompt",
                    "core_proposition",
                )
            )
            for field in future_question_surfaces_by_field:
                future_question_surfaces_by_field[field].append(
                    future_question.get(field, "")
                )
            future_core_surfaces.append(
                future_question.get("core_proposition", "")
            )
            for future_option in future_question.get("options", []):
                option_surfaces = [
                    future_option.get(field, "")
                    for field in ("label", "description", "explanation")
                ]
                future_option_surfaces.extend(option_surfaces)
                future_option_labels.append(option_surfaces[0])
                future_option_support_surfaces.extend(option_surfaces[1:])
                if future_option.get("id") == future_question.get(
                    "correct_option_id"
                ):
                    future_correct_surfaces.extend(option_surfaces)
        if check_future_surfaces:
            question_hidden_surfaces = [
                *current_question_hidden_surfaces,
                *future_question_surfaces,
                *future_option_surfaces,
            ]
            option_hidden_surfaces = [
                *current_hidden_surfaces,
                *future_question_surfaces,
                *future_option_surfaces,
            ]
        else:
            question_hidden_surfaces = [
                *current_hidden_surfaces,
                *future_question_surfaces,
                *future_option_labels,
                *future_option_support_surfaces,
                *future_correct_surfaces,
            ]
            option_hidden_surfaces = [
                *current_hidden_surfaces,
                *future_question_surfaces,
                *future_option_labels,
                *future_option_support_surfaces,
                *future_correct_surfaces,
            ]

        for surface_field in ("title", "scenario_context", "prompt"):
            value = _nonempty(
                question.get(surface_field), f"{question_field}.{surface_field}", 4000
            )
            if _question_surface_leaks_answer(value, question):
                raise SpecError(
                    f"{question_field}.{surface_field} reveals correctness or points to the correct answer"
                )
            leaked_token = _contains_stable_choice_token(
                value, stable_tokens, strict_tokens=strict_tokens
            )
            if leaked_token is not None:
                raise SpecError(
                    f"{question_field}.{surface_field} exposes a stable internal token"
                )
            if check_future_surfaces:
                hidden_surfaces = question_hidden_surfaces
            else:
                hidden_surfaces = [
                    *current_question_hidden_surfaces,
                    *future_core_surfaces,
                    *future_option_labels,
                    *future_option_support_surfaces,
                    *future_correct_surfaces,
                ]
                normalized_value = _normalize_choice_surface(value)
                repeated_template = (
                    question_surface_counts[surface_field][normalized_value] >= 3
                )
                for future_field, future_values in (
                    future_question_surfaces_by_field.items()
                ):
                    for future_value in future_values:
                        if (
                            repeated_template
                            and future_field == surface_field
                            and _normalize_choice_surface(future_value)
                            == normalized_value
                        ):
                            continue
                        hidden_surfaces.append(future_value)
            if _contains_hidden_choice_surface(value, hidden_surfaces):
                raise SpecError(
                    f"{question_field}.{surface_field} exposes hidden or future question content"
                )

        for option_index, option in enumerate(question.get("options", [])):
            field = f"{question_field}.options[{option_index}]"
            label = _nonempty(option.get("label"), f"{field}.label", 300)
            if choice_description_leaks_answer(label):
                raise SpecError(
                    f"{field}.label reveals correctness or recommends its own selection"
                )
            surfaces = [("label", label)]
            if check_descriptions:
                description = _nonempty(
                    option.get("description"), f"{field}.description", 800
                )
                if len(_normalize_choice_surface(description)) < 4:
                    raise SpecError(
                        f"{field}.description must contain meaningful boundary text"
                    )
                normalized_label = _normalize_choice_surface(label)
                contains_label = _contains_hidden_choice_surface(
                    description, [label]
                )
                repeats_label = (
                    _normalize_choice_surface(description) == normalized_label
                    or len(normalized_label) >= 4
                    and contains_label
                    or contains_label
                    and OWN_LABEL_CUE_PATTERN.search(
                        _normalize_security_text(description)
                    )
                )
                if repeats_label:
                    raise SpecError(
                        f"{field}.description must supplement rather than repeat its label"
                    )
                if not _choice_description_has_boundary(description):
                    raise SpecError(
                        f"{field}.description must add an explicit boundary, prerequisite, tradeoff, or omitted factor"
                    )
                if choice_description_leaks_answer(description):
                    raise SpecError(
                        f"{field}.description reveals correctness; describe only a boundary, prerequisite, tradeoff, or omitted factor"
                    )
                surfaces.append(("description", description))
            for surface_field, value in surfaces:
                leaked_token = _contains_stable_choice_token(
                    value, stable_tokens, strict_tokens=strict_tokens
                )
                if leaked_token is not None:
                    raise SpecError(
                        f"{field}.{surface_field} exposes a stable internal token"
                    )
                hidden_surfaces = [
                    *option_hidden_surfaces,
                    *(
                        other_option.get(other_field, "")
                        for other_index, other_option in enumerate(
                            question.get("options", [])
                        )
                        if other_index != option_index
                        for other_field in ("label", "description")
                    ),
                ]
                if _contains_hidden_choice_surface(value, hidden_surfaces):
                    raise SpecError(
                        f"{field}.{surface_field} exposes hidden or future question content"
                    )


def validate_choice_label_contract(
    spec: Mapping[str, Any], *, check_future_surfaces: bool = True
) -> None:
    """Reject scored labels that disclose server-only answer material."""

    validate_choice_description_contract(
        spec,
        check_descriptions=False,
        check_future_surfaces=check_future_surfaces,
    )


def _validate_question(
    question: Any,
    field: str,
    *,
    phase: str,
    area_ids: set[str],
    review: bool = False,
) -> dict[str, Any]:
    if not isinstance(question, Mapping):
        raise SpecError(f"{field} must be an object")
    question_id = _identifier(question.get("question_id"), f"{field}.question_id")
    area_id = _identifier(question.get("area_id"), f"{field}.area_id")
    if area_id not in area_ids:
        raise SpecError(f"{field}.area_id is not declared by the cycle: {area_id}")
    family = question.get("question_family")
    if family not in QUESTION_FAMILIES:
        raise SpecError(f"{field}.question_family is unsupported")
    options = question.get("options")
    if not isinstance(options, list) or not 3 <= len(options) <= 5:
        raise SpecError(f"{field}.options must contain 3 to 5 choices")
    normalized_options = [
        _validate_option(option, f"{field}.options[{index}]")
        for index, option in enumerate(options)
    ]
    option_ids = [item["id"] for item in normalized_options]
    if len(set(option_ids)) != len(option_ids):
        raise SpecError(f"{field}.options contains duplicate IDs")
    visible_labels = [_normalize_text(item["label"]) for item in normalized_options]
    visible_surfaces = [
        (_normalize_text(item["label"]), _normalize_text(item["description"]))
        for item in normalized_options
    ]
    if len(set(visible_labels)) != len(visible_labels) or len(
        set(visible_surfaces)
    ) != len(visible_surfaces):
        raise SpecError(f"{field}.options contains duplicate learner-visible choices")

    correct_value = question.get("correct_option_id")
    legacy_correct = question.get("correct_option_ids")
    if legacy_correct is not None:
        if not isinstance(legacy_correct, list) or len(legacy_correct) != 1:
            raise SpecError(f"{field}.correct_option_ids must contain exactly one answer")
        if correct_value not in (None, "") and legacy_correct[0] != correct_value:
            raise SpecError(f"{field} has conflicting correct answer fields")
        if correct_value in (None, ""):
            correct_value = legacy_correct[0]
    correct_id = _identifier(correct_value, f"{field}.correct_option_id")
    if correct_id not in option_ids:
        raise SpecError(f"{field}.correct_option_id is not an option")
    for option in normalized_options:
        if option["id"] != correct_id and not option["misconception_tag"]:
            raise SpecError(
                f"{field}.options wrong choices require misconception_tag"
            )

    scenario_context = _nonempty(
        question.get("scenario_context"), f"{field}.scenario_context", 4000
    )
    normalized: dict[str, Any] = {
        "question_id": question_id,
        "area_id": area_id,
        "concept_id": _identifier(question.get("concept_id"), f"{field}.concept_id"),
        "core_proposition": _nonempty(
            question.get("core_proposition"), f"{field}.core_proposition", 2400
        ),
        "scenario_id": _identifier(question.get("scenario_id"), f"{field}.scenario_id"),
        "scenario_context": scenario_context,
        "scenario_fingerprint": scenario_fingerprint(scenario_context),
        "question_family": family,
        "title": _nonempty(question.get("title"), f"{field}.title", 240),
        "prompt": _nonempty(question.get("prompt"), f"{field}.prompt", 2400),
        "sources": _string_list(
            question.get("sources"), f"{field}.sources", minimum=1, maximum=50
        ),
        "options": normalized_options,
        "correct_option_id": correct_id,
        "correct_option_ids": [correct_id],
        "importance": _bounded_number(
            question.get("importance", 1), f"{field}.importance", 0, 10
        ),
    }
    if review:
        normalized["primary_kernel_id"] = _identifier(
            question.get("primary_kernel_id"), f"{field}.primary_kernel_id"
        )
        normalized["knowledge_kernel_id"] = normalized["primary_kernel_id"]
        normalized["integrated_kernel_ids"] = _id_list(
            question.get("integrated_kernel_ids", []),
            f"{field}.integrated_kernel_ids",
            maximum=20,
        )
        if normalized["primary_kernel_id"] in normalized["integrated_kernel_ids"]:
            raise SpecError(f"{field}.integrated_kernel_ids must not repeat the primary kernel")
        normalized["source_question_id"] = _identifier(
            question.get("source_question_id"), f"{field}.source_question_id"
        )
        lineage = question.get("lineage", {})
        if not isinstance(lineage, Mapping):
            raise SpecError(f"{field}.lineage must be an object")
        normalized["lineage"] = {
            "assessment_question_ids": _id_list(
                lineage.get("assessment_question_ids", []),
                f"{field}.lineage.assessment_question_ids",
                maximum=20,
            ),
            "learning_slice_ids": _id_list(
                lineage.get("learning_slice_ids", []),
                f"{field}.lineage.learning_slice_ids",
                maximum=50,
            ),
            "learning_checkpoint_ids": _id_list(
                lineage.get("learning_checkpoint_ids", []),
                f"{field}.lineage.learning_checkpoint_ids",
                maximum=20,
            ),
        }
    else:
        normalized["knowledge_kernel_id"] = _identifier(
            question.get("knowledge_kernel_id"), f"{field}.knowledge_kernel_id"
        )
    return normalized


def _phase_header(data: Mapping[str, Any], phase: str) -> tuple[str, str]:
    if data.get("schema_version") != 3:
        raise SpecError(f"{phase} schema_version must be 3")
    if data.get("phase") != phase:
        raise SpecError(f"phase must be {phase}")
    return (
        _identifier(data.get("cycle_id"), "cycle_id"),
        _nonempty(data.get("title"), "title", 240),
    )


def validate_assessment_spec(
    data: Mapping[str, Any], cycle: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise SpecError("assessment spec must be an object")
    cycle_id, title = _phase_header(data, "assessment")
    normalized_cycle = validate_cycle(cycle) if cycle is not None else None
    if normalized_cycle and cycle_id != normalized_cycle["cycle_id"]:
        raise SpecError("assessment cycle_id does not match cycle.json")

    if normalized_cycle:
        area_ids = {area["area_id"] for area in normalized_cycle["areas"]}
    else:
        area_ids = set(_id_list(data.get("area_ids"), "area_ids", minimum=3, maximum=6))
    questions = data.get("questions")
    if not isinstance(questions, list) or not 10 <= len(questions) <= 20:
        raise SpecError("assessment.questions must contain 10 to 20 questions")
    normalized_questions = [
        _validate_question(
            question,
            f"questions[{index}]",
            phase="assessment",
            area_ids=area_ids,
        )
        for index, question in enumerate(questions)
    ]
    _require_unique(normalized_questions, "question_id", "assessment question ID")
    _require_unique(normalized_questions, "knowledge_kernel_id", "assessment knowledge kernel")
    _require_unique(normalized_questions, "scenario_id", "assessment scenario ID")
    _require_unique(
        normalized_questions,
        "scenario_fingerprint",
        "assessment scenario fingerprint",
    )

    counts = {area_id: 0 for area_id in area_ids}
    for question in normalized_questions:
        counts[question["area_id"]] += 1
    missing = [area_id for area_id, count in counts.items() if count < 2]
    if missing:
        raise SpecError(f"Every assessment area requires at least 2 questions: {missing}")

    estimated = data.get("estimated_minutes")
    if isinstance(estimated, bool) or not isinstance(estimated, int) or not 1 <= estimated <= 240:
        raise SpecError("estimated_minutes must be an integer from 1 to 240")
    result = {
        "schema_version": 3,
        "phase": "assessment",
        "cycle_id": cycle_id,
        "title": title,
        "instructions": _nonempty(data.get("instructions"), "instructions", 2000),
        "estimated_minutes": estimated,
        "area_ids": sorted(area_ids),
        "questions": normalized_questions,
    }
    if normalized_cycle is not None:
        result["cycle_contract_digest"] = _cycle_contract_digest(normalized_cycle)
    return result


def _require_unique(items: Iterable[Mapping[str, Any]], key: str, label: str) -> None:
    values = [str(item[key]) for item in items]
    if len(set(values)) != len(values):
        raise SpecError(f"Duplicate {label}")


def validate_learning_slice(data: Mapping[str, Any], area_ids: set[str]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise SpecError("learning slice must be an object")
    if data.get("schema_version") != 3:
        raise SpecError("learning slice schema_version must be 3")
    slice_id = _identifier(data.get("slice_id"), "slice_id")
    area_id = _identifier(data.get("area_id"), "area_id")
    if area_id not in area_ids:
        raise SpecError(f"Slice area_id is not declared by the cycle: {area_id}")
    order = data.get("order")
    if isinstance(order, bool) or not isinstance(order, int) or order < 1:
        raise SpecError("slice.order must be a positive integer")
    difficulty = data.get("difficulty")
    if difficulty not in DIFFICULTIES:
        raise SpecError(f"slice.difficulty must be one of: {sorted(DIFFICULTIES)}")
    example = data.get("worked_example")
    if not isinstance(example, Mapping):
        raise SpecError("worked_example must be an object")
    example_context = _nonempty(
        example.get("scenario_context"), "worked_example.scenario_context", 4000
    )
    return {
        "schema_version": 3,
        "slice_id": slice_id,
        "area_id": area_id,
        "title": _nonempty(data.get("title"), "slice.title", 240),
        "order": order,
        "difficulty": difficulty,
        "prerequisites": _id_list(data.get("prerequisites", []), "slice.prerequisites", maximum=30),
        "learning_objective": _nonempty(
            data.get("learning_objective"), "slice.learning_objective", 1600
        ),
        "assessment_question_ids": _id_list(
            data.get("assessment_question_ids", []),
            "slice.assessment_question_ids",
            minimum=1,
            maximum=40,
        ),
        "addresses_gap_ids": _id_list(
            data.get("addresses_gap_ids", []), "slice.addresses_gap_ids", maximum=40
        ),
        "core_explanation": _nonempty(
            data.get("core_explanation"), "slice.core_explanation", 8000
        ),
        "mechanism": _nonempty(data.get("mechanism"), "slice.mechanism", 4000),
        "boundaries": _string_list(
            data.get("boundaries"), "slice.boundaries", minimum=1, maximum=30
        ),
        "worked_example": {
            "scenario_id": _identifier(
                example.get("scenario_id"), "worked_example.scenario_id"
            ),
            "scenario_context": example_context,
            "scenario_fingerprint": scenario_fingerprint(example_context),
            "walkthrough": _nonempty(
                example.get("walkthrough"), "worked_example.walkthrough", 8000
            ),
        },
        "common_mistakes": _string_list(
            data.get("common_mistakes"), "slice.common_mistakes", minimum=1, maximum=30
        ),
        "key_takeaways": _string_list(
            data.get("key_takeaways"), "slice.key_takeaways", minimum=1, maximum=30
        ),
        "sources": _string_list(data.get("sources"), "slice.sources", minimum=1, maximum=50),
    }


def _slice_mapping(
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    area_ids: set[str],
) -> dict[str, dict[str, Any]]:
    raw_items = list(slices.values()) if isinstance(slices, Mapping) else list(slices)
    normalized = [validate_learning_slice(item, area_ids) for item in raw_items]
    _require_unique(normalized, "slice_id", "learning slice ID")
    return {item["slice_id"]: item for item in normalized}


def validate_learning_path(
    data: Mapping[str, Any],
    cycle: Mapping[str, Any] | None = None,
    *,
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
    assessment_report: Mapping[str, Any] | None = None,
    assessment_spec: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise SpecError("learning path must be an object")
    cycle_id, title = _phase_header(data, "learning")
    normalized_cycle = validate_cycle(cycle) if cycle is not None else None
    if normalized_cycle and cycle_id != normalized_cycle["cycle_id"]:
        raise SpecError("learning cycle_id does not match cycle.json")
    cycle_area_ids = (
        {area["area_id"] for area in normalized_cycle["areas"]}
        if normalized_cycle
        else None
    )
    raw_areas = data.get("areas")
    if not isinstance(raw_areas, list) or not 3 <= len(raw_areas) <= 6:
        raise SpecError("learning.areas must contain 3 to 6 areas")
    declared_ids = {
        _identifier(area.get("area_id") if isinstance(area, Mapping) else None, f"areas[{index}].area_id")
        for index, area in enumerate(raw_areas)
    }
    if len(declared_ids) != len(raw_areas):
        raise SpecError("Duplicate learning area_id")
    if cycle_area_ids is not None and declared_ids != cycle_area_ids:
        raise SpecError("learning areas must match cycle areas")

    normalized_areas: list[dict[str, Any]] = []
    all_slice_ids: list[str] = []
    checkpoint_kernels: set[str] = set()
    checkpoint_question_ids: set[str] = set()
    for index, area in enumerate(raw_areas):
        assert isinstance(area, Mapping)
        area_id = _identifier(area.get("area_id"), f"areas[{index}].area_id")
        slice_ids = _id_list(
            area.get("slice_ids"), f"areas[{index}].slice_ids", minimum=5, maximum=10
        )
        checkpoint = _validate_question(
            area.get("checkpoint"),
            f"areas[{index}].checkpoint",
            phase="learning",
            area_ids=declared_ids,
        )
        if checkpoint["area_id"] != area_id:
            raise SpecError(f"areas[{index}].checkpoint must belong to its area")
        if checkpoint["knowledge_kernel_id"] in checkpoint_kernels:
            raise SpecError("Learning checkpoints must use unique knowledge kernels")
        checkpoint_kernels.add(checkpoint["knowledge_kernel_id"])
        if checkpoint["question_id"] in checkpoint_question_ids:
            raise SpecError("Learning checkpoints must use unique question IDs")
        checkpoint_question_ids.add(checkpoint["question_id"])
        all_slice_ids.extend(slice_ids)
        normalized_areas.append(
            {
                "area_id": area_id,
                "title": _nonempty(area.get("title"), f"areas[{index}].title", 240),
                "slice_ids": slice_ids,
                "checkpoint": checkpoint,
            }
        )
    if len(set(all_slice_ids)) != len(all_slice_ids):
        raise SpecError("Learning slice IDs must be globally unique")

    normalized_slices: dict[str, dict[str, Any]] | None = None
    if slices is not None:
        normalized_slices = _slice_mapping(slices, declared_ids)
        if set(normalized_slices) != set(all_slice_ids):
            raise SpecError("learning path slice_ids must exactly match supplied slice files")
        position = {slice_id: index for index, slice_id in enumerate(all_slice_ids)}
        for area in normalized_areas:
            previous_difficulty = -1
            difficulty_rank = {"foundation": 0, "core": 1, "advanced": 2}
            for expected_order, slice_id in enumerate(area["slice_ids"], start=1):
                item = normalized_slices[slice_id]
                if item["area_id"] != area["area_id"]:
                    raise SpecError(f"Slice {slice_id} is listed under the wrong area")
                if item["order"] != expected_order:
                    raise SpecError(f"Slice {slice_id} order does not match the knowledge map")
                current_difficulty = difficulty_rank[item["difficulty"]]
                if current_difficulty < previous_difficulty:
                    raise SpecError(
                        f"Slice difficulty must progress from simple to complex: {slice_id}"
                    )
                previous_difficulty = current_difficulty
                for prerequisite in item["prerequisites"]:
                    if prerequisite not in normalized_slices:
                        raise SpecError(f"Slice {slice_id} has an unknown prerequisite: {prerequisite}")
                    if position[prerequisite] >= position[slice_id]:
                        raise SpecError(
                            f"Slice prerequisite must appear earlier in the knowledge map: {prerequisite} -> {slice_id}"
                        )

    normalized_assessment: dict[str, Any] | None = None
    if assessment_spec is not None:
        normalized_assessment = validate_assessment_spec(
            assessment_spec, normalized_cycle
        )
        assessment_question_ids = {
            item["question_id"] for item in normalized_assessment["questions"]
        }
        assessment_kernel_ids = {
            item["knowledge_kernel_id"] for item in normalized_assessment["questions"]
        }
        collisions = sorted(checkpoint_question_ids & assessment_question_ids)
        if collisions:
            raise SpecError(
                f"Learning checkpoint question IDs collide with Assessment: {collisions}"
            )
        kernel_collisions = sorted(checkpoint_kernels & assessment_kernel_ids)
        if kernel_collisions:
            raise SpecError(
                "Learning checkpoint knowledge kernels collide with Assessment: "
                f"{kernel_collisions}"
            )
        if normalized_slices is not None:
            unknown_links = sorted(
                {
                    question_id
                    for item in normalized_slices.values()
                    for question_id in item["assessment_question_ids"]
                    if question_id not in assessment_question_ids
                }
            )
            if unknown_links:
                raise SpecError(
                    f"Learning slices reference unknown Assessment questions: {unknown_links}"
                )

    if assessment_report is not None:
        gaps = assessment_report.get("gaps", [])
        if not isinstance(gaps, list):
            raise SpecError("assessment_report.gaps must be an array")
        gap_ids_by_area: dict[str, set[str]] = {area_id: set() for area_id in declared_ids}
        gap_source_question: dict[str, str] = {}
        for index, gap in enumerate(gaps):
            if not isinstance(gap, Mapping):
                raise SpecError(f"assessment_report.gaps[{index}] must be an object")
            area_id = _identifier(gap.get("area_id"), f"assessment_report.gaps[{index}].area_id")
            if area_id not in declared_ids:
                raise SpecError(f"Assessment gap references unknown area: {area_id}")
            gap_id = _identifier(
                gap.get("gap_id"), f"assessment_report.gaps[{index}].gap_id"
            )
            gap_ids_by_area[area_id].add(gap_id)
            gap_source_question[gap_id] = _identifier(
                gap.get("source_question_id"),
                f"assessment_report.gaps[{index}].source_question_id",
            )
        for area in normalized_areas:
            expected = min(10, 5 + len(gap_ids_by_area[area["area_id"]]))
            if len(area["slice_ids"]) != expected:
                raise SpecError(
                    f"Area {area['area_id']} requires {expected} slices for its independent gaps"
                )
        if normalized_slices is None and gaps:
            raise SpecError("slice files are required to validate assessment gap mapping")
        mapped = {
            gap_id
            for item in (normalized_slices or {}).values()
            for gap_id in item["addresses_gap_ids"]
        }
        required = {gap_id for area_gaps in gap_ids_by_area.values() for gap_id in area_gaps}
        missing = sorted(required - mapped)
        if missing:
            raise SpecError(f"Every assessment gap must map to a learning slice: {missing}")
        unknown = sorted(mapped - required)
        if unknown:
            raise SpecError(f"Learning slices reference unknown assessment gaps: {unknown}")
        gap_area = {
            gap_id: area_id
            for area_id, area_gaps in gap_ids_by_area.items()
            for gap_id in area_gaps
        }
        for item in (normalized_slices or {}).values():
            wrong_area = [
                gap_id
                for gap_id in item["addresses_gap_ids"]
                if gap_area[gap_id] != item["area_id"]
            ]
            if wrong_area:
                raise SpecError(
                    f"Slice {item['slice_id']} maps gaps from another area: {wrong_area}"
                )
            missing_sources = [
                gap_id
                for gap_id in item["addresses_gap_ids"]
                if gap_source_question[gap_id]
                not in item["assessment_question_ids"]
            ]
            if missing_sources:
                raise SpecError(
                    f"Slice {item['slice_id']} must link each addressed gap's source question: "
                    f"{missing_sources}"
                )

    return {
        "schema_version": 3,
        "phase": "learning",
        "cycle_id": cycle_id,
        "title": title,
        "areas": normalized_areas,
    }


def _question_index(spec: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["question_id"]: item for item in spec["questions"]}


def _kernel_index(
    assessment_spec: Mapping[str, Any], learning_path: Mapping[str, Any] | None = None
) -> dict[str, dict[str, Any]]:
    index = {item["knowledge_kernel_id"]: item for item in assessment_spec["questions"]}
    if learning_path:
        for area in learning_path["areas"]:
            checkpoint = area["checkpoint"]
            if checkpoint["knowledge_kernel_id"] in index:
                raise SpecError("Checkpoint kernel collides with an assessment kernel")
            index[checkpoint["knowledge_kernel_id"]] = checkpoint
    return index


def _required_primary_gap_kernels(
    gaps: Iterable[Mapping[str, Any]],
    area_order: list[str],
    question_count: int,
) -> set[str]:
    """Choose the highest-priority gaps that can receive direct scoring.

    A capped Review can contain fewer questions than prior independent gaps.
    Areas with no gap still need one primary question for area coverage, so
    those questions are reserved before allocating the remaining capacity.
    """

    unique: dict[str, dict[str, Any]] = {}
    for position, gap in enumerate(gaps):
        kernel_id = str(gap["knowledge_kernel_id"])
        if kernel_id not in unique:
            unique[kernel_id] = {**gap, "_position": position}

    gap_areas = {str(gap["area_id"]) for gap in unique.values()}
    reserved_for_gap_free_areas = len(set(area_order) - gap_areas)
    capacity = min(
        len(unique),
        max(0, question_count - reserved_for_gap_free_areas),
    )

    def priority(gap: Mapping[str, Any]) -> tuple[int, int, int]:
        source_rank = 0 if gap.get("source") == "assessment" else 1
        critical_rank = 0 if gap.get("critical") is True else 1
        return source_rank, critical_rank, int(gap["_position"])

    required: list[str] = []
    # First make gap-bearing areas visible in direct scoring, using the best
    # candidate in each area. The ordinary all-area validator reserves the
    # remaining questions for areas that had no prior gap.
    for area_id in area_order:
        candidates = [
            gap for gap in unique.values() if gap["area_id"] == area_id
        ]
        if candidates:
            chosen = min(candidates, key=priority)["knowledge_kernel_id"]
            if chosen not in required:
                required.append(chosen)

    for gap in sorted(unique.values(), key=priority):
        kernel_id = str(gap["knowledge_kernel_id"])
        if kernel_id not in required:
            required.append(kernel_id)
        if len(required) >= capacity:
            break
    return set(required[:capacity])


def validate_review_spec(
    data: Mapping[str, Any],
    cycle: Mapping[str, Any],
    *,
    assessment_spec: Mapping[str, Any],
    learning_path: Mapping[str, Any] | None = None,
    learning_slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
    assessment_report: Mapping[str, Any] | None = None,
    learning_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise SpecError("review spec must be an object")
    cycle_id, title = _phase_header(data, "review")
    normalized_cycle = validate_cycle(cycle)
    if cycle_id != normalized_cycle["cycle_id"]:
        raise SpecError("review cycle_id does not match cycle.json")
    normalized_assessment = validate_assessment_spec(assessment_spec, normalized_cycle)
    normalized_learning = (
        validate_learning_path(
            learning_path,
            normalized_cycle,
            slices=learning_slices,
            assessment_report=assessment_report,
            assessment_spec=normalized_assessment,
        )
        if learning_path is not None
        else None
    )
    area_order = [area["area_id"] for area in normalized_cycle["areas"]]
    area_ids = set(area_order)
    questions = data.get("questions")
    if not isinstance(questions, list) or not 8 <= len(questions) <= 15:
        raise SpecError("review.questions must contain 8 to 15 questions")
    normalized_questions = [
        _validate_question(
            question,
            f"questions[{index}]",
            phase="review",
            area_ids=area_ids,
            review=True,
        )
        for index, question in enumerate(questions)
    ]
    _require_unique(normalized_questions, "question_id", "review question ID")
    _require_unique(normalized_questions, "scenario_id", "review scenario ID")
    _require_unique(normalized_questions, "scenario_fingerprint", "review scenario fingerprint")

    source_by_id = _question_index(normalized_assessment)
    if normalized_learning:
        for area in normalized_learning["areas"]:
            source_by_id[area["checkpoint"]["question_id"]] = area["checkpoint"]
    sources_by_kernel = _kernel_index(normalized_assessment, normalized_learning)
    known_kernels = set(sources_by_kernel)
    prior_fingerprints = {
        item["scenario_fingerprint"] for item in normalized_assessment["questions"]
    }
    prior_scenario_ids = {
        item["scenario_id"] for item in normalized_assessment["questions"]
    }
    prior_scenario_contexts = [
        item["scenario_context"] for item in normalized_assessment["questions"]
    ]
    if normalized_learning:
        checkpoint_questions = [
            area["checkpoint"] for area in normalized_learning["areas"]
        ]
        prior_fingerprints.update(
            item["scenario_fingerprint"] for item in checkpoint_questions
        )
        prior_scenario_ids.update(
            item["scenario_id"] for item in checkpoint_questions
        )
        prior_scenario_contexts.extend(
            item["scenario_context"] for item in checkpoint_questions
        )
    example_fingerprints: set[str] = set()
    example_scenario_ids: set[str] = set()
    slice_ids: set[str] = set()
    if learning_slices is not None:
        normalized_slice_map = _slice_mapping(learning_slices, area_ids)
        slice_ids = set(normalized_slice_map)
        example_fingerprints = {
            item["worked_example"]["scenario_fingerprint"]
            for item in normalized_slice_map.values()
        }
        example_scenario_ids = {
            item["worked_example"]["scenario_id"]
            for item in normalized_slice_map.values()
        }
        prior_scenario_contexts.extend(
            item["worked_example"]["scenario_context"]
            for item in normalized_slice_map.values()
        )

    assessment_question_ids = set(_question_index(normalized_assessment))
    checkpoint_question_ids = {
        area["checkpoint"]["question_id"] for area in (normalized_learning or {}).get("areas", [])
    }

    for index, question in enumerate(normalized_questions):
        field = f"questions[{index}]"
        source = source_by_id.get(question["source_question_id"])
        if source is None:
            raise SpecError(f"{field}.source_question_id does not exist")
        if source["knowledge_kernel_id"] != question["primary_kernel_id"]:
            raise SpecError(f"{field}.primary_kernel_id must match its source question")
        if source["area_id"] != question["area_id"]:
            raise SpecError(f"{field}.area_id must match its primary source question")
        if question["core_proposition"] != source["core_proposition"]:
            raise SpecError(f"{field} must preserve the source core_proposition")
        unknown_integrated = set(question["integrated_kernel_ids"]) - known_kernels
        if unknown_integrated:
            raise SpecError(f"{field} references unknown integrated kernels: {sorted(unknown_integrated)}")
        if question["scenario_id"] in prior_scenario_ids | example_scenario_ids:
            raise SpecError(f"{field} must use a new scenario_id")
        if question["scenario_fingerprint"] in prior_fingerprints | example_fingerprints:
            raise SpecError(
                f"{field} reuses an assessment, checkpoint, or learning scenario"
            )
        if any(
            _near_duplicate(question["scenario_context"], context)
            for context in prior_scenario_contexts
        ):
            raise SpecError(f"{field} is a near-duplicate of a prior scenario")
        if question["question_family"] == source["question_family"]:
            raise SpecError(f"{field} must change question_family")
        if _normalize_text(question["prompt"]) == _normalize_text(source["prompt"]):
            raise SpecError(f"{field} must change the prompt")
        source_ids = {item["id"] for item in source["options"]}
        review_ids = {item["id"] for item in question["options"]}
        if source_ids & review_ids:
            raise SpecError(f"{field} must use new option IDs")
        source_labels = {_normalize_text(item["label"]) for item in source["options"]}
        review_labels = {_normalize_text(item["label"]) for item in question["options"]}
        if source_labels & review_labels:
            raise SpecError(f"{field} must rewrite every option label")
        source_descriptions = {
            _normalize_text(item["description"]) for item in source["options"]
        }
        review_descriptions = {
            _normalize_text(item["description"]) for item in question["options"]
        }
        if source_descriptions & review_descriptions:
            raise SpecError(f"{field} must rewrite every option description")
        source_explanations = {
            _normalize_text(item["explanation"]) for item in source["options"]
        }
        review_explanations = {
            _normalize_text(item["explanation"]) for item in question["options"]
        }
        if source_explanations & review_explanations:
            raise SpecError(f"{field} must rewrite every option explanation")
        source_position = [item["id"] for item in source["options"]].index(
            source["correct_option_id"]
        )
        review_position = [item["id"] for item in question["options"]].index(
            question["correct_option_id"]
        )
        if source_position == review_position:
            raise SpecError(f"{field} must rotate the correct-answer position")
        lineage = question["lineage"]
        if source["question_id"] in _question_index(normalized_assessment):
            if source["question_id"] not in lineage["assessment_question_ids"]:
                raise SpecError(f"{field}.lineage must include its assessment source")
        elif source["question_id"] not in lineage["learning_checkpoint_ids"]:
            raise SpecError(f"{field}.lineage must include its learning checkpoint source")
        for kernel_id in question["integrated_kernel_ids"]:
            integrated_source = sources_by_kernel[kernel_id]
            if integrated_source["question_id"] in _question_index(normalized_assessment):
                if integrated_source["question_id"] not in lineage["assessment_question_ids"]:
                    raise SpecError(
                        f"{field}.lineage must include every integrated assessment source"
                    )
            elif integrated_source["question_id"] not in lineage["learning_checkpoint_ids"]:
                raise SpecError(
                    f"{field}.lineage must include every integrated checkpoint source"
                )
        unknown_slices = set(lineage["learning_slice_ids"]) - slice_ids
        if learning_slices is not None and unknown_slices:
            raise SpecError(f"{field}.lineage references unknown learning slices")
        unknown_assessment = (
            set(lineage["assessment_question_ids"]) - assessment_question_ids
        )
        if unknown_assessment:
            raise SpecError(
                f"{field}.lineage references unknown Assessment questions: {sorted(unknown_assessment)}"
            )
        unknown_checkpoints = (
            set(lineage["learning_checkpoint_ids"]) - checkpoint_question_ids
        )
        if unknown_checkpoints:
            raise SpecError(
                f"{field}.lineage references unknown Learning checkpoints: {sorted(unknown_checkpoints)}"
            )

    covered_areas = {question["area_id"] for question in normalized_questions}
    missing_areas = sorted(area_ids - covered_areas)
    if missing_areas:
        raise SpecError(f"Review must cover every major area: {missing_areas}")

    has_cross_area_integration = any(
        any(
            sources_by_kernel[kernel_id]["area_id"] != question["area_id"]
            for kernel_id in question["integrated_kernel_ids"]
        )
        for question in normalized_questions
    )
    if not has_cross_area_integration:
        raise SpecError("Review requires at least one cross-area integrated question")

    gaps = _combined_gap_records(assessment_report, learning_report)
    if assessment_report is not None or learning_report is not None:
        gap_kernels = {gap["knowledge_kernel_id"] for gap in gaps}
        unknown_gap_kernels = sorted(gap_kernels - known_kernels)
        if unknown_gap_kernels:
            raise SpecError(
                f"Reports reference unknown gap kernels: {unknown_gap_kernels}"
            )
        unknown_gap_areas = sorted(
            {gap["area_id"] for gap in gaps} - area_ids
        )
        if unknown_gap_areas:
            raise SpecError(
                f"Reports reference unknown gap areas: {unknown_gap_areas}"
            )
        expected = clamp(len(gap_kernels) + len(area_ids), 8, 15)
        if len(normalized_questions) != expected:
            raise SpecError(f"Review requires {expected} questions for current gaps and areas")
        primary_covered = {
            question["primary_kernel_id"] for question in normalized_questions
        }
        required_primary = _required_primary_gap_kernels(
            gaps, area_order, len(normalized_questions)
        )
        missing_primary = sorted(required_primary - primary_covered)
        if missing_primary:
            raise SpecError(
                "Review primary kernels omit capacity-prioritized gaps: "
                f"{missing_primary}"
            )
        all_covered = {
            kernel_id
            for question in normalized_questions
            for kernel_id in [
                question["primary_kernel_id"],
                *question["integrated_kernel_ids"],
            ]
        }
        missing_gap_coverage = sorted(gap_kernels - all_covered)
        if missing_gap_coverage:
            raise SpecError(
                "Every prior gap kernel must appear as primary or integrated: "
                f"{missing_gap_coverage}"
            )
        result_by_question = {
            item.get("question_id"): item
            for item in (assessment_report or {}).get("question_results", [])
            if isinstance(item, Mapping)
        }
        critical_correct = {
            question["knowledge_kernel_id"]
            for question in normalized_assessment["questions"]
            if question["importance"] >= 8
            and result_by_question.get(question["question_id"], {}).get("is_correct") is True
        }
        missing_critical = sorted(critical_correct - all_covered)
        if missing_critical:
            raise SpecError(
                f"Review must include mission-critical correct kernels: {missing_critical}"
            )

    return {
        "schema_version": 3,
        "phase": "review",
        "cycle_id": cycle_id,
        "cycle_contract_digest": _cycle_contract_digest(normalized_cycle),
        "title": title,
        "instructions": _nonempty(data.get("instructions"), "instructions", 2000),
        "questions": normalized_questions,
    }


def _combined_gap_records(
    assessment_report: Mapping[str, Any] | None,
    learning_report: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for report in (assessment_report, learning_report):
        if report is None:
            continue
        gaps = report.get("gaps", [])
        if not isinstance(gaps, list):
            raise SpecError("report.gaps must be an array")
        for index, gap in enumerate(gaps):
            if not isinstance(gap, Mapping):
                raise SpecError(f"report.gaps[{index}] must be an object")
            gap_id = _identifier(gap.get("gap_id"), f"report.gaps[{index}].gap_id")
            source = gap.get("source")
            if source is None:
                source = (
                    "assessment"
                    if gap_id.startswith("assessment.")
                    else "learning_checkpoint"
                )
            if source not in {"assessment", "learning_checkpoint"}:
                raise SpecError(
                    f"report.gaps[{index}].source must be assessment or learning_checkpoint"
                )
            critical = gap.get("critical", False)
            if not isinstance(critical, bool):
                raise SpecError(f"report.gaps[{index}].critical must be boolean")
            result[gap_id] = {
                "gap_id": gap_id,
                "source": source,
                "area_id": _identifier(gap.get("area_id"), f"report.gaps[{index}].area_id"),
                "knowledge_kernel_id": _identifier(
                    gap.get("knowledge_kernel_id"),
                    f"report.gaps[{index}].knowledge_kernel_id",
                ),
                "source_question_id": _identifier(
                    gap.get("source_question_id"),
                    f"report.gaps[{index}].source_question_id",
                ),
                "core_proposition": _optional(
                    gap.get("core_proposition"),
                    f"report.gaps[{index}].core_proposition",
                    2400,
                ),
                "critical": critical,
            }
    return list(result.values())


def _find_question(spec: Mapping[str, Any], question_id: str) -> dict[str, Any]:
    for question in spec.get("questions", []):
        if question["question_id"] == question_id:
            return question
    raise SpecError(f"Unknown question_id: {question_id}")


def _batch_spec_digest(spec: Mapping[str, Any]) -> str:
    if spec.get("phase") not in {"assessment", "review"}:
        raise SpecError("Batch manifests support Assessment or Review specs")
    return _content_digest(spec)


def validate_batch_manifest(
    phase_dir: Path,
    spec: Mapping[str, Any],
    *,
    required: bool = False,
) -> dict[str, Any] | None:
    """Validate the write-once digest that seals an entire question batch."""

    path = _contained_child(phase_dir, "batch-manifest.json")
    if path.exists() and not path.is_file():
        raise SpecError(f"Batch manifest path is not a file: {path}")
    if not path.is_file():
        if required:
            raise SpecError(f"Batch manifest is missing: {path}")
        return None
    record = read_json_object(path)
    expected = {
        "schema_version": 3,
        "record_type": "batch_manifest",
        "phase": spec.get("phase"),
        "cycle_id": spec.get("cycle_id"),
        "cycle_contract_digest": spec.get("cycle_contract_digest"),
        "spec_digest": _batch_spec_digest(spec),
        "question_ids": [item["question_id"] for item in spec.get("questions", [])],
    }
    for field, value in expected.items():
        if record.get(field) != value:
            raise SpecError(f"Batch manifest {field} mismatch: {path}")
    _rfc3339(record.get("sealed_at"), f"{path}.sealed_at")
    return record


def ensure_batch_manifest(
    phase_dir: Path, spec: Mapping[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Seal a complete normalized batch before its first learner action."""

    existing = validate_batch_manifest(phase_dir, spec)
    if existing is not None:
        validate_choice_label_contract(spec, check_future_surfaces=False)
        return existing, False
    validate_choice_description_contract(spec)
    record = {
        "schema_version": 3,
        "record_type": "batch_manifest",
        "phase": spec["phase"],
        "cycle_id": spec["cycle_id"],
        "cycle_contract_digest": spec.get("cycle_contract_digest"),
        "spec_digest": _batch_spec_digest(spec),
        "question_ids": [item["question_id"] for item in spec["questions"]],
        "sealed_at": utc_now(),
    }
    path = _contained_child(phase_dir, "batch-manifest.json")
    try:
        write_json_once(path, record)
    except FileExistsError:
        committed = validate_batch_manifest(phase_dir, spec, required=True)
        assert committed is not None
        return committed, False
    return record, True


def _validate_display_order(question: Mapping[str, Any], order: Iterable[str]) -> list[str]:
    if not isinstance(order, list):
        raise SpecError("displayed_option_order must be an array")
    normalized = [_identifier(item, f"displayed_option_order[{index}]") for index, item in enumerate(order)]
    expected = {item["id"] for item in question["options"]}
    if len(normalized) != len(expected) or set(normalized) != expected:
        raise SpecError("displayed_option_order must be an exact option permutation")
    return normalized


def _idempotent_existing(
    path: Path, *, request_id: str, selected_option_id: str | None = None
) -> tuple[dict[str, Any], bool]:
    existing = read_json_object(path)
    same_selection = (
        selected_option_id is None
        or existing.get("selected_option_id") == selected_option_id
    )
    # The committed answer is the idempotency key at question scope.  A client
    # may legitimately generate a fresh request ID after an uncertain timeout.
    if same_selection:
        return existing, False
    raise ConflictError(f"Immutable record already committed: {path}")


def record_response(
    phase_dir: Path,
    spec: Mapping[str, Any],
    question_id: str,
    selected_option_id: str,
    displayed_option_order: list[str],
    request_id: str,
) -> tuple[dict[str, Any], bool]:
    """Commit one Assessment/Review answer with request-level idempotency."""

    phase = spec.get("phase")
    if phase not in {"assessment", "review"}:
        raise SpecError("record_response supports assessment or review specs")
    question_id = _identifier(question_id, "question_id")
    selected_option_id = _identifier(selected_option_id, "selected_option_id")
    request_id = _identifier(request_id, "request_id")
    question = _find_question(spec, question_id)
    order = _validate_display_order(question, displayed_option_order)
    options = {item["id"]: item for item in question["options"]}
    if selected_option_id not in options:
        raise SpecError("selected_option_id is not a valid option")
    selected = options[selected_option_id]
    is_correct = selected_option_id == question["correct_option_id"]
    manifest, _ = ensure_batch_manifest(phase_dir, spec)
    record = {
        "schema_version": 3,
        "record_type": "question_response",
        "phase": phase,
        "cycle_id": spec["cycle_id"],
        "question_id": question_id,
        "batch_spec_digest": manifest["spec_digest"],
        "question_digest": _question_digest(question),
        "area_id": question["area_id"],
        "concept_id": question["concept_id"],
        "knowledge_kernel_id": question["knowledge_kernel_id"],
        "primary_kernel_id": question.get("primary_kernel_id"),
        "integrated_kernel_ids": question.get("integrated_kernel_ids", []),
        "scenario_id": question["scenario_id"],
        "scenario_fingerprint": question["scenario_fingerprint"],
        "question_family": question["question_family"],
        "lineage": question.get("lineage", {}),
        "displayed_option_order": order,
        "selected_option_id": selected_option_id,
        "selected_misconception_tag": selected["misconception_tag"] or None,
        "correct_option_id": question["correct_option_id"],
        "is_correct": is_correct,
        "independence": "independent" if phase == "assessment" else "feedback_exposed",
        "feedback_exposed": phase == "review",
        "feedback_timing": "immediate_after_commit",
        "request_id": request_id,
        "answered_at": utc_now(),
    }
    path = _contained_child(phase_dir, "responses", f"{question_id}.json")
    if path.exists():
        _responses_for(phase_dir, spec, require_complete=False)
        return _idempotent_existing(
            path, request_id=request_id, selected_option_id=selected_option_id
        )
    try:
        write_json_once(path, record)
    except FileExistsError:
        _responses_for(phase_dir, spec, require_complete=False)
        return _idempotent_existing(
            path, request_id=request_id, selected_option_id=selected_option_id
        )
    return record, True


def _responses_for(
    phase_dir: Path,
    spec: Mapping[str, Any],
    *,
    require_complete: bool,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    expected_names = {f"{question['question_id']}.json" for question in spec["questions"]}
    responses_dir = _contained_child(phase_dir, "responses")
    if responses_dir.exists() and not responses_dir.is_dir():
        raise SpecError(f"Responses path is not a directory: {responses_dir}")
    response_paths = list(responses_dir.glob("*.json")) if responses_dir.is_dir() else []
    manifest = validate_batch_manifest(
        phase_dir, spec, required=bool(response_paths)
    )
    batch_spec_digest = _batch_spec_digest(spec)
    if responses_dir.is_dir():
        unexpected = sorted(
            path.name
            for path in response_paths
            if path.name not in expected_names
        )
        if unexpected:
            raise SpecError(f"Unexpected response files: {unexpected}")
    for question in spec["questions"]:
        path = _contained_child(
            phase_dir, "responses", f"{question['question_id']}.json"
        )
        if path.exists() and not path.is_file():
            raise SpecError(f"Response path is not a file: {path}")
        if not path.is_file():
            missing.append(question["question_id"])
            continue
        record = read_json_object(path)
        expected_identity = {
            "schema_version": 3,
            "record_type": "question_response",
            "phase": spec["phase"],
            "cycle_id": spec["cycle_id"],
            "question_id": question["question_id"],
            "batch_spec_digest": batch_spec_digest,
            "question_digest": _question_digest(question),
            "area_id": question["area_id"],
            "concept_id": question["concept_id"],
            "knowledge_kernel_id": question["knowledge_kernel_id"],
            "primary_kernel_id": question.get("primary_kernel_id"),
            "integrated_kernel_ids": question.get("integrated_kernel_ids", []),
            "scenario_id": question["scenario_id"],
            "scenario_fingerprint": question["scenario_fingerprint"],
            "question_family": question["question_family"],
            "lineage": question.get("lineage", {}),
            "correct_option_id": question["correct_option_id"],
            "independence": (
                "independent" if spec["phase"] == "assessment" else "feedback_exposed"
            ),
            "feedback_exposed": spec["phase"] == "review",
            "feedback_timing": "immediate_after_commit",
        }
        for field, value in expected_identity.items():
            if record.get(field) != value:
                raise SpecError(f"Response {field} mismatch: {path}")
        _validate_display_order(question, record.get("displayed_option_order"))
        options = {item["id"]: item for item in question["options"]}
        selected_option_id = record.get("selected_option_id")
        if selected_option_id not in options:
            raise SpecError(f"Response selected option mismatch: {path}")
        expected_correct = selected_option_id == question["correct_option_id"]
        if record.get("is_correct") is not expected_correct:
            raise SpecError(f"Response correctness mismatch: {path}")
        expected_misconception = options[selected_option_id]["misconception_tag"] or None
        if record.get("selected_misconception_tag") != expected_misconception:
            raise SpecError(f"Response misconception mismatch: {path}")
        _identifier(record.get("request_id"), f"{path}.request_id")
        _rfc3339(record.get("answered_at"), f"{path}.answered_at")
        records[question["question_id"]] = record
    if records and manifest is None:
        raise SpecError("Responses require a sealed batch manifest")
    if require_complete and missing:
        raise IncompletePhaseError(f"Missing responses: {missing}")
    return records, missing


def response_completion_state(
    phase_dir: Path, spec: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate responses and expose a strict sequential completion prefix."""

    records, _ = _responses_for(phase_dir, spec, require_complete=False)
    question_ids = [question["question_id"] for question in spec["questions"]]
    completed_ids: list[str] = []
    missing_seen = False
    for question_id in question_ids:
        if question_id in records:
            if missing_seen:
                raise SpecError(f"Responses are out of order at {question_id}")
            completed_ids.append(question_id)
        else:
            missing_seen = True
    return {
        "complete": len(completed_ids) == len(question_ids),
        "completed_question_ids": completed_ids,
        "completed": len(completed_ids),
        "total": len(question_ids),
        "next_question_id": (
            question_ids[len(completed_ids)]
            if len(completed_ids) < len(question_ids)
            else None
        ),
    }


def _signal(correct: int, total: int) -> str:
    ratio = correct / total if total else 0
    if ratio >= 0.8:
        return "stable_signal"
    if ratio >= 0.5:
        return "mixed_signal"
    return "needs_support"


def build_assessment_report(
    phase_dir: Path,
    spec: Mapping[str, Any],
    *,
    require_complete: bool = True,
    persist: bool = False,
) -> dict[str, Any]:
    responses, missing = _responses_for(phase_dir, spec, require_complete=require_complete)
    area_order = list(spec["area_ids"])
    area_results: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    strengths: list[dict[str, Any]] = []
    question_results: list[dict[str, Any]] = []
    total_correct = 0
    for area_id in area_order:
        questions = [item for item in spec["questions"] if item["area_id"] == area_id]
        answered = [item for item in questions if item["question_id"] in responses]
        correct = sum(bool(responses[item["question_id"]]["is_correct"]) for item in answered)
        total_correct += correct
        signal = _signal(correct, len(answered)) if answered else "needs_support"
        area_gap_ids: list[str] = []
        for question in answered:
            response = responses[question["question_id"]]
            result = {
                "question_id": question["question_id"],
                "area_id": area_id,
                "knowledge_kernel_id": question["knowledge_kernel_id"],
                "core_proposition": question["core_proposition"],
                "sources": question["sources"],
                "is_correct": response["is_correct"],
                "selected_option_id": response["selected_option_id"],
                "misconception_tag": response.get("selected_misconception_tag"),
            }
            question_results.append(result)
            if response["is_correct"]:
                strengths.append(
                    {
                        "source_question_id": question["question_id"],
                        "area_id": area_id,
                        "knowledge_kernel_id": question["knowledge_kernel_id"],
                        "core_proposition": question["core_proposition"],
                        "importance": question["importance"],
                        "sources": question["sources"],
                    }
                )
            else:
                gap_id = f"assessment.{question['question_id']}"
                area_gap_ids.append(gap_id)
                gaps.append(
                    {
                        "gap_id": gap_id,
                        "source": "assessment",
                        "source_question_id": question["question_id"],
                        "area_id": area_id,
                        "knowledge_kernel_id": question["knowledge_kernel_id"],
                        "core_proposition": question["core_proposition"],
                        "sources": question["sources"],
                        "misconception_tag": response.get("selected_misconception_tag"),
                        "critical": question["importance"] >= 8,
                    }
                )
        area_results.append(
            {
                "area_id": area_id,
                "answered": len(answered),
                "total": len(questions),
                "correct": correct,
                "accuracy": correct / len(answered) if answered else 0,
                "signal": signal,
                "signal_label": SIGNAL_LABELS[signal],
                "strength_question_ids": [
                    item["question_id"]
                    for item in answered
                    if responses[item["question_id"]]["is_correct"]
                ],
                "wrong_question_ids": [
                    item["question_id"]
                    for item in answered
                    if not responses[item["question_id"]]["is_correct"]
                ],
                "gap_ids": area_gap_ids,
                "critical_gap_ids": [
                    gap["gap_id"]
                    for gap in gaps
                    if gap["area_id"] == area_id and gap["critical"]
                ],
                "suggested_slice_count": min(10, 5 + len(set(area_gap_ids))),
                "confidence": "medium" if len(answered) >= 3 else "low",
            }
        )
    report = {
        "schema_version": 3,
        "report_type": "assessment_report",
        "cycle_id": spec["cycle_id"],
        "complete": not missing,
        "answered": len(responses),
        "total": len(spec["questions"]),
        "correct": total_correct,
        "area_results": area_results,
        "question_results": question_results,
        "strengths": strengths,
        "gaps": gaps,
        "critical_gap_ids": [gap["gap_id"] for gap in gaps if gap["critical"]],
        "missing_question_ids": missing,
        "evidence_limitations": [
            "Immediate feedback means later same-kernel evidence is feedback-exposed.",
            "Choice responses do not prove end-to-end execution by themselves.",
        ],
        "generated_at": utc_now(),
    }
    if persist:
        atomic_write_json(_contained_child(phase_dir, "report.json"), report)
    return report


def _learning_event_path(learning_dir: Path, event_type: str, subject_id: str) -> Path:
    return _contained_child(
        learning_dir, "events", f"{event_type}.{subject_id}.json"
    )


def _learning_sequence(path_spec: Mapping[str, Any]) -> list[tuple[str, str]]:
    sequence: list[tuple[str, str]] = []
    for area in path_spec["areas"]:
        sequence.extend(("slice_completed", slice_id) for slice_id in area["slice_ids"])
        sequence.append(("checkpoint_answered", area["area_id"]))
    return sequence


def _slice_map_for_path(
    path_spec: Mapping[str, Any],
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    area_ids = {area["area_id"] for area in path_spec["areas"]}
    slice_map = _slice_mapping(slices, area_ids)
    required = {
        slice_id for area in path_spec["areas"] for slice_id in area["slice_ids"]
    }
    if set(slice_map) != required:
        raise SpecError("Learning event validation requires the exact slice set")
    return slice_map


def _learning_contract_digest(
    path_spec: Mapping[str, Any], slice_map: Mapping[str, Mapping[str, Any]]
) -> str:
    ordered_slices = [
        slice_map[slice_id]
        for area in path_spec["areas"]
        for slice_id in area["slice_ids"]
    ]
    return _content_digest({"path": path_spec, "slices": ordered_slices})


def _validate_slice_event(
    path: Path,
    record: Mapping[str, Any],
    path_spec: Mapping[str, Any],
    item: Mapping[str, Any],
    contract_digest: str,
) -> dict[str, Any]:
    expected = {
        "schema_version": 3,
        "record_type": "learning_event",
        "event_type": "slice_completed",
        "cycle_id": path_spec["cycle_id"],
        "slice_id": item["slice_id"],
        "area_id": item["area_id"],
        "learning_contract_digest": contract_digest,
        "slice_digest": _slice_digest(item),
        "mastery_effect": "progress_only",
    }
    for field, value in expected.items():
        if record.get(field) != value:
            raise SpecError(f"Slice completion {field} mismatch: {path}")
    _identifier(record.get("request_id"), f"{path}.request_id")
    _rfc3339(record.get("completed_at"), f"{path}.completed_at")
    return dict(record)


def _validate_checkpoint_event(
    path: Path,
    record: Mapping[str, Any],
    path_spec: Mapping[str, Any],
    area: Mapping[str, Any],
    contract_digest: str,
) -> dict[str, Any]:
    question = area["checkpoint"]
    expected_identity = {
        "schema_version": 3,
        "record_type": "learning_event",
        "event_type": "checkpoint_answered",
        "cycle_id": path_spec["cycle_id"],
        "area_id": area["area_id"],
        "question_id": question["question_id"],
        "learning_contract_digest": contract_digest,
        "question_digest": _question_digest(question),
        "knowledge_kernel_id": question["knowledge_kernel_id"],
        "concept_id": question["concept_id"],
        "scenario_id": question["scenario_id"],
        "scenario_fingerprint": question["scenario_fingerprint"],
        "question_family": question["question_family"],
        "correct_option_id": question["correct_option_id"],
        "independence": "feedback_exposed",
        "feedback_exposed": True,
        "feedback_timing": "immediate_after_commit",
    }
    for field, value in expected_identity.items():
        if record.get(field) != value:
            raise SpecError(f"Checkpoint {field} mismatch: {path}")
    _validate_display_order(question, record.get("displayed_option_order"))
    options = {item["id"]: item for item in question["options"]}
    selected_option_id = record.get("selected_option_id")
    if selected_option_id not in options:
        raise SpecError(f"Checkpoint selected option mismatch: {path}")
    selected = options[selected_option_id]
    expected_correct = selected_option_id == question["correct_option_id"]
    if record.get("is_correct") is not expected_correct:
        raise SpecError(f"Checkpoint correctness mismatch: {path}")
    expected_misconception = selected["misconception_tag"] or None
    if record.get("selected_misconception_tag") != expected_misconception:
        raise SpecError(f"Checkpoint misconception mismatch: {path}")
    _identifier(record.get("request_id"), f"{path}.request_id")
    _rfc3339(record.get("answered_at"), f"{path}.answered_at")
    return dict(record)


def _validated_learning_records(
    learning_dir: Path,
    path_spec: Mapping[str, Any],
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    slice_map = _slice_map_for_path(path_spec, slices)
    contract_digest = _learning_contract_digest(path_spec, slice_map)
    area_map = {area["area_id"]: area for area in path_spec["areas"]}
    expected_names = {
        f"slice_completed.{slice_id}.json"
        for slice_id in slice_map
    } | {
        f"checkpoint_answered.{area_id}.json"
        for area_id in area_map
    }
    events_dir = _contained_child(learning_dir, "events")
    if events_dir.exists() and not events_dir.is_dir():
        raise SpecError(f"Learning events path is not a directory: {events_dir}")
    if events_dir.is_dir():
        unexpected = sorted(
            path.name for path in events_dir.glob("*.json") if path.name not in expected_names
        )
        if unexpected:
            raise SpecError(f"Unexpected Learning event files: {unexpected}")

    slice_records: dict[str, dict[str, Any]] = {}
    checkpoint_records: dict[str, dict[str, Any]] = {}
    present_keys: set[str] = set()
    for slice_id, item in slice_map.items():
        path = _learning_event_path(learning_dir, "slice_completed", slice_id)
        if path.exists() and not path.is_file():
            raise SpecError(f"Learning event path is not a file: {path}")
        if path.is_file():
            slice_records[slice_id] = _validate_slice_event(
                path, read_json_object(path), path_spec, item, contract_digest
            )
            present_keys.add(f"slice_completed:{slice_id}")
    for area_id, area in area_map.items():
        path = _learning_event_path(learning_dir, "checkpoint_answered", area_id)
        if path.exists() and not path.is_file():
            raise SpecError(f"Learning event path is not a file: {path}")
        if path.is_file():
            checkpoint_records[area_id] = _validate_checkpoint_event(
                path, read_json_object(path), path_spec, area, contract_digest
            )
            present_keys.add(f"checkpoint_answered:{area_id}")

    sequence_keys = [f"{event_type}:{subject_id}" for event_type, subject_id in _learning_sequence(path_spec)]
    completed_keys: list[str] = []
    missing_seen = False
    for key in sequence_keys:
        if key in present_keys:
            if missing_seen:
                raise SpecError(f"Learning events are out of order at {key}")
            completed_keys.append(key)
        else:
            missing_seen = True
    return slice_records, checkpoint_records, completed_keys


def record_slice_completion(
    learning_dir: Path,
    path_spec: Mapping[str, Any],
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    slice_id: str,
    request_id: str,
) -> tuple[dict[str, Any], bool]:
    slice_id = _identifier(slice_id, "slice_id")
    request_id = _identifier(request_id, "request_id")
    slice_map = _slice_map_for_path(path_spec, slices)
    if slice_id not in slice_map:
        raise SpecError(f"Unknown slice_id: {slice_id}")
    slice_records, _, completed_keys = _validated_learning_records(
        learning_dir, path_spec, slice_map
    )
    if completed_keys:
        validate_choice_label_contract(
            path_spec, check_future_surfaces=False
        )
    else:
        validate_choice_description_contract(path_spec)
    path = _learning_event_path(learning_dir, "slice_completed", slice_id)
    if slice_id in slice_records:
        return _idempotent_existing(path, request_id=request_id)
    sequence = [f"{event_type}:{subject_id}" for event_type, subject_id in _learning_sequence(path_spec)]
    next_key = sequence[len(completed_keys)] if len(completed_keys) < len(sequence) else None
    if next_key != f"slice_completed:{slice_id}":
        raise IncompleteLearningError(f"Slice is not the next unlocked node: {slice_id}")
    completed = set(slice_records)
    missing = sorted(set(slice_map[slice_id]["prerequisites"]) - completed)
    if missing:
        raise IncompleteLearningError(f"Slice prerequisites are incomplete: {missing}")
    record = {
        "schema_version": 3,
        "record_type": "learning_event",
        "event_type": "slice_completed",
        "cycle_id": path_spec["cycle_id"],
        "slice_id": slice_id,
        "area_id": slice_map[slice_id]["area_id"],
        "learning_contract_digest": _learning_contract_digest(
            path_spec, slice_map
        ),
        "slice_digest": _slice_digest(slice_map[slice_id]),
        "request_id": request_id,
        "completed_at": utc_now(),
        "mastery_effect": "progress_only",
    }
    try:
        write_json_once(path, record)
    except FileExistsError:
        return _idempotent_existing(path, request_id=request_id)
    return record, True


def record_checkpoint_response(
    learning_dir: Path,
    path_spec: Mapping[str, Any],
    area_id: str,
    selected_option_id: str,
    displayed_option_order: list[str],
    request_id: str,
    *,
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    area_id = _identifier(area_id, "area_id")
    request_id = _identifier(request_id, "request_id")
    area = next((item for item in path_spec["areas"] if item["area_id"] == area_id), None)
    if area is None:
        raise SpecError(f"Unknown learning area: {area_id}")
    _, checkpoint_records, completed_keys = _validated_learning_records(
        learning_dir, path_spec, slices
    )
    if completed_keys:
        validate_choice_label_contract(
            path_spec, check_future_surfaces=False
        )
    else:
        validate_choice_description_contract(path_spec)
    path = _learning_event_path(learning_dir, "checkpoint_answered", area_id)
    if area_id in checkpoint_records:
        return _idempotent_existing(
            path, request_id=request_id, selected_option_id=selected_option_id
        )
    sequence = [f"{event_type}:{subject_id}" for event_type, subject_id in _learning_sequence(path_spec)]
    next_key = sequence[len(completed_keys)] if len(completed_keys) < len(sequence) else None
    if next_key != f"checkpoint_answered:{area_id}":
        raise IncompleteLearningError(
            f"Checkpoint is not the next unlocked node: {area_id}"
        )
    slice_records, _, _ = _validated_learning_records(learning_dir, path_spec, slices)
    completed = set(slice_records)
    missing = sorted(set(area["slice_ids"]) - completed)
    if missing:
        raise IncompleteLearningError(f"Area slices are incomplete: {missing}")
    question = area["checkpoint"]
    slice_map = _slice_map_for_path(path_spec, slices)
    selected_option_id = _identifier(selected_option_id, "selected_option_id")
    order = _validate_display_order(question, displayed_option_order)
    options = {item["id"]: item for item in question["options"]}
    if selected_option_id not in options:
        raise SpecError("selected_option_id is not a checkpoint option")
    selected = options[selected_option_id]
    record = {
        "schema_version": 3,
        "record_type": "learning_event",
        "event_type": "checkpoint_answered",
        "cycle_id": path_spec["cycle_id"],
        "area_id": area_id,
        "question_id": question["question_id"],
        "learning_contract_digest": _learning_contract_digest(
            path_spec, slice_map
        ),
        "question_digest": _question_digest(question),
        "knowledge_kernel_id": question["knowledge_kernel_id"],
        "concept_id": question["concept_id"],
        "scenario_id": question["scenario_id"],
        "scenario_fingerprint": question["scenario_fingerprint"],
        "question_family": question["question_family"],
        "displayed_option_order": order,
        "selected_option_id": selected_option_id,
        "selected_misconception_tag": selected["misconception_tag"] or None,
        "correct_option_id": question["correct_option_id"],
        "is_correct": selected_option_id == question["correct_option_id"],
        "independence": "feedback_exposed",
        "feedback_exposed": True,
        "feedback_timing": "immediate_after_commit",
        "request_id": request_id,
        "answered_at": utc_now(),
    }
    try:
        write_json_once(path, record)
    except FileExistsError:
        return _idempotent_existing(
            path, request_id=request_id, selected_option_id=selected_option_id
        )
    return record, True


def record_learning_event(
    learning_dir: Path,
    path_spec: Mapping[str, Any],
    event_type: str,
    subject_id: str,
    request_id: str,
    *,
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
    selected_option_id: str | None = None,
    displayed_option_order: list[str] | None = None,
) -> tuple[dict[str, Any], bool]:
    if event_type == "slice_completed":
        if slices is None:
            raise SpecError("slice completion requires slice files")
        return record_slice_completion(
            learning_dir, path_spec, slices, subject_id, request_id
        )
    if event_type == "checkpoint_answered":
        if slices is None:
            raise SpecError("checkpoint response requires slice files")
        if selected_option_id is None or displayed_option_order is None:
            raise SpecError("checkpoint response requires an option and displayed order")
        return record_checkpoint_response(
            learning_dir,
            path_spec,
            subject_id,
            selected_option_id,
            displayed_option_order,
            request_id,
            slices=slices,
        )
    raise SpecError(f"Unsupported learning event_type: {event_type}")


def learning_completion_state(
    learning_dir: Path,
    path_spec: Mapping[str, Any],
    *,
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    slice_records, checkpoint_records, completed_event_keys = _validated_learning_records(
        learning_dir, path_spec, slices
    )
    completed_slices = set(slice_records)
    required_slices = {
        slice_id for area in path_spec["areas"] for slice_id in area["slice_ids"]
    }
    missing_slices = sorted(required_slices - completed_slices)
    completed_checkpoints = set(checkpoint_records)
    required_areas = {area["area_id"] for area in path_spec["areas"]}
    missing_checkpoints = sorted(required_areas - completed_checkpoints)
    sequence_keys = [f"{event_type}:{subject_id}" for event_type, subject_id in _learning_sequence(path_spec)]
    return {
        "complete": not missing_slices and not missing_checkpoints,
        "completed_slice_ids": sorted(completed_slices & required_slices),
        "missing_slice_ids": missing_slices,
        "completed_checkpoint_area_ids": sorted(completed_checkpoints),
        "missing_checkpoint_area_ids": missing_checkpoints,
        "completed_slices": len(completed_slices & required_slices),
        "total_slices": len(required_slices),
        "completed_checkpoints": len(completed_checkpoints),
        "total_checkpoints": len(required_areas),
        "completed_event_keys": completed_event_keys,
        "next_event_key": (
            sequence_keys[len(completed_event_keys)]
            if len(completed_event_keys) < len(sequence_keys)
            else None
        ),
    }


def ensure_review_ready(
    learning_dir: Path,
    path_spec: Mapping[str, Any],
    *,
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    state = learning_completion_state(learning_dir, path_spec, slices=slices)
    if not state["complete"]:
        raise IncompleteLearningError(
            "Review is locked until every slice and area checkpoint is complete"
        )
    return state


def build_learning_report(
    learning_dir: Path,
    path_spec: Mapping[str, Any],
    *,
    slices: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    require_complete: bool = True,
    persist: bool = False,
) -> dict[str, Any]:
    slice_map = _slice_map_for_path(path_spec, slices)
    contract_digest = _learning_contract_digest(path_spec, slice_map)
    state = learning_completion_state(
        learning_dir, path_spec, slices=slice_map
    )
    if require_complete and not state["complete"]:
        raise IncompleteLearningError(
            f"Learning is incomplete: slices={state['missing_slice_ids']}, checkpoints={state['missing_checkpoint_area_ids']}"
        )
    checkpoint_results: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for area in path_spec["areas"]:
        path = _learning_event_path(
            learning_dir, "checkpoint_answered", area["area_id"]
        )
        if not path.is_file():
            continue
        record = _validate_checkpoint_event(
            path, read_json_object(path), path_spec, area, contract_digest
        )
        checkpoint = area["checkpoint"]
        if record.get("question_digest") != _question_digest(checkpoint):
            raise SpecError(f"Checkpoint question digest mismatch: {path}")
        _validate_display_order(checkpoint, record.get("displayed_option_order"))
        expected = record.get("selected_option_id") == checkpoint["correct_option_id"]
        if record.get("is_correct") is not expected:
            raise SpecError(f"Checkpoint correctness mismatch: {path}")
        result = {
            "area_id": area["area_id"],
            "question_id": checkpoint["question_id"],
            "knowledge_kernel_id": checkpoint["knowledge_kernel_id"],
            "is_correct": expected,
            "selected_option_id": record.get("selected_option_id"),
            "misconception_tag": record.get("selected_misconception_tag"),
        }
        checkpoint_results.append(result)
        if not expected:
            gaps.append(
                {
                    "gap_id": f"learning.{checkpoint['question_id']}",
                    "source": "learning_checkpoint",
                    "source_question_id": checkpoint["question_id"],
                    "area_id": area["area_id"],
                    "knowledge_kernel_id": checkpoint["knowledge_kernel_id"],
                    "core_proposition": checkpoint["core_proposition"],
                    "sources": checkpoint["sources"],
                    "misconception_tag": record.get("selected_misconception_tag"),
                }
            )
    report = {
        "schema_version": 3,
        "report_type": "learning_report",
        "cycle_id": path_spec["cycle_id"],
        **state,
        "checkpoint_results": checkpoint_results,
        "gaps": gaps,
        "review_ready": state["complete"],
        "area_results": [
            {
                "area_id": area["area_id"],
                "completed_slices": len(
                    set(area["slice_ids"]) & set(state["completed_slice_ids"])
                ),
                "total_slices": len(area["slice_ids"]),
                "checkpoint_complete": area["area_id"]
                in set(state["completed_checkpoint_area_ids"]),
                "checkpoint_correct": next(
                    (
                        item["is_correct"]
                        for item in checkpoint_results
                        if item["area_id"] == area["area_id"]
                    ),
                    None,
                ),
            }
            for area in path_spec["areas"]
        ],
        "mastery_effect": "learning_progress_only",
        "generated_at": utc_now(),
    }
    if persist:
        atomic_write_json(_contained_child(learning_dir, "report.json"), report)
    return report


def build_review_report(
    review_dir: Path,
    review_spec: Mapping[str, Any],
    assessment_report: Mapping[str, Any],
    learning_report: Mapping[str, Any] | None = None,
    *,
    require_complete: bool = True,
    persist: bool = False,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    responses, missing = _responses_for(
        review_dir, review_spec, require_complete=require_complete
    )
    prior_gaps = _combined_gap_records(assessment_report, learning_report)
    prior_gap_by_kernel: dict[str, list[dict[str, Any]]] = {}
    for gap in prior_gaps:
        prior_gap_by_kernel.setdefault(gap["knowledge_kernel_id"], []).append(gap)
    primary_review_kernels = {
        question["primary_kernel_id"] for question in review_spec["questions"]
    }
    directly_reviewed_gap_ids = {
        gap["gap_id"]
        for gap in prior_gaps
        if gap["knowledge_kernel_id"] in primary_review_kernels
    }
    not_directly_reviewed_gap_ids = {
        gap["gap_id"] for gap in prior_gaps
    } - directly_reviewed_gap_ids
    corrected_gap_ids: set[str] = set()
    remaining_gap_ids: set[str] = set()
    new_errors: list[dict[str, Any]] = []
    reinforced: list[dict[str, Any]] = []
    integration_results: list[dict[str, Any]] = []
    question_results: list[dict[str, Any]] = []
    for question in review_spec["questions"]:
        response = responses.get(question["question_id"])
        if response is None:
            continue
        primary_gaps = prior_gap_by_kernel.get(question["primary_kernel_id"], [])
        integrated_gaps = [
            gap
            for kernel in question["integrated_kernel_ids"]
            for gap in prior_gap_by_kernel.get(kernel, [])
        ]
        if response["is_correct"]:
            corrected_gap_ids.update(gap["gap_id"] for gap in primary_gaps)
            if not primary_gaps:
                reinforced.append(
                    {
                        "question_id": question["question_id"],
                        "knowledge_kernel_id": question["primary_kernel_id"],
                        "core_proposition": question["core_proposition"],
                    }
                )
        else:
            if primary_gaps:
                remaining_gap_ids.update(gap["gap_id"] for gap in primary_gaps)
            else:
                new_errors.append(
                    {
                        "question_id": question["question_id"],
                        "area_id": question["area_id"],
                        "knowledge_kernel_id": question["primary_kernel_id"],
                        "core_proposition": question["core_proposition"],
                        "misconception_tag": response.get("selected_misconception_tag"),
                    }
                )
        question_results.append(
            {
                "question_id": question["question_id"],
                "primary_kernel_id": question["primary_kernel_id"],
                "integrated_kernel_ids": question["integrated_kernel_ids"],
                "is_correct": response["is_correct"],
                "prior_gap_ids": [gap["gap_id"] for gap in primary_gaps],
                "integrated_gap_ids": [gap["gap_id"] for gap in integrated_gaps],
            }
        )
        if question["integrated_kernel_ids"]:
            integration_results.append(
                {
                    "question_id": question["question_id"],
                    "primary_kernel_id": question["primary_kernel_id"],
                    "integrated_kernel_ids": question["integrated_kernel_ids"],
                    "is_correct": response["is_correct"],
                }
            )
    all_prior_gap_ids = {gap["gap_id"] for gap in prior_gaps}
    remaining_gap_ids.update(all_prior_gap_ids - corrected_gap_ids)
    corrected_gap_ids -= remaining_gap_ids
    answered_in_order = [
        responses[question["question_id"]]
        for question in review_spec["questions"]
        if question["question_id"] in responses
    ]
    if answered_in_order:
        completion_anchor = answered_in_order[-1]["answered_at"]
        due_base = dt.datetime.fromisoformat(
            completion_anchor.replace("Z", "+00:00")
        )
    else:
        due_base = now or dt.datetime.now(dt.timezone.utc)
        completion_anchor = due_base.isoformat()
    due_date = (due_base.date() + dt.timedelta(days=3)).isoformat()
    delayed = [
        {"gap_id": gap_id, "due_date": due_date, "mode": "uncued"}
        for gap_id in sorted(remaining_gap_ids)
    ] + [
        {
            "gap_id": f"review.{item['question_id']}",
            "due_date": due_date,
            "mode": "uncued",
        }
        for item in new_errors
    ]
    report = {
        "schema_version": 3,
        "report_type": "review_report",
        "cycle_id": review_spec["cycle_id"],
        "complete": not missing,
        "answered": len(responses),
        "total": len(review_spec["questions"]),
        "question_results": question_results,
        "directly_reviewed_gap_ids": sorted(directly_reviewed_gap_ids),
        "not_directly_reviewed_gap_ids": sorted(not_directly_reviewed_gap_ids),
        "corrected_gap_ids": sorted(corrected_gap_ids),
        "remaining_gap_ids": sorted(remaining_gap_ids),
        "new_errors": new_errors,
        "reinforced_concepts": reinforced,
        "integration_results": integration_results,
        "delayed_review": delayed,
        "missing_question_ids": missing,
        "completion_anchor": completion_anchor,
        "generated_at": utc_now(),
    }
    if persist:
        atomic_write_json(_contained_child(review_dir, "report.json"), report)
    return report


__all__ = [
    "ConflictError",
    "IncompleteLearningError",
    "IncompletePhaseError",
    "PhaseLock",
    "SpecError",
    "atomic_write_json",
    "build_assessment_report",
    "build_learning_report",
    "build_review_report",
    "choice_description_is_safe",
    "choice_description_leaks_answer",
    "clamp",
    "ensure_batch_manifest",
    "ensure_review_ready",
    "learning_completion_state",
    "load_cycle",
    "read_json_object",
    "record_checkpoint_response",
    "record_learning_event",
    "record_response",
    "record_slice_completion",
    "response_completion_state",
    "resolve_cycle",
    "scenario_fingerprint",
    "validate_assessment_spec",
    "validate_batch_manifest",
    "validate_choice_description_contract",
    "validate_choice_label_contract",
    "validate_visible_context_contract",
    "validate_cycle",
    "validate_learning_path",
    "validate_learning_slice",
    "validate_review_spec",
    "write_json_once",
]
