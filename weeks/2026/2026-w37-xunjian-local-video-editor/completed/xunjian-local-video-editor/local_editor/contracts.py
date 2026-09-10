"""Executable public contracts shared by HTTP, MCP and service entry points.

Only the JSON Schema vocabulary used here is implemented by ``validate``.
Schemas stay data-only so clients can discover every action without source reads.
"""
from __future__ import annotations

import json
import math
import re


def obj(properties=None, required=(), **extra):
    return {"type": "object", "properties": properties or {}, "required": list(required),
            "additionalProperties": False, **extra}


def num(low=0, high=86400):
    return {"type": "number", "minimum": low, "maximum": high}


def text(limit=10000, empty=False):
    return {"type": "string", "minLength": 0 if empty else 1, "maxLength": limit}


ID = {**text(100), "pattern": r"^[A-Za-z0-9_-]+$"}
BOOL = {"type": "boolean"}
TIME = num()
VERSION = {"type": "integer", "minimum": 1}
COLOR = {"type": "string", "pattern": r"^#[0-9a-fA-F]{6}$"}
RANGE = obj({"start": TIME, "end": TIME}, ["start", "end"])
TRACK = {"type": "string", "enum": ["video", "overlay", "audio"]}
WORD = obj({"id": ID, "text": text(1000, True), "start": TIME, "end": TIME,
            "probability": num(0, 1)}, ["text", "start", "end"])
WORDS = {"type": "array", "items": WORD, "maxItems": 10000}
CLIP = {"media_id": ID, "track": TRACK, "start": TIME, "end": TIME, "offset": TIME,
        "speed": num(.1, 16), "volume": num(0, 4), "muted": BOOL, "opacity": num(0, 1),
        "scale": num(.05, 4), "x": num(-32768, 32768), "y": num(-32768, 32768),
        "rotation": num(-360, 360), "brightness": num(-1, 1), "contrast": num(0, 3),
        "saturation": num(0, 3), "fade_in": num(0, 600), "fade_out": num(0, 600)}
TITLE = {"text": text(), "start": TIME, "end": TIME, "x": num(-32768, 32768),
         "y": num(-32768, 32768), "font_size": num(8, 300), "color": COLOR}
CAPTION = {"id": ID, "media_id": ID, "text": text(empty=True), "start": TIME, "end": TIME, "words": WORDS,
           "alignment_status": {"type": "string", "enum": ["valid", "stale", "missing"]}}
STYLE = {"font_size": num(8, 250), "color": COLOR, "background": COLOR,
         "position": {"type": "string", "enum": ["top", "center", "bottom"]}}
SETTINGS = {"width": {"type": "integer", "minimum": 128, "maximum": 7680},
            "height": {"type": "integer", "minimum": 128, "maximum": 4320}, "fps": num(1, 120)}
BRIEF = {"goal": text(10000, True), "audience": text(10000, True), "pacing": text(10000, True),
         "target_duration": {"anyOf": [num(), {"type": "null"}]}, "must_keep": {"type": "array", "items": text(2000), "maxItems": 200},
         "notes": text(10000, True)}


def wrapped(properties, name, required=()):
    direct = obj(properties, required, minProperties=1)
    return {"oneOf": [direct, obj({name: direct}, [name])]}


def update(key, properties):
    # Existing clients may use id or entity_id; nested changes is canonical.
    variants = []
    for identifier in (key, "id"):
        variants.append(obj({identifier: ID, "changes": obj(properties, minProperties=1)}, [identifier, "changes"]))
        variants.append(obj({identifier: ID, **properties}, [identifier], minProperties=2))
    return {"oneOf": variants}


def identified(key, extra=None, required=()):
    return {"oneOf": [obj({identifier: ID, **(extra or {})}, [identifier, *required])
                      for identifier in (key, "id")]}


