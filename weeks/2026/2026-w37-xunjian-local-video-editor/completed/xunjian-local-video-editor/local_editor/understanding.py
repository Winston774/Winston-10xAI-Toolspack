"""Deterministic observations; perceptual claims always require media evidence.

No source file reads or model inference belongs here. Responses distinguish exact
project facts, heuristic concerns and the audiovisual work that remains unchecked.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re
from difflib import SequenceMatcher

from .core import (EditorError, _find, _number, clip_duration,
                   mapped_captions, project_duration, validate_project)


def _stable(kind: str, *parts) -> str:
    digest = hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()[:24]
    return f"{kind}-{digest}"


def normalize_range(project: dict, request: dict | None = None) -> dict:
    request = request or {}
    if not isinstance(request, dict):
        raise EditorError("觀察參數必須是物件。")
    if "revision" in request:
        revision = _number(request["revision"], "revision", 1, 2**53 - 1, True)
        if revision != project["version"]:
            raise EditorError("觀察版本已過期；請重新取得工作情境。", "version_conflict", 409)
    time_space = request.get("time_space", "timeline")
    if time_space not in ("timeline", "source"):
        raise EditorError("time_space 必須是 timeline 或 source。")
    detail = request.get("detail", "summary")
    if detail not in ("summary", "review"):
        raise EditorError("detail 必須是 summary 或 review。")
    result = {"project_id": project["id"], "revision": project["version"],
              "time_space": time_space, "detail": detail}
    duration = project_duration(project)
    if time_space == "source":
        media = _find(project["media"], request.get("media_id"), "素材")
        duration = media["duration"]
        if media["kind"] == "image":
            duration = max([5.] + [c["end"] for c in project["clips"] if c["media_id"] == media["id"]])
        result["media_id"] = media["id"]
    requested = request.get("range", {"start": 0., "end": duration})
    if not isinstance(requested, dict) or set(requested) != {"start", "end"}:
        raise EditorError("range 必須包含 start 與 end。")
    start = _number(requested["start"], "觀察起點", 0, 864000)
    end = _number(requested["end"], "觀察終點", 0, 864000)
    if end < start or (end == start and (duration > 0 or "range" in request)) or end > duration + 1e-6:
        raise EditorError("觀察範圍須位於所選時間空間內，且終點晚於起點。")
    result["range"] = {"start": min(start, duration), "end": min(end, duration)}
    result["available_duration"] = duration
    return result


def _overlaps(start: float, end: float, window: dict) -> bool:
    return start < window["end"] - 1e-7 and end > window["start"] + 1e-7


def cut_boundaries(project: dict, window: dict | None = None) -> list[dict]:
    """Boundary IDs depend on source edges and adjacent IDs, not shifted offsets."""
    duration = project_duration(project)
    events = {}
    for clip in project["clips"]:
        for side, at in (("right", clip["offset"]), ("left", clip["offset"] + clip_duration(clip))):
            events.setdefault(round(at, 9), {"left": [], "right": []})[side].append(clip)
    result = []
    for at, event in sorted(events.items()):
        if at <= 1e-7 or at >= duration - 1e-7:
            continue
        if window and not window["start"] - 1e-7 <= at <= window["end"] + 1e-7:
            continue
        left, right = event["left"], event["right"]
        edges = [(c["id"], "end", c["end"]) for c in left] + [(c["id"], "start", c["start"]) for c in right]
        result.append({"id": _stable("cut", sorted(edges)), "at": at,
                       "kind": "join" if left and right else "layer_end" if left else "layer_start",
                       "left": [{"clip_id": c["id"], "media_id": c["media_id"], "track": c["track"],
                                 "source_time": c["end"]} for c in left],
                       "right": [{"clip_id": c["id"], "media_id": c["media_id"], "track": c["track"],
                                  "source_time": c["start"]} for c in right],
                       "audiovisual_review": "unchecked"})
    return result


def _placements(project: dict, scope: dict) -> list[dict]:
    window = scope["range"]
    placements = []
    for index, clip in enumerate(project["clips"]):
        if scope["time_space"] == "source":
            if clip["media_id"] != scope["media_id"] or not _overlaps(clip["start"], clip["end"], window):
                continue
            source_start, source_end = max(clip["start"], window["start"]), min(clip["end"], window["end"])
            timeline_start = clip["offset"] + (source_start - clip["start"]) / clip["speed"]
            timeline_end = clip["offset"] + (source_end - clip["start"]) / clip["speed"]
        else:
            end = clip["offset"] + clip_duration(clip)
            if not _overlaps(clip["offset"], end, window):
                continue
            timeline_start, timeline_end = max(clip["offset"], window["start"]), min(end, window["end"])
            source_start = clip["start"] + (timeline_start - clip["offset"]) * clip["speed"]
            source_end = clip["start"] + (timeline_end - clip["offset"]) * clip["speed"]
        placements.append({"clip_id": clip["id"], "media_id": clip["media_id"], "track": clip["track"],
                           "project_list_index": index, "speed": clip["speed"],
                           "timeline_range": {"start": timeline_start, "end": timeline_end},
                           "source_range": {"start": source_start, "end": source_end},
                           "mapping": {"source_origin": clip["start"], "timeline_origin": clip["offset"],
                                       "source_seconds_per_timeline_second": clip["speed"]}})
    return placements


def _layer(project: dict, placement: dict, order: int | None, clip_lookup: dict, media_lookup: dict) -> dict:
    clip = clip_lookup[placement["clip_id"]]
    media = media_lookup[placement["media_id"]]
    transform = {key: clip[key] for key in ("scale", "x", "y", "rotation", "opacity")}
    return {**placement, "type": "clip", "composition_order": order,
            "media": {key: media.get(key) for key in ("id", "name", "kind", "width", "height", "duration", "has_audio")},
            "transform": transform,
            "compositing_rule": "aspect_fit_then_scale_rotate_center_offset_alpha" if order is not None else "audio_only",
            "color": {key: clip[key] for key in ("brightness", "contrast", "saturation")},
            "fades": {"in": clip["fade_in"], "out": clip["fade_out"], "time_space": "clip_timeline"},
            "audio": {"enabled": bool(media.get("has_audio") and not clip["muted"] and clip["volume"]),
                      "muted": clip["muted"], "gain": clip["volume"], "mixing": "sum_then_limiter"},
            "source_visual_content": {"status": "unexamined", "reason": "圖層參數不包含素材內部的人物、文字或操作語意。"}}


def _scope_captions(project: dict, scope: dict) -> list[dict]:
    if scope["time_space"] == "timeline":
        captions = mapped_captions(project)
    else:
        captions = []
        for item in project["captions"]:
            if item["media_id"] != scope["media_id"]:
                continue
            caption = copy.deepcopy(item)
            # Legacy data acquires the same stable IDs used by core reads/mapping.
            from .core import _discard_stale_words
            _discard_stale_words(caption)
            captions.append(caption)
    return [c for c in captions if _overlaps(c["start"], c["end"], scope["range"])]


def inspect_structure(project: dict, request: dict | None = None) -> dict:
    scope = normalize_range(project, request)
    placements = _placements(project, scope)
    visual_ids = [c["id"] for c in sorted(project["clips"], key=lambda c: c["track"] == "overlay")
                  if c["track"] != "audio"]
    orders = {clip_id: index + 1 for index, clip_id in enumerate(visual_ids)}
    clip_lookup = {c["id"]: c for c in project["clips"]}
    media_lookup = {m["id"]: m for m in project["media"]}
    layers = [_layer(project, p, orders.get(p["clip_id"]), clip_lookup, media_lookup) for p in placements]
    layers.sort(key=lambda layer: (layer["composition_order"] is None, layer["composition_order"] or 0))
    captions = _scope_captions(project, scope)
    limit = 80 if scope["detail"] == "summary" else 1000
    timelines = [scope["range"]] if scope["time_space"] == "timeline" else [p["timeline_range"] for p in placements]
    titles = [copy.deepcopy(t) for t in project.get("titles", [])
              if any(_overlaps(t["start"], t["end"], w) for w in timelines)]
    boundaries = [b for b in cut_boundaries(project)
                  if any(w["start"] - 1e-7 <= b["at"] <= w["end"] + 1e-7 for w in timelines)]
    result = {**scope, "brief": copy.deepcopy(project.get("brief", {})),
              "direction_status": {"provided_fields": sorted(project.get("brief", {})),
                                   "missing_fields": [key for key in ("goal", "audience", "pacing", "target_duration", "must_keep", "notes")
                                                      if project.get("brief", {}).get(key) in (None, "", [])],
                                   "inferred": False},
              "canvas": {key: project[key] for key in ("width", "height", "fps")},
              "composition": {"background": "#000000", "order": "video_list_order,overlay_list_order,captions,titles",
                              "coordinates": "project_pixels", "origin": "center_for_clip_and_title_offsets",
                              "source_observation": scope["time_space"] == "source"},
              "placements": placements[:limit], "layers": layers[:limit], "captions": captions[:limit],
              "caption_style": {**project["caption_style"], "font_family": "Microsoft JhengHei",
                                "margin_left": 30, "margin_right": 30,
                                "margin_vertical": max(20, int(project["height"] * .055)),
                                "wrap_style": "libass_smart_wrap"},
              "titles": titles[:limit], "cut_boundaries": boundaries[:limit],
              "counts": {"placements": len(placements), "layers": len(layers), "captions": len(captions),
                         "titles": len(titles), "cut_boundaries": len(boundaries)},
              "truncated": any(len(items) > limit for items in (placements, layers, captions, titles, boundaries)),
              "limit": limit, "uncertainties": ["尚未解讀素材內部畫面文字、人物與示範操作。",
                                                  "尚未聆聽此範圍；結構資料無法確認語音辨識正確或剪接自然。"]}
    if scope["detail"] == "summary":
        result["captions"] = [{key: value for key, value in c.items() if key != "words"} for c in result["captions"]]
        result["omitted_detail"] = ["逐字時間；以 detail=review 取得。"]
    return result


def _layout_estimates(project: dict, captions: list[dict]) -> list[dict]:
    style = project["caption_style"]
    font_size = style["font_size"]
    available_width = max(1., project["width"] - 60.)
    estimates = []
    for caption in captions:
        lines = caption["text"].split("\n")
        widths = [sum(font_size * (.55 if ord(char) < 256 else 1.) for char in line) for line in lines]
        estimated_lines = sum(max(1, math.ceil(width / available_width)) for width in widths)
        cps = len(re.sub(r"\s", "", caption["text"])) / max(.001, caption["end"] - caption["start"])
        concerns = []
        if estimated_lines > 2:
            concerns.append("estimated_more_than_two_lines")
        if estimated_lines * font_size * 1.25 > project["height"] - 2 * max(20, int(project["height"] * .055)):
            concerns.append("estimated_vertical_overflow")
        if cps > 9:
            concerns.append("fast_reading_rate")
        estimates.append({"caption_id": caption["id"], "start": caption["start"], "end": caption["end"],
                          "estimated_lines": estimated_lines, "characters_per_second": round(cps, 3),
                          "concerns": concerns, "status": "estimated",
                          "method": "unicode_width_heuristic", "rendered_bounds_checked": False,
                          "occlusion_checked": False})
    return estimates


def _normalized_text(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE).lower()


def analyze_structure(project: dict, request: dict | None = None) -> dict:
    scope = normalize_range(project, request)
    captions = sorted(_scope_captions(project, scope), key=lambda c: (c["start"], c["end"], c["id"]))
    characters = sum(len(_normalized_text(c["text"])) for c in captions)
    covered = sum(c["end"] - c["start"] for c in captions)
    candidates = []
    # Text context may extend beyond the bounded media capture. Keep the same
    # coordinate space and require every candidate to touch the selected range.
    analysis_limit = 1000
    window = scope["range"]
    context_range = {"start": max(0., window["start"] - 180),
                     "end": min(scope["available_duration"], window["end"] + 180)}
    context = _scope_captions(project, {**scope, "range": context_range})
    # Under the cap, prioritize selected cues and the nearest surrounding cues
    # so a long preceding transcript cannot exclude the requested selection.
    def distance(caption):
        return max(window["start"] - caption["end"], caption["start"] - window["end"], 0.)
    selected = sorted(sorted(context, key=lambda c: (not _overlaps(c["start"], c["end"], window),
                      distance(c), c["start"], c["id"]))[:analysis_limit],
                      key=lambda c: (c["start"], c["end"], c["id"]))
    comparison_limited = False
    for index, left in enumerate(selected):
        left_text = _normalized_text(left["text"])[:512]
        if len(left_text) < 4:
            continue
        for right in selected[index + 1:index + 41]:
            if right["start"] - left["end"] > 180:
                break
            if right["start"] < left["end"]:
                continue
            if not any(_overlaps(c["start"], c["end"], window) for c in (left, right)):
                continue
            right_text = _normalized_text(right["text"])[:512]
            if len(right_text) < 4:
                continue
            ratio = SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()
            if ratio < .72:
                continue
            candidates.append({"id": _stable("repeat", left["id"], right["id"]), "kind": "possible_retake",
                               "caption_ids": [left["id"], right["id"]],
                               "ranges": [{"start": c["start"], "end": c["end"]} for c in (left, right)],
                               "texts": [left["text"][:512], right["text"][:512]], "text_similarity": round(ratio, 4),
                               "texts_truncated": any(len(c["text"]) > 512 for c in (left, right)),
                               "detector": "normalized_text_sequence_similarity",
                               "context_before": selected[index - 1]["text"][:512] if index else None,
                               "context_after": next((c["text"][:512] for c in selected if c["start"] >= right["end"] and c["id"] != right["id"]), None),
                               "outside_observation_ranges": [{"start": c["start"], "end": c["end"]}
                                   for c in (left, right) if c["start"] < window["start"] or c["end"] > window["end"]],
                               "edit_recommendation": "review_only", "safe_to_delete": None,
                               "uncertainties": ["可能為刻意重述；相似度不是可刪除的信心值。", "示範畫面與敘事意義尚未確認。"]})
            if len(candidates) >= 200:
                break
        if index + 41 < len(selected) and selected[index + 41]["start"] - left["end"] <= 180:
            comparison_limited = True
        if len(candidates) >= 200:
            break
    layout = _layout_estimates(project, captions[:analysis_limit])
    return {**scope, "speech_pace": {"basis": "caption_text_and_cue_durations", "characters": characters,
                                     "cue_seconds_sum": covered,
                                     "characters_per_cue_second": round(characters / covered, 3) if covered else None,
                                     "actual_voiced_seconds": None, "status": "estimated"},
            "retake_candidates": candidates, "subtitle_layout": layout,
            "analysis_coverage": {"caption_count": len(captions), "analyzed_caption_count": min(len(captions), analysis_limit),
                                  "observation_range": window, "speech_pace_and_layout_range": window,
                                  "transcript_context": {"time_space": scope["time_space"], "range": context_range,
                                      "caption_count": len(context), "analyzed_caption_count": len(selected),
                                      "media_evidence_coverage": "observation_range_only",
                                      "candidate_rule": "at_least_one_cue_overlaps_observation_range",
                                      "note": "前後文僅來自字幕；超出觀察範圍的候選需另行取得聲畫證據。"},
                                  "comparison_horizon_seconds": 180, "max_later_cues": 40,
                                  "max_comparison_characters": 512,
                                  "truncated": len(context) > analysis_limit or comparison_limited or len(candidates) >= 200},
            "silence": {"status": "not_analyzed", "reason": "低音量偵測由媒體證據服務提供；字幕空隙不等同靜音。"},
            "visual_semantics": {"status": "not_analyzed"},
            "uncertainties": ["文字相似與節奏統計屬候選依據，無法判定跨段語意完整性或最佳剪法。",
                              "字幕行數僅估算；實際字型、換行、遮擋與音訊自然度需查看合成證據。"]}


def _timeline_gaps(project: dict, window: dict) -> list[dict]:
    intervals = sorted((max(c["offset"], window["start"]), min(c["offset"] + clip_duration(c), window["end"]))
                       for c in project["clips"] if c["track"] == "video" and
                       _overlaps(c["offset"], c["offset"] + clip_duration(c), window))
    cursor, gaps = window["start"], []
    for start, end in intervals:
        if start > cursor + 1e-6:
            gaps.append({"start": cursor, "end": start})
        cursor = max(cursor, end)
    if cursor < window["end"] - 1e-6:
        gaps.append({"start": cursor, "end": window["end"]})
    return gaps


def verify_project(project: dict, request: dict | None = None) -> dict:
    scope = normalize_range(project, request)
    issues = []
    try:
        validate_project(project)
        structure = {"status": "passed", "checks": ["project_schema", "source_bounds", "positive_durations", "unique_item_ids"]}
    except (EditorError, KeyError, TypeError, ZeroDivisionError) as error:
        return {**scope, "structure": {"status": "failed", "message": str(error)},
                "caption_alignment": {"status": "unchecked"}, "subtitle_layout": {"status": "unchecked"},
                "audiovisual": {"status": "unchecked", "naturalness": "unchecked"}, "overall_status": "needs_review"}
    captions = _scope_captions(project, scope)
    for caption in captions:
        if caption.get("alignment_status", "missing") != "valid":
            issues.append({"code": "caption_alignment_" + caption.get("alignment_status", "missing"),
                           "caption_id": caption["id"], "source_caption_id": caption.get("source_caption_id", caption["id"]),
                           "range": {"start": caption["start"], "end": caption["end"]},
                           "severity": "warning", "message": "缺少可用的逐字時間，無法保證切點未切斷詞語。"})
        for word in caption.get("words", []):
            if word.get("partial_word"):
                issues.append({"code": "partial_word_at_cut", "caption_id": caption["id"], "word_id": word["id"],
                               "source_word_id": word.get("source_word_id", word["id"]),
                               "range": {"start": word["start"], "end": word["end"]},
                               "severity": "warning", "message": "保留片段切入單詞內部，請試聽此切點。"})
    if scope["time_space"] == "source":
        for caption in mapped_captions(project):
            if caption["media_id"] != scope["media_id"] or not _overlaps(caption["source_start"], caption["source_end"], scope["range"]):
                continue
            for word in caption.get("words", []):
                if word.get("partial_word"):
                    issues.append({"code": "partial_word_at_cut", "caption_id": caption["id"], "word_id": word["id"],
                                   "source_word_id": word["source_word_id"], "time_space": "source",
                                   "range": {"start": word["source_start"], "end": word["source_end"]},
                                   "timeline_range": {"start": word["start"], "end": word["end"]},
                                   "severity": "warning", "message": "此來源單詞被時間軸切點切入內部，請試聽。"})
    gaps = _timeline_gaps(project, scope["range"]) if scope["time_space"] == "timeline" else []
    layout = _layout_estimates(project, captions[:1000])
    boundaries = cut_boundaries(project, scope["range"]) if scope["time_space"] == "timeline" else inspect_structure(project, request)["cut_boundaries"]
    brief = project.get("brief", {})
    target = brief.get("target_duration")
    return {**scope, "structure": structure,
            "brief_checks": {"target_duration": {"status": "measured" if target is not None else "unspecified",
                                                    "target_seconds": target, "actual_seconds": project_duration(project),
                                                    "difference_seconds": project_duration(project) - target if target is not None else None},
                             "must_keep": {"status": "unchecked", "items": brief.get("must_keep", []),
                                           "reason": "是否完整保留指定內容需要語意與聲畫證據，不以關鍵字存在冒充驗證。"},
                             "narrative_goal": "unchecked"},
            "timeline_gaps": {"status": "needs_review" if gaps else "passed", "gaps": gaps,
                              "basis": "main_video_track", "note": "主影片空隙可能有疊加、標題或音訊，未直接判定為錯誤。"},
            "caption_alignment": {"status": "needs_review" if issues else "passed" if captions else "unchecked",
                                  "issues": issues[:200], "issue_count": len(issues), "truncated": len(issues) > 200,
                                  "caption_count": len(captions),
                                  "coverage": "existing_captions_only; speech_without_captions_is_unchecked",
                                  "meaning_of_valid": "字幕文字與詞級區間符合結構契約，不代表辨識內容正確。"},
            "subtitle_layout": {"status": "estimated", "items": layout,
                                "truncated": len(captions) > 1000, "rendered_checked": False, "occlusion_checked": False},
            "audiovisual": {"status": "unchecked", "naturalness": "unchecked", "reviewed_ranges": [],
                            "unreviewed_ranges": [scope["range"]] if scope["range"]["end"] > scope["range"]["start"] else [],
                            "cut_boundaries": boundaries[:1000], "cut_boundary_count": len(boundaries),
                            "truncated": len(boundaries) > 1000, "reviewed_cut_ids": [],
                            "note": "抽樣影格或已產生預覽不等於已完整視聽確認。"},
            "summary": {"structure_passed": True, "caption_issue_count": len(issues), "main_video_gap_count": len(gaps),
                        "estimated_layout_concern_count": sum(bool(item["concerns"]) for item in layout),
                        "unreviewed_cut_count": len(boundaries), "audiovisual_reviewed": False},
            "overall_status": "needs_review"}


def describe_edit(before: dict, after: dict) -> dict:
    """Exact entity diffs plus explicit side effects for proposal and direct edits."""
    diff, affected = {}, {}
    for collection in ("clips", "captions", "titles"):
        previous = {item["id"]: item for item in before[collection]}
        current = {item["id"]: item for item in after[collection]}
        added, removed = sorted(current.keys() - previous.keys()), sorted(previous.keys() - current.keys())
        changed = []
        for item_id in sorted(current.keys() & previous.keys()):
            fields = {key: {"before": previous[item_id].get(key), "after": current[item_id].get(key)}
                      for key in previous[item_id].keys() | current[item_id].keys()
                      if previous[item_id].get(key) != current[item_id].get(key)}
            if fields:
                changed.append({"id": item_id, "fields": fields})
        diff[collection] = {"added": [current[item_id] for item_id in added],
                            "removed": [previous[item_id] for item_id in removed], "changed": changed}
        affected[collection] = sorted(set(added + removed + [item["id"] for item in changed]))
    diff["settings"] = {key: {"before": before.get(key), "after": after.get(key)}
                        for key in ("name", "width", "height", "fps", "caption_style") if before.get(key) != after.get(key)}
    diff["brief"] = ({"before": before.get("brief", {}), "after": after.get("brief", {})}
                     if before.get("brief", {}) != after.get("brief", {}) else {})
    before_mapped, after_mapped = mapped_captions(before), mapped_captions(after)
    old_map, new_map = {c["id"]: c for c in before_mapped}, {c["id"]: c for c in after_mapped}
    affected["mapped_captions"] = sorted(caption_id for caption_id in old_map.keys() | new_map.keys()
                                         if old_map.get(caption_id) != new_map.get(caption_id))
    warnings = []
    previous_caps = {c["id"]: c for c in before["captions"]}
    for caption in after["captions"]:
        previous = previous_caps.get(caption["id"], {})
        if caption.get("alignment_status") == "stale" and previous.get("alignment_status") != "stale":
            warnings.append({"code": "caption_alignment_invalidated", "caption_id": caption["id"],
                             "message": "字幕文字或時間變更已使逐字對齊失效；詞級安全剪輯需重新複核或提供已驗證詞級時間。",
                             "required_followup": "review_transcription_or_replace_validated_words"})
    partial = [(c["id"], w["id"]) for c in after_mapped for w in c.get("words", []) if w.get("partial_word")]
    if partial:
        warnings.append({"code": "partial_words_in_result", "word_ids": [word for _, word in partial],
                         "message": "結果包含被切入內部的單詞，請查看切點並試聽。"})
    before_cuts = {b["id"] for b in cut_boundaries(before)}
    new_cuts = [b for b in cut_boundaries(after) if b["id"] not in before_cuts]
    affected["cut_boundaries"] = [b["id"] for b in new_cuts]
    return {"before": {"duration": project_duration(before), "clip_count": len(before["clips"]),
                        "caption_count": len(before_mapped), "revision": before["version"]},
            "after": {"duration": project_duration(after), "clip_count": len(after["clips"]),
                       "caption_count": len(after_mapped), "revision": after["version"]},
            "diff": diff, "affected_ids": affected, "warnings": warnings, "new_cut_boundaries": new_cuts,
            "verification": {"structure": "passed", "rendered_preview": "not_generated",
                             "audiovisual_review": "unchecked"}}
