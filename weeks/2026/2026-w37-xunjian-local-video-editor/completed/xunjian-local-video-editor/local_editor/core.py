"""Persistent, versioned domain operations for the local video workbench.

All API and MCP writes go through ProjectStore. Media paths are references only;
no operation in this module reads, overwrites or deletes a source media file.
"""
from __future__ import annotations

import copy
import json
import math
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EditorError(ValueError):
    def __init__(self, message: str, code: str = "invalid_input", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status
        self.status_code = status


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _number(value: Any, field: str, low: float = 0, high: float = 86400,
            integer: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EditorError(f"「{field}」必須是數字。")
    if (isinstance(value, float) and not math.isfinite(value)) or not low <= value <= high:
        raise EditorError(f"「{field}」必須介於 {low} 至 {high}，且為有限數字。")
    if integer and int(value) != value:
        raise EditorError(f"「{field}」必須是整數。")
    return int(value) if integer else float(value)


def _text(value: Any, field: str, max_length: int = 10000, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > max_length or (not empty and not value.strip()):
        raise EditorError(f"「{field}」必須是有效文字（最多 {max_length} 字）。")
    return value


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise EditorError("資料含無效數值或無法儲存的內容。") from exc


def _find(items: list[dict], item_id: Any, kind: str) -> dict:
    for item in items:
        if item["id"] == item_id:
            return item
    raise EditorError(f"找不到指定的{kind}。", "not_found", 404)


CLIP_DEFAULTS = {
    "track": "video", "start": 0.0, "offset": 0.0, "speed": 1.0,
    "volume": 1.0, "muted": False, "opacity": 1.0, "scale": 1.0,
    "x": 0.0, "y": 0.0, "rotation": 0.0, "brightness": 0.0,
    "contrast": 1.0, "saturation": 1.0, "fade_in": 0.0, "fade_out": 0.0,
}
CLIP_FIELDS = set(CLIP_DEFAULTS) | {"end", "media_id"}
CAPTION_STYLE = {"font_size": 48, "color": "#ffffff", "background": "#000000", "position": "bottom"}
EDIT_ACTIONS = frozenset({"rename", "settings", "clip_add", "clip_update", "clip_move",
                          "clip_split", "clip_delete", "clip_move_many", "clip_delete_many", "captions_set", "caption_update",
                          "caption_delete", "titles_set", "title_add", "title_update",
                          "title_delete", "caption_style", "smart_cut_apply", "brief_update", "caption_cut", "clip_paste", "clip_trim_at"})
BRIEF_FIELDS = frozenset({"goal", "audience", "pacing", "target_duration", "must_keep", "notes"})


def clip_duration(clip: dict) -> float:
    return (clip["end"] - clip["start"]) / clip["speed"]


def project_duration(project: dict) -> float:
    ends = [c["offset"] + clip_duration(c) for c in project["clips"]]
    ends.extend(t["end"] for t in project.get("titles", []))
    return max(ends, default=0.0)


def _color(value: Any, field: str) -> str:
    import re
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise EditorError(f"「{field}」需使用 #RRGGBB 色碼。")
    return value


def _validate_media(media: dict) -> None:
    _text(media.get("id"), "媒體 ID", 128)
    _text(media.get("name"), "媒體名稱", 1024)
    _text(media.get("path"), "媒體路徑", 32768)
    if media.get("kind") not in ("video", "audio", "image"):
        raise EditorError("媒體種類須為 video、audio 或 image。")
    _number(media.get("duration", 0), "媒體時長", 0 if media["kind"] == "image" else 0.000001)
    for field in ("width", "height"):
        _number(media.get(field, 0), field, 0, 32768, True)
    if not isinstance(media.get("has_audio", False), bool):
        raise EditorError("has_audio 必須是布林值。")


def _validate_clip(clip: dict, media: dict) -> None:
    _text(clip["id"], "片段 ID", 128)
    if clip.get("track") not in ("video", "audio", "overlay"):
        raise EditorError("軌道須為 video、audio 或 overlay。")
    if clip["track"] in ("video", "overlay") and media["kind"] == "audio":
        raise EditorError("音訊素材只能放入音訊軌。")
    _number(clip.get("start"), "來源起點")
    _number(clip.get("end"), "來源終點", 0.000001)
    if clip["end"] <= clip["start"]:
        raise EditorError("片段終點必須晚於起點。")
    if media["kind"] != "image" and clip["end"] > media["duration"] + 1e-6:
        raise EditorError("片段範圍超出來源媒體時長。")
    _number(clip.get("offset"), "時間軸位置")
    for field, low, high in (("speed", .1, 16), ("volume", 0, 4), ("opacity", 0, 1),
                             ("scale", .05, 4), ("x", -32768, 32768), ("y", -32768, 32768),
                             ("rotation", -360, 360), ("brightness", -1, 1),
                             ("contrast", 0, 3), ("saturation", 0, 3),
                             ("fade_in", 0, 600), ("fade_out", 0, 600)):
        _number(clip.get(field), field, low, high)
    if not isinstance(clip.get("muted"), bool):
        raise EditorError("muted 必須是布林值。")
    if clip["fade_in"] > clip_duration(clip) or clip["fade_out"] > clip_duration(clip):
        raise EditorError("淡入、淡出時間不可超過片段時長。")


def _validate_caption(caption: dict, project: dict) -> None:
    _text(caption.get("id"), "字幕 ID", 128)
    media = _find(project["media"], caption.get("media_id"), "媒體")
    _text(caption.get("text"), "字幕", 10000, empty=True)
    _number(caption.get("start"), "字幕起點")
    _number(caption.get("end"), "字幕終點", .000001)
    if caption["end"] <= caption["start"] or caption["end"] > media["duration"] + 1e-6:
        raise EditorError("字幕時間必須位於來源媒體範圍內，且終點晚於起點。")
    if "words" in caption:
        words = caption["words"]
        if not isinstance(words, list) or len(words) > 10000:
            raise EditorError("逐字時間必須是陣列，最多 10000 筆。")
        previous_start = -1.0
        word_ids = set()
        for word in words:
            if not isinstance(word, dict):
                raise EditorError("每筆逐字時間必須是物件。")
            _text(word.get("text"), "逐字文字", 1000, empty=True)
            if "id" in word:
                _text(word["id"], "單詞 ID", 128)
                if word["id"] in word_ids:
                    raise EditorError("同一句字幕的單詞 ID 不可重複。")
                word_ids.add(word["id"])
            if "probability" in word:
                _number(word["probability"], "單詞機率", 0, 1)
            _number(word.get("start"), "逐字起點")
            _number(word.get("end"), "逐字終點")
            if (word["end"] < word["start"] or word["start"] < caption["start"] - 1e-6
                    or word["end"] > caption["end"] + 1e-6 or word["start"] < previous_start):
                raise EditorError("逐字時間必須依序排列，且位於所屬字幕範圍內。")
            previous_start = word["start"]
    if caption.get("alignment_status", "missing") not in ("valid", "stale", "missing"):
        raise EditorError("字幕對齊狀態無效。")


def _discard_stale_words(caption: dict) -> None:
    """A manual transcript replacement cannot reuse alignment of different text."""
    words = caption.get("words")
    if (isinstance(caption.get("text"), str) and isinstance(words, list)
            and all(isinstance(w, dict) and isinstance(w.get("text"), str) for w in words)):
        normalized_text = re.sub(r"\s+", "", caption.get("text", ""))
        normalized_words = re.sub(r"\s+", "", "".join(w["text"] for w in words))
        if normalized_text != normalized_words:
            caption.pop("words", None)
            caption["alignment_status"] = "stale"
        elif words:
            for index, word in enumerate(words):
                word.setdefault("id", uuid.uuid5(uuid.NAMESPACE_URL,
                    f"caption:{caption['id']}:word:{index}:{word.get('start')}:{word.get('end')}:{word['text']}").hex)
            caption["alignment_status"] = "valid"
        else:
            caption["alignment_status"] = "stale" if caption.get("alignment_status") == "stale" else "missing"
    elif "words" not in caption:
        caption["alignment_status"] = "stale" if caption.get("alignment_status") == "stale" else "missing"


def _normalize_alignment(project: dict) -> dict:
    """Add deterministic legacy word IDs on read without changing the project version."""
    for caption in project.get("captions", []):
        _discard_stale_words(caption)
    return project


def _validate_brief(brief: dict) -> None:
    if not isinstance(brief, dict) or set(brief) - BRIEF_FIELDS:
        raise EditorError("剪輯方向只接受 goal、audience、pacing、target_duration、must_keep、notes。")
    for key, value in brief.items():
        if key == "target_duration":
            if value is not None:
                _number(value, "目標時長")
        elif key == "must_keep":
            if not isinstance(value, list) or len(value) > 200:
                raise EditorError("must_keep 必須是最多 200 項的文字陣列。")
            for item in value:
                _text(item, "必須保留的內容", 2000)
        else:
            _text(value, key, 10000, empty=True)


def _validate_title(title: dict) -> None:
    _text(title.get("id"), "文字 ID", 128)
    _text(title.get("text"), "文字", 10000)
    _number(title.get("start"), "文字起點")
    _number(title.get("end"), "文字終點", .000001)
    if title["end"] <= title["start"]:
        raise EditorError("文字終點必須晚於起點。")
    _number(title.get("x", 0), "文字 x", -32768, 32768)
    _number(title.get("y", 0), "文字 y", -32768, 32768)
    _number(title.get("font_size", 48), "文字大小", 8, 300)
    _color(title.get("color", "#ffffff"), "文字顏色")


def validate_project(project: dict) -> None:
    _text(project["name"], "專案名稱", 200)
    _number(project["width"], "畫布寬度", 128, 7680, True)
    _number(project["height"], "畫布高度", 128, 4320, True)
    _number(project["fps"], "影格率", 1, 120)
    if "brief" in project:
        _validate_brief(project["brief"])
    for collection in ("media", "clips", "captions", "titles"):
        if not isinstance(project[collection], list) or len(project[collection]) > 100_000:
            raise EditorError("專案項目格式錯誤或數量超出上限。")
        if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in project[collection]):
            raise EditorError("專案項目必須是具有文字 ID 的物件。")
        ids = [item.get("id") for item in project[collection]]
        if len(set(ids)) != len(ids):
            raise EditorError(f"{collection} 不可包含重複 ID。")
    for media in project["media"]:
        _validate_media(media)
    for clip in project["clips"]:
        _validate_clip(clip, _find(project["media"], clip.get("media_id"), "媒體"))
        _number(clip["x"], "影像 x", -project["width"] * 4, project["width"] * 4)
        _number(clip["y"], "影像 y", -project["height"] * 4, project["height"] * 4)
    for caption in project["captions"]:
        _validate_caption(caption, project)
    for title in project["titles"]:
        _validate_title(title)
        _number(title.get("x", 0), "文字 x", -project["width"] * 4, project["width"] * 4)
        _number(title.get("y", 0), "文字 y", -project["height"] * 4, project["height"] * 4)
    style = project["caption_style"]
    if set(style) - set(CAPTION_STYLE):
        raise EditorError("字幕樣式包含不支援的欄位。")
    _number(style["font_size"], "字幕大小", 8, 250)
    _color(style["color"], "字幕顏色")
    _color(style["background"], "字幕背景")
    if style["position"] not in ("top", "center", "bottom"):
        raise EditorError("字幕位置須為 top、center 或 bottom。")
    _json(project)


def mapped_captions(project: dict) -> list[dict]:
    """Map immutable source caption times through every video clip placement."""
    mapped = []
    for clip in project["clips"]:
        if clip["track"] != "video":
            continue
        for original in project["captions"]:
            caption = copy.deepcopy(original)
            _discard_stale_words(caption)
            if caption["media_id"] != clip["media_id"]:
                continue
            start, end = max(caption["start"], clip["start"]), min(caption["end"], clip["end"])
            if end - start <= 1e-7:
                continue
            item = {**caption, "id": f"{caption['id']}:{clip['id']}",
                           "source_caption_id": caption["id"], "clip_id": clip["id"],
                           "source_start": start, "source_end": end,
                           "start": clip["offset"] + (start - clip["start"]) / clip["speed"],
                           "end": clip["offset"] + (end - clip["start"]) / clip["speed"]}
            if caption.get("words"):
                words = [w for w in caption["words"] if
                         (w["start"] < end and w["end"] > start)
                         or (w["start"] == w["end"] and start <= w["start"] < end)]
                if not words:
                    continue
                item["text"] = "".join(w["text"] for w in words).strip()
                item["words"] = [{**w,
                                  "id": f"{w['id']}:{clip['id']}", "source_word_id": w["id"],
                                  "source_start": w["start"], "source_end": w["end"],
                                  "partial_word": w["start"] < start - 1e-6 or w["end"] > end + 1e-6,
                                  "start": clip["offset"] + (max(start, w["start"]) - clip["start"]) / clip["speed"],
                                  "end": clip["offset"] + (min(end, w["end"]) - clip["start"]) / clip["speed"]}
                                 for w in words]
            mapped.append(item)
    return sorted(mapped, key=lambda item: (item["start"], item["end"], item["id"]))


def _merge_ranges(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(ranges):
        if end - start <= 1e-7:
            continue
        if merged and start <= merged[-1][1] + 1e-7:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _remaining(start: float, end: float, cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    keep = []
    cursor = start
    for left, right in cuts:
        if right <= cursor or left >= end:
            continue
        if left > cursor:
            keep.append((cursor, min(left, end)))
        cursor = max(cursor, right)
        if cursor >= end:
            break
    if cursor < end - 1e-7:
        keep.append((cursor, end))
    return keep


def _ripple_time(time: float, cuts: list[tuple[float, float]]) -> float:
    return max(0.0, time - sum(max(0, min(time, end) - start) for start, end in cuts if start < time))


def _cut_timeline(project: dict, cuts: list[tuple[float, float]]) -> None:
    cuts = _merge_ranges(cuts)
    result = []
    for clip in project["clips"]:
        left, right = clip["offset"], clip["offset"] + clip_duration(clip)
        for index, (start, end) in enumerate(_remaining(left, right, cuts)):
            part = copy.deepcopy(clip)
            part.update(id=clip["id"] if index == 0 else _id(),
                        start=clip["start"] + (start - left) * clip["speed"],
                        end=clip["start"] + (end - left) * clip["speed"],
                        offset=_ripple_time(start, cuts))
            part["fade_in"] = min(part["fade_in"] if start == left else 0, clip_duration(part))
            part["fade_out"] = min(part["fade_out"] if end == right else 0, clip_duration(part))
            result.append(part)
    project["clips"] = result
    titles = []
    for title in project["titles"]:
        for index, (start, end) in enumerate(_remaining(title["start"], title["end"], cuts)):
            titles.append({**title, "id": title["id"] if index == 0 else _id(),
                           "start": _ripple_time(start, cuts), "end": _ripple_time(end, cuts)})
    project["titles"] = titles


def _candidate_windows(project: dict, candidates: list[dict]) -> list[tuple[float, float]]:
    windows = []
    for clip in project["clips"]:
        if clip["track"] != "video":
            continue
        for candidate in candidates:
            if candidate["media_id"] != clip["media_id"]:
                continue
            start = max(candidate["start"], clip["start"])
            end = min(candidate["end"], clip["end"])
            if end > start:
                windows.append((clip["offset"] + (start - clip["start"]) / clip["speed"],
                                clip["offset"] + (end - clip["start"]) / clip["speed"]))
    return _merge_ranges(windows)


class ProjectStore:
    """SQLite snapshot store. Every edit is atomic and guards the exact version."""
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "projects.sqlite3"
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, snapshot TEXT NOT NULL,
                    undo_stack TEXT NOT NULL DEFAULT '[]', redo_stack TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    snapshot TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                CREATE INDEX IF NOT EXISTS plans_project_idx ON plans(project_id);
                CREATE TABLE IF NOT EXISTS edit_proposals (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, snapshot TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                CREATE INDEX IF NOT EXISTS edits_project_idx ON edit_proposals(project_id);
            """)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _load(connection: sqlite3.Connection, project_id: str) -> tuple[dict, list, list]:
        _text(project_id, "專案 ID", 128)
        row = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise EditorError("找不到指定的專案。", "not_found", 404)
        return _normalize_alignment(json.loads(row["snapshot"])), json.loads(row["undo_stack"]), json.loads(row["redo_stack"])

    @staticmethod
    def _response(project: dict, undo: list, redo: list) -> dict:
        return {**_normalize_alignment(project), "history": {"undo_count": len(undo), "redo_count": len(redo)}}

    @staticmethod
    def _guard(project: dict, expected_version: Any) -> None:
        _number(expected_version, "expected_version", 1, 2**53 - 1, True)
        if expected_version != project["version"]:
            raise EditorError(f"專案已變更（目前版本 {project['version']}）；請重新讀取後再操作。",
                              "version_conflict", 409)

    def list_projects(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT snapshot FROM projects").fetchall()
        summaries = []
        for row in rows:
            project = json.loads(row["snapshot"])
            summaries.append({key: project[key] for key in ("id", "name", "version", "created_at", "updated_at", "width", "height", "fps")})
            summaries[-1].update(duration=project_duration(project), media_count=len(project["media"]), clip_count=len(project["clips"]))
        return sorted(summaries, key=lambda p: p["updated_at"], reverse=True)

    def create_project(self, name: str = "未命名專案", width: int = 1920, height: int = 1080, fps: float = 30) -> dict:
        _text(name, "專案名稱", 200)
        project = {"id": _id(), "name": name.strip(), "version": 1, "created_at": _now(), "updated_at": _now(),
                   "width": width, "height": height, "fps": fps, "media": [], "clips": [],
                   "captions": [], "titles": [], "caption_style": dict(CAPTION_STYLE)}
        validate_project(project)
        with self._connect() as connection:
            connection.execute("INSERT INTO projects(id,snapshot) VALUES (?,?)", (project["id"], _json(project)))
        return self._response(project, [], [])

    def get_project(self, project_id: str) -> dict:
        with self._connect() as connection:
            project, undo, redo = self._load(connection, project_id)
        return self._response(project, undo, redo)

    def mutate(self, project_id: str, expected_version: int, action: str, params: dict | None = None) -> dict:
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise EditorError("操作參數必須是物件。")
        _json(params)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project, undo, redo = self._load(connection, project_id)
            self._guard(project, expected_version)
            before = copy.deepcopy(project)
            if action == "undo":
                if not undo:
                    raise EditorError("沒有可以復原的操作。", "nothing_to_undo", 409)
                project = undo.pop()
                redo.append(before)
            elif action == "redo":
                if not redo:
                    raise EditorError("沒有可以重做的操作。", "nothing_to_redo", 409)
                project = redo.pop()
                undo.append(before)
            else:
                self._apply(connection, project, action, params)
                undo.append(before)
                undo = undo[-100:]
                redo = []
            project["version"] = before["version"] + 1
            project["updated_at"] = _now()
            _normalize_alignment(project)
            validate_project(project)
            connection.execute("UPDATE projects SET snapshot=?,undo_stack=?,redo_stack=? WHERE id=?",
                               (_json(project), _json(undo), _json(redo), project_id))
        return self._response(project, undo, redo)

    def _apply(self, connection: sqlite3.Connection, project: dict, action: str, params: dict) -> None:
        if action == "brief_update":
            brief = copy.deepcopy(params.get("brief", params))
            _validate_brief(brief)
            project.setdefault("brief", {}).update(brief)
        elif action == "rename":
            project["name"] = _text(params.get("name"), "專案名稱", 200).strip()
        elif action == "settings":
            settings = params.get("settings", params)
            if not isinstance(settings, dict) or set(settings) - {"width", "height", "fps"}:
                raise EditorError("畫布設定只接受 width、height、fps。")
            project.update(settings)
        elif action == "media_add":
            media = copy.deepcopy(params.get("media", params))
            if not isinstance(media, dict):
                raise EditorError("媒體參數必須是物件。")
            _text(media.get("path"), "媒體路徑", 32768)
            media.setdefault("id", _id())
            media.setdefault("name", Path(media.get("path", "素材")).name)
            media.setdefault("width", 0)
            media.setdefault("height", 0)
            media.setdefault("has_audio", media.get("kind") == "audio")
            media.setdefault("duration", 0)
            _validate_media(media)
            project["media"].append(media)
        elif action == "clip_add":
            values = copy.deepcopy(params.get("clip", params))
            if not isinstance(values, dict) or set(values) - (CLIP_FIELDS | {"id"}):
                raise EditorError("片段含不支援的欄位。")
            media = _find(project["media"], values.get("media_id"), "媒體")
            clip = {**CLIP_DEFAULTS, "id": _id(), "end": media["duration"] or 5.0,
                    "track": "audio" if media["kind"] == "audio" else "video", **values}
            project["clips"].append(clip)
        elif action in ("clip_update", "clip_move"):
            clip = _find(project["clips"], params.get("clip_id", params.get("id")), "片段")
            values = params.get("changes", {k: v for k, v in params.items() if k not in ("clip_id", "id")})
            allowed = {"offset", "track"} if action == "clip_move" else CLIP_FIELDS
            if not isinstance(values, dict) or set(values) - allowed:
                raise EditorError("片段更新含不支援的欄位。")
            clip.update(values)
        elif action == "clip_split":
            clip = _find(project["clips"], params.get("clip_id", params.get("id")), "片段")
            at = _number(params.get("at"), "分割位置")
            if not clip["offset"] + 1e-6 < at < clip["offset"] + clip_duration(clip) - 1e-6:
                raise EditorError("分割位置必須位於片段內部（時間軸秒數）。")
            source_at = clip["start"] + (at - clip["offset"]) * clip["speed"]
            second = {**clip, "id": _id(), "start": source_at, "offset": at, "fade_in": 0}
            clip["end"] = source_at
            clip["fade_out"] = 0
            clip["fade_in"] = min(clip["fade_in"], clip_duration(clip))
            second["fade_out"] = min(second["fade_out"], clip_duration(second))
            project["clips"].insert(project["clips"].index(clip) + 1, second)
        elif action == "clip_trim_at":
            from .contracts import validate_action
            validate_action(action, params)
            clip = _find(project["clips"], params["clip_id"], "片段")
            at = params["at"]
            start, end = clip["offset"], clip["offset"] + clip_duration(clip)
            if not start + 1e-6 < at < end - 1e-6:
                raise EditorError("請把播放頭移到片段內部再修剪。")
            if params.get("ripple", True):
                window = (start, at) if params["side"] == "before" else (at, end)
                _cut_timeline(project, [window])
            else:
                source_at = clip["start"] + (at-start)*clip["speed"]
                if params["side"] == "before":
                    clip.update(start=source_at, offset=at, fade_in=0)
                else:
                    clip.update(end=source_at, fade_out=0)
                clip["fade_in"] = min(clip["fade_in"], clip_duration(clip))
                clip["fade_out"] = min(clip["fade_out"], clip_duration(clip))
        elif action == "caption_cut":
            from .contracts import validate_action
            from .transcript_edit import cut_caption
            validate_action(action, params)
            cut_caption(project, params)
        elif action == "clip_paste":
            from .contracts import validate_action
            from .transcript_edit import insert_space
            validate_action(action, params)
            # Validate all copies before changing the current timeline.
            scratch = copy.deepcopy(project)
            copies = []
            for value in params['clips']:
                self._apply(connection, scratch, 'clip_add', value)
                copies.append(copy.deepcopy(scratch['clips'][-1]))
            origin = min(c['offset'] for c in copies)
            length = max(c['offset']+clip_duration(c) for c in copies)-origin
            insert_space(project, params['at'], length)
            for clip in copies:
                clip['offset'] = params['at'] + clip['offset']-origin
            project['clips'].extend(copies)
        elif action in {"clip_move_many", "clip_delete_many"}:
            from .contracts import validate_action
            validate_action(action, params)
            clips = [_find(project["clips"], identifier, "片段") for identifier in params["clip_ids"]]
            if action == "clip_move_many":
                delta = params["delta"]
                if any(c["offset"] + delta < -1e-7 for c in clips):
                    raise EditorError("整組片段不能移到時間軸起點之前。")
                for clip in clips:
                    clip["offset"] = max(0., clip["offset"] + delta)
            elif params.get("ripple", False):
                _cut_timeline(project, [(c["offset"], c["offset"] + clip_duration(c)) for c in clips])
            else:
                ids = set(params["clip_ids"])
                project["clips"] = [c for c in project["clips"] if c["id"] not in ids]
        elif action == "clip_delete":
            clip = _find(project["clips"], params.get("clip_id", params.get("id")), "片段")
            ripple = params.get("ripple", False)
            if not isinstance(ripple, bool):
                raise EditorError("ripple 必須是布林值。")
            if ripple:
                _cut_timeline(project, [(clip["offset"], clip["offset"] + clip_duration(clip))])
            else:
                project["clips"].remove(clip)
        elif action == "captions_set":
            captions = copy.deepcopy(params.get("captions"))
            if not isinstance(captions, list):
                raise EditorError("captions 必須是字幕陣列。")
            media_id = params.get("media_id")
            if media_id is not None:
                _find(project["media"], media_id, "媒體")
            for caption in captions:
                if not isinstance(caption, dict):
                    raise EditorError("每筆字幕必須是物件。")
                caption.setdefault("id", _id())
                if media_id is not None:
                    if caption.get("media_id", media_id) != media_id:
                        raise EditorError("字幕 media_id 與指定素材不符。")
                    caption["media_id"] = media_id
                _discard_stale_words(caption)
            project["captions"] = ([c for c in project["captions"] if c["media_id"] != media_id]
                                    if media_id is not None else []) + captions
        elif action in ("caption_update", "title_update"):
            is_caption = action == "caption_update"
            key = "caption_id" if is_caption else "title_id"
            item = _find(project["captions" if is_caption else "titles"], params.get(key, params.get("id")), "字幕" if is_caption else "文字")
            values = params.get("changes", {k: v for k, v in params.items() if k not in (key, "id")})
            allowed = {"start", "end", "text", "media_id", "words"} if is_caption else {"text", "start", "end", "x", "y", "font_size", "color"}
            if not isinstance(values, dict) or set(values) - allowed:
                raise EditorError("更新包含不支援的欄位。")
            if is_caption and any(key in values and values[key] != item.get(key)
                                  for key in ("text", "start", "end", "media_id")):
                item.pop("words", None)
                item["alignment_status"] = "stale"
            item.update(copy.deepcopy(values))
            if is_caption:
                _discard_stale_words(item)
        elif action in ("caption_delete", "title_delete"):
            is_caption = action == "caption_delete"
            key, collection = ("caption_id", "captions") if is_caption else ("title_id", "titles")
            item = _find(project[collection], params.get(key, params.get("id")), "字幕" if is_caption else "文字")
            project[collection].remove(item)
        elif action in ("titles_set", "title_add"):
            values = copy.deepcopy(params.get("titles")) if action == "titles_set" else [copy.deepcopy(params.get("title", params))]
            if not isinstance(values, list) or any(not isinstance(t, dict) for t in values):
                raise EditorError("文字必須是物件陣列。")
            titles = [{"id": _id(), "x": 0, "y": 0, "font_size": 48, "color": "#ffffff", **t} for t in values]
            project["titles"] = titles if action == "titles_set" else project["titles"] + titles
        elif action == "caption_style":
            values = params.get("style", params)
            if not isinstance(values, dict) or set(values) - set(CAPTION_STYLE):
                raise EditorError("字幕樣式包含不支援的欄位。")
            project["caption_style"].update(values)
        elif action == "smart_cut_apply":
            plan = self._load_plan(connection, project["id"], params.get("plan_id"))
            self._guard(project, plan["base_version"])
            ids = params.get("candidate_ids")
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
                raise EditorError("請明確指定不重複的候選 ID 陣列。")
            candidates = [_find(plan["candidates"], candidate_id, "剪輯候選") for candidate_id in ids]
            windows = _candidate_windows(project, candidates)
            if not windows:
                raise EditorError("選取的候選未對應任何影片片段。")
            if sum(end - start for start, end in windows) >= project_duration(project) - 1e-6:
                raise EditorError("智能剪口播不可刪除整條時間軸，請至少保留一個片段。")
            _cut_timeline(project, windows)
            if not any(clip["track"] == "video" for clip in project["clips"]):
                raise EditorError("智能剪口播需至少保留一個主影片片段。")
        else:
            raise EditorError(f"不支援的操作：{action}", "unknown_action")

    def prepare_plan(self, project_id: str, expected_version: int, candidates: list[dict],
                     metadata: dict | None = None) -> dict:
        if not isinstance(candidates, list) or len(candidates) > 10000:
            raise EditorError("剪輯候選必須是陣列，最多 10000 筆。")
        candidates = copy.deepcopy(candidates)
        if metadata is not None and not isinstance(metadata, dict):
            raise EditorError("提案 metadata 必須是物件。")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project, _, _ = self._load(connection, project_id)
            self._guard(project, expected_version)
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    raise EditorError("每筆剪輯候選必須是物件。")
                candidate.setdefault("id", _id())
                _text(candidate["id"], "候選 ID", 128)
                media = _find(project["media"], candidate.get("media_id"), "媒體")
                _number(candidate.get("start"), "候選起點")
                _number(candidate.get("end"), "候選終點", .000001)
                if candidate["end"] <= candidate["start"] or candidate["end"] > media["duration"] + 1e-6:
                    raise EditorError("候選範圍超出來源媒體，或終點未晚於起點。")
                candidate.setdefault("reason", "建議剪除")
                _text(candidate["reason"], "剪輯原因", 2000)
                if not _candidate_windows(project, [candidate]):
                    raise EditorError("剪輯候選必須對應時間軸上的影片片段。")
            if len({c["id"] for c in candidates}) != len(candidates):
                raise EditorError("剪輯候選 ID 不可重複。")
            windows = _candidate_windows(project, candidates)
            plan = {"id": _id(), "project_id": project_id, "base_version": project["version"],
                    "project_version": project["version"], "created_at": _now(),
                    "candidates": candidates, "metadata": metadata or {},
                    "removed_duration": sum(end - start for start, end in windows)}
            connection.execute("INSERT INTO plans(id,project_id,snapshot) VALUES (?,?,?)",
                               (plan["id"], project_id, _json(plan)))
        return plan

    @staticmethod
    def _load_plan(connection: sqlite3.Connection, project_id: str, plan_id: str) -> dict:
        _text(project_id, "專案 ID", 128)
        _text(plan_id, "提案 ID", 128)
        row = connection.execute("SELECT snapshot FROM plans WHERE id=? AND project_id=?", (plan_id, project_id)).fetchone()
        if row is None:
            raise EditorError("找不到指定的智能剪輯提案。", "not_found", 404)
        return json.loads(row["snapshot"])

    def get_plan(self, project_id: str, plan_id: str) -> dict:
        with self._connect() as connection:
            return self._load_plan(connection, project_id, plan_id)

    def apply_plan(self, project_id: str, expected_version: int, plan_id: str, candidate_ids: list[str]) -> dict:
        return self.mutate(project_id, expected_version, "smart_cut_apply",
                           {"plan_id": plan_id, "candidate_ids": candidate_ids})

    def prepare_edit(self, project_id: str, expected_version: int, operations: list[dict],
                     intent: str = "", checks: list[dict] | None = None) -> dict:
        """Compute a batch once; its persisted snapshot is the only apply target."""
        from .understanding import describe_edit
        from .contracts import validate_checks
        from .acceptance import evaluate_checks
        checks = [] if checks is None else copy.deepcopy(checks)
        validate_checks(checks)
        _text(intent, "修改意圖", 10000, empty=True)
        if not isinstance(operations, list) or not 1 <= len(operations) <= 100:
            raise EditorError("operations 必須包含 1 至 100 個操作。")
        operations = copy.deepcopy(operations)
        for operation in operations:
            if not isinstance(operation, dict) or set(operation) - {"action", "params"}:
                raise EditorError("每個操作只接受 action 與 params。")
            if not isinstance(operation.get("action"), str) or operation["action"] not in EDIT_ACTIONS:
                raise EditorError("提案不支援此操作；素材匯入與復原重做請使用各自工具。")
            if not isinstance(operation.get("params", {}), dict):
                raise EditorError("操作 params 必須是物件。")
        _json(operations)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            before, _, _ = self._load(connection, project_id)
            self._guard(before, expected_version)
            after = copy.deepcopy(before)
            for operation in operations:
                self._apply(connection, after, operation["action"], operation.get("params", {}))
                _normalize_alignment(after)
                validate_project(after)
            after["version"] = before["version"] + 1
            after["updated_at"] = _now()
            edit_id = _id()
            proposal = {"id": edit_id, "edit_id": edit_id, "project_id": project_id,
                        "base_version": before["version"], "status": "prepared",
                        "created_at": _now(), "intent": intent, "operations": operations,
                        **describe_edit(before, after),
                        "checks": checks, "acceptance": evaluate_checks(after, checks),
                        "_before_snapshot": before, "_after_snapshot": after}
            connection.execute("INSERT INTO edit_proposals(id,project_id,snapshot) VALUES (?,?,?)",
                               (edit_id, project_id, _json(proposal)))
        return self._edit_response(proposal)

    @staticmethod
    def _edit_response(proposal: dict) -> dict:
        return copy.deepcopy({key: value for key, value in proposal.items() if not key.startswith("_")})

    @staticmethod
    def _load_edit(connection: sqlite3.Connection, project_id: str, edit_id: str) -> dict:
        _text(project_id, "專案 ID", 128)
        _text(edit_id, "修改提案 ID", 128)
        row = connection.execute("SELECT snapshot FROM edit_proposals WHERE id=? AND project_id=?",
                                 (edit_id, project_id)).fetchone()
        if row is None:
            raise EditorError("找不到指定的修改提案。", "not_found", 404)
        return json.loads(row["snapshot"])

    def get_edit(self, project_id: str, edit_id: str) -> dict:
        with self._connect() as connection:
            proposal = self._load_edit(connection, project_id, edit_id)
            project, _, _ = self._load(connection, project_id)
        result = self._edit_response(proposal)
        result["current_version"] = project["version"]
        result["can_apply"] = proposal["status"] == "prepared" and project["version"] == proposal["base_version"]
        return result

    def list_edits(self, project_id: str, limit: int = 8) -> list[dict]:
        _number(limit, "limit", 1, 100, True)
        with self._connect() as connection:
            project, _, _ = self._load(connection, project_id)
            rows = connection.execute("SELECT snapshot FROM edit_proposals WHERE project_id=? ORDER BY rowid DESC LIMIT ?",
                                      (project_id, limit)).fetchall()
        fields = ("id", "edit_id", "project_id", "base_version", "status", "created_at", "intent",
                  "before", "after", "affected_ids", "warnings", "applied_version", "undo_ref")
        result = []
        for row in rows:
            proposal = json.loads(row["snapshot"])
            result.append({**{key: proposal[key] for key in fields if key in proposal},
                           "can_apply": proposal["status"] == "prepared" and proposal["base_version"] == project["version"]})
        return result

    def preview_edit(self, project_id: str, edit_id: str, side: str = "after") -> dict:
        """Internal render input. Both sides stay reproducible after later edits."""
        if side not in ("before", "after"):
            raise EditorError("預覽 side 必須是 before 或 after。")
        with self._connect() as connection:
            proposal = self._load_edit(connection, project_id, edit_id)
        return _normalize_alignment(proposal[f"_{side}_snapshot"])

    def apply_edit(self, project_id: str, expected_version: int, edit_id: str) -> dict:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project, undo, _ = self._load(connection, project_id)
            self._guard(project, expected_version)
            proposal = self._load_edit(connection, project_id, edit_id)
            if proposal["status"] != "prepared":
                raise EditorError("此修改提案已套用，不能重複套用。", "edit_already_applied", 409)
            self._guard(project, proposal["base_version"])
            before = copy.deepcopy(project)
            project = _normalize_alignment(copy.deepcopy(proposal["_after_snapshot"]))
            project["version"] = before["version"] + 1
            project["updated_at"] = _now()
            validate_project(project)
            undo = (undo + [before])[-100:]
            proposal.update(status="applied", applied_at=project["updated_at"],
                            applied_version=project["version"],
                            undo_ref=f"{project_id}:{project['version']}")
            connection.execute("UPDATE projects SET snapshot=?,undo_stack=?,redo_stack='[]' WHERE id=?",
                               (_json(project), _json(undo), project_id))
            connection.execute("UPDATE edit_proposals SET snapshot=? WHERE id=?",
                               (_json(proposal), edit_id))
        return self._response(project, undo, [])