ACTION_PARAMS = {
    "clip_trim_at": obj({"clip_id": ID, "at": TIME, "side": {"enum": ["before", "after"]},
                         "ripple": BOOL}, ["clip_id", "at", "side"]),
    "caption_cut": obj({"caption_id": ID, "clip_id": ID, "text": text(),
                        "selection": obj({"start": {"type": "integer", "minimum": 0},
                                          "end": {"type": "integer", "minimum": 1}}, ["start", "end"])},
                       ["caption_id", "clip_id", "text"]),
    "clip_paste": obj({"at": TIME, "clips": {"type": "array", "minItems": 1, "maxItems": 1000,
                       "items": obj(CLIP, ["media_id", "start", "end", "offset"])}}, ["at", "clips"]),
    "clip_move_many": obj({"clip_ids": {"type": "array", "items": ID, "minItems": 1, "maxItems": 1000, "uniqueItems": True},
                           "delta": num(-86400, 86400)}, ["clip_ids", "delta"]),
    "clip_delete_many": obj({"clip_ids": {"type": "array", "items": ID, "minItems": 1, "maxItems": 1000, "uniqueItems": True},
                             "ripple": BOOL}, ["clip_ids"]),
    "rename": obj({"name": text(200)}, ["name"]),
    "settings": wrapped(SETTINGS, "settings"),
    "brief_update": wrapped(BRIEF, "brief"),
    "clip_add": wrapped({"id": ID, **CLIP}, "clip", ["media_id"]),
    "clip_update": update("clip_id", CLIP),
    "clip_move": update("clip_id", {"offset": TIME, "track": TRACK}),
    "clip_split": identified("clip_id", {"at": TIME}, ["at"]),
    "clip_delete": identified("clip_id", {"ripple": BOOL}),
    "captions_set": obj({"media_id": ID, "captions": {"type": "array", "maxItems": 100000,
                            "items": obj(CAPTION, ["text", "start", "end"])}}, ["captions"]),
    "caption_update": update("caption_id", {k: v for k, v in CAPTION.items() if k not in {"id", "alignment_status"}}),
    "caption_delete": identified("caption_id"),
    "caption_style": wrapped(STYLE, "style"),
    "title_add": wrapped({"id": ID, **TITLE}, "title", ["text", "start", "end"]),
    "title_update": update("title_id", TITLE),
    "title_delete": identified("title_id"),
    "titles_set": obj({"titles": {"type": "array", "maxItems": 100000,
                                 "items": obj({"id": ID, **TITLE}, ["text", "start", "end"])}}, ["titles"]),
    "undo": obj(), "redo": obj(),
    "smart_cut_apply": obj({"plan_id": ID, "candidate_ids": {"type": "array", "items": ID,
                                      "minItems": 1, "maxItems": 10000, "uniqueItems": True}},
                           ["plan_id", "candidate_ids"]),
}
EDIT_ACTIONS = [key for key in ACTION_PARAMS if key != "smart_cut_apply"]
BATCH_ACTIONS = [key for key in ACTION_PARAMS if key not in {"undo", "redo"}]
# Advertise one canonical spelling per action to keep tool discovery compact.
# HTTP/service validation preserves already-supported aliases for existing UI.
CANONICAL_ACTION_PARAMS = {name: schema["oneOf"][0] if "oneOf" in schema else schema
                           for name, schema in ACTION_PARAMS.items()}


def operation_schema(*, batch=False):
    names = BATCH_ACTIONS if batch else EDIT_ACTIONS
    return {"oneOf": [obj({"action": {"const": name}, "params": CANONICAL_ACTION_PARAMS[name]}, ["action", "params"])
                      for name in names]}


ASR_OPTIONS = obj({"model_path": text(32768, True), "model": text(200),
    "device": {"type": "string", "enum": ["cpu", "cuda", "auto"]},
    "compute_type": {"type": "string", "enum": ["default", "auto", "int8", "int8_float16", "int8_float32", "int8_bfloat16", "float16", "float32", "bfloat16"]},
    "language": text(32), "timeout": num(30, 14400),
    "cpu_threads": {"type": "integer", "minimum": 1, "maximum": 64},
    "beam_size": {"type": "integer", "minimum": 1, "maximum": 20},
    "initial_prompt": text(10000, True), "traditional_chinese": BOOL})
EXPORT_OPTIONS = obj({**SETTINGS, "crf": {"type": "integer", "minimum": 0, "maximum": 51},
    "preset": {"type": "string", "enum": ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]},
    "timeout": num(10, 28800), "burn_captions": BOOL, "denoise": BOOL, "normalize_audio": BOOL})
RANGE_FIELDS = {"expected_version": VERSION, "time_space": {"type": "string", "enum": ["source", "timeline"]},
                "range": RANGE, "media_id": ID, "edit_id": ID,
                "preview_side": {"type": "string", "enum": ["before", "after"]}}
SAMPLING = obj({"strategy": {"enum": ["uniform", "cut_boundaries"]},
    "offset_frames": {"type": "array", "items": {"type": "integer", "minimum": -30, "maximum": 30},
                      "minItems": 1, "maxItems": 9, "uniqueItems": True}}, ["strategy"])
ACCEPTANCE_CHECKS = {"type": "array", "maxItems": 20, "items": {"oneOf": [
    obj({"kind": {"const": "no_timeline_gaps"}}, ["kind"]),
    obj({"kind": {"const": "duration_between"}, "min": TIME, "max": TIME}, ["kind", "min", "max"]),
    obj({"kind": {"const": "no_black_frames"}, "range": RANGE}, ["kind", "range"])]}}
INSPECT_SCHEMA = obj({**RANGE_FIELDS, "sampling": SAMPLING, "scan_black_frames": BOOL,
    "include": {"type": "array", "minItems": 1, "maxItems": 7, "uniqueItems": True,
                "items": {"type": "string", "enum": ["frames", "composite_frames", "audio", "video", "transcript", "layers", "cut_boundaries"]}},
    "max_frames": {"type": "integer", "minimum": 1, "maximum": 8},
    "detail": {"type": "string", "enum": ["summary", "review"]}}, ["expected_version", "time_space", "range"])
ANALYZE_SCHEMA = obj({**RANGE_FIELDS, "options": obj({"threshold_db": num(-80, -5),
    "min_silence": num(.1, 10), "keep_pause": num(0, 5), "detect_silence": BOOL,
    "detect_fillers": BOOL, "detect_repeats": BOOL, "visual_change_threshold": num(.001, 1)}),
    "max_frames": {"type": "integer", "minimum": 1, "maximum": 8}}, ["expected_version", "time_space", "range"])
PREPARE_EDIT_SCHEMA = obj({"expected_version": VERSION, "intent": text(10000),
    "operations": {"type": "array", "items": operation_schema(batch=True), "minItems": 1, "maxItems": 100},
    "preview_range": RANGE, "checks": ACCEPTANCE_CHECKS}, ["expected_version", "intent", "operations"])
APPLY_EDIT_SCHEMA = obj({"expected_version": VERSION, "edit_id": ID}, ["expected_version", "edit_id"])
VERIFY_EDIT_SCHEMA = obj({"expected_version": VERSION, "edit_id": ID, "range": RANGE,
    "preview_side": {"type": "string", "enum": ["before", "after"]}}, ["expected_version"])
REVIEW_CAPTION_SCHEMA = obj({"expected_version": VERSION, "caption_id": ID,
    "options": obj({**ASR_OPTIONS["properties"], "padding": num(0, 2)})}, ["expected_version", "caption_id"])
RECORD_REVIEW_SCHEMA = obj({"expected_version": VERSION, "evidence_id": ID, "edit_id": ID,
    "preview_side": {"type": "string", "enum": ["before", "after"]},
    "file_ids": {"type": "array", "items": ID, "minItems": 1, "maxItems": 12, "uniqueItems": True},
    "reviewer": text(120), "checks": {"type": "array", "items": {"type": "string", "enum": ["visual", "audio", "subtitle_layout"]},
                                     "minItems": 1, "maxItems": 3, "uniqueItems": True},
    "outcome": {"type": "string", "enum": ["pass", "issue"]}, "notes": text(4000)},
    ["expected_version", "evidence_id", "file_ids", "reviewer", "checks", "outcome", "notes"])
HTTP_SCHEMAS = {"inspect": INSPECT_SCHEMA, "analyze": ANALYZE_SCHEMA, "edits": PREPARE_EDIT_SCHEMA,
                "edits/apply": APPLY_EDIT_SCHEMA, "verify": VERIFY_EDIT_SCHEMA,
                "captions/review": REVIEW_CAPTION_SCHEMA, "reviews": RECORD_REVIEW_SCHEMA}


def validate(value, schema, path="arguments"):
    for keyword in ("allOf", "anyOf", "oneOf"):
        if keyword not in schema:
            continue
        matches, errors = 0, []
        for variant in schema[keyword]:
            try:
                validate(value, variant, path)
                matches += 1
            except ValueError as exc:
                errors.append(str(exc))
        if ((keyword == "allOf" and matches != len(schema[keyword]))
                or (keyword == "anyOf" and not matches) or (keyword == "oneOf" and matches != 1)):
            raise ValueError(f"{path} 不符合欄位契約：" + (errors[0] if errors else "只能符合一種參數格式"))
    kind = schema.get("type")
    checks = {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str),
              "boolean": isinstance(value, bool), "integer": isinstance(value, int) and not isinstance(value, bool),
              "number": isinstance(value, (int, float)) and not isinstance(value, bool), "null": value is None}
    if kind and not checks[kind]:
        raise ValueError(f"{path} 必須為 {kind}")
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{path} 必須為 {schema['const']}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} 不在支援清單中")
    if kind == "object":
        missing = [key for key in schema.get("required", []) if key not in value]
        if missing:
            raise ValueError(f"{path} 缺少必要欄位：{', '.join(missing)}")
        properties = schema.get("properties", {})
        unknown = set(value) - set(properties)
        if schema.get("additionalProperties") is False and unknown:
            raise ValueError(f"{path} 含不支援欄位：{', '.join(sorted(unknown))}")
        if len(value) < schema.get("minProperties", 0):
            raise ValueError(f"{path} 至少需指定一個可修改欄位")
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], f"{path}.{key}")
    elif kind == "array":
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", math.inf):
            raise ValueError(f"{path} 筆數超出範圍")
        for index, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{path}[{index}]")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            raise ValueError(f"{path} 不可重複")
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", math.inf):
            raise ValueError(f"{path} 文字長度超出範圍")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ValueError(f"{path} 格式錯誤")
    elif kind in {"number", "integer"}:
        if ((isinstance(value, float) and not math.isfinite(value))
                or not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf)):
            raise ValueError(f"{path} 數值超出範圍")


def validate_action(action, params, *, batch=False):
    allowed = BATCH_ACTIONS if batch else EDIT_ACTIONS
    if action not in allowed:
        raise ValueError(f"不支援的剪輯動作：{action}")
    validate(params, ACTION_PARAMS[action], f"{action}.params")


def validate_request(operation, data):
    """Cross-field semantics augment the discoverable field schemas."""
    schema = HTTP_SCHEMAS.get(operation)
    if schema:
        validate(data, schema)
    if "preview_side" in data and not data.get("edit_id"):
        raise ValueError("preview_side 僅可搭配 edit_id 指定提案的 before／after 快照")
    if operation in {"inspect", "analyze"}:
        bounds = data["range"]
        if not 0 < bounds["end"] - bounds["start"] <= 30:
            raise ValueError("觀察／分析區間必須大於 0 且最多 30 秒；長影片請分段取得證據")
        if data["time_space"] == "source" and not data.get("media_id"):
            raise ValueError("source 時間空間必須指定 media_id")
        if data["time_space"] == "timeline" and data.get("media_id"):
            raise ValueError("timeline 使用完整合成，請勿指定 media_id")
        if data.get("sampling", {}).get("strategy") == "cut_boundaries" and data["time_space"] != "timeline":
            raise ValueError("切點取樣僅支援 timeline 時間空間")
        if data.get("scan_black_frames") and data["time_space"] != "timeline":
            raise ValueError("黑畫面掃描僅支援 timeline 合成證據")
    if operation == "edits":
        validate_checks(data.get("checks", []))
        for entry in data["operations"]:
            validate_action(entry["action"], entry["params"], batch=True)
    if "preview_range" in data or (operation == "verify" and "range" in data):
        bounds = data.get("preview_range", data.get("range"))
        if not 0 < bounds["end"] - bounds["start"] <= 30:
            raise ValueError("預覽／驗證區間必須大於 0 且最多 30 秒")


def validate_checks(checks):
    validate(checks, ACCEPTANCE_CHECKS, "checks")
    for check in checks:
        if check["kind"] == "duration_between" and check["min"] > check["max"]:
            raise ValueError("驗收最短時長不可大於最長時長")
        if check["kind"] == "no_black_frames":
            bounds = check["range"]
            if not 0 < bounds["end"] - bounds["start"] <= 30:
                raise ValueError("黑畫面驗收區間必須大於 0 且最多 30 秒")
