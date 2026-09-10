"""Shared application operations for the UI and the stdio MCP bridge.

Only this service imports local files. Browser/agent edit commands cannot forge
media records or use the file-serving endpoints as a general filesystem reader.
"""

from __future__ import annotations

import copy
import json
import math
import re
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .core import ProjectStore, project_duration
from .observation_service import ObservationServiceMixin


class ServiceError(ValueError):
    def __init__(self, message: str, code: str = "invalid_request", status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mts", ".m2ts",
                    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
                    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
EDIT_ACTIONS = ["rename", "settings", "clip_add", "clip_update", "clip_move", "clip_split", "clip_move_many", "clip_delete_many",
                "clip_delete", "captions_set", "caption_update", "caption_delete", "caption_style",
                "title_add", "title_update", "title_delete", "titles_set", "brief_update", "caption_cut", "clip_paste", "clip_trim_at", "undo", "redo"]


def error_payload(exc: Exception) -> dict[str, Any]:
    return {"code": getattr(exc, "code", "invalid_request"), "message": str(exc)}


def _required(data: dict, name: str, kind: type = str):
    value = data.get(name)
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ServiceError(f"{name} 格式不正確")
    if kind is str and not value.strip():
        raise ServiceError(f"{name} 不可空白")
    return value


class EditorService(ObservationServiceMixin):
    def __init__(self, data_dir: str | Path, *, workers: int = 2, max_jobs: int = 8):
        self.root = Path(data_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.assets = self.root / "assets"
        self.uploads = self.root / "uploads"
        self.exports = self.root / "exports"
        self.work = self.root / "work"
        self.job_dir = self.root / "jobs"
        for folder in (self.assets, self.uploads, self.exports, self.work, self.job_dir):
            folder.mkdir(exist_ok=True)
        self.store = ProjectStore(self.root / "projects")
        self._lock = threading.RLock()
        self._job_changed = threading.Condition(self._lock)
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="editor-job")
        self._slots = threading.BoundedSemaphore(max_jobs)
        self._jobs: dict[str, dict] = {}
        self._events: deque = deque(maxlen=80)
        self._load_jobs()
        self._init_observation()

    def close(self):
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _load_jobs(self):
        for path in sorted(self.job_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)[-200:]:
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(job, dict) or not SAFE_ID.fullmatch(str(job.get("id", ""))):
                    continue
                if job.get("status") in {"queued", "running"}:
                    job.update(status="failed", error={"code": "interrupted", "message": "上次服務中止，請重新執行工作。"})
                self._jobs[job["id"]] = job
            except (OSError, ValueError):
                continue

    def _save_job(self, job: dict):
        path = self.job_dir / f"{job['id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        tmp.replace(path)

    def record_event(self, action: str, project_id: str | None = None, actor: str = "ui"):
        with self._lock:
            self._events.appendleft({"id": uuid.uuid4().hex, "time": time.time(), "actor": actor,
                                     "action": action, "project_id": project_id})

    def events(self):
        with self._lock:
            return {"events": list(self._events)}

    def doctor(self):
        from . import media_engine as media
        return {"app": "本地剪輯工作台", "version": __version__, "data_dir": str(self.root),
                "mcp": {"transport": "stdio", "protocol_version": "2025-11-25"}, **media.doctor()}

    def _project(self, project_id: str, expected_version: int | None = None):
        project = self.store.get_project(project_id)
        if expected_version is not None and project["version"] != expected_version:
            raise ServiceError(f"專案版本已變更：預期 {expected_version}，目前 {project['version']}，請重新讀取。",
                               "version_conflict", 409)
        return project

    def _decorate(self, project: dict):
        result = copy.deepcopy(project)
        result["duration"] = project_duration(project)
        result["can_undo"] = project.get("history", {}).get("undo_count", 0) > 0
        result["can_redo"] = project.get("history", {}).get("redo_count", 0) > 0
        for media in result.get("media", []):
            base = f"/api/projects/{result['id']}/media/{media['id']}"
            media["url"] = base + "/file"
            if isinstance(media.get("thumbnail"), str):
                media["thumbnail_url"] = base + "/thumbnail"
            if isinstance(media.get("waveform"), str):
                media["waveform_url"] = base + "/waveform"
        return result

    def list_projects(self):
        return {"projects": self.store.list_projects()}

    def create_project(self, data: dict):
        name = _required(data, "name")
        kwargs = {k: data[k] for k in ("width", "height", "fps") if k in data}
        return self._decorate(self.store.create_project(name, **kwargs))

    def get_project(self, project_id: str):
        return self._decorate(self._project(project_id))

    def edit(self, project_id: str, data: dict):
        from .contracts import validate_action
        action = _required(data, "action")
        # Internal record insertion is exclusively available through import_media.
        if action in {"add_media", "import_media", "set_media", "replace_media", "media_add"}:
            raise ServiceError("請使用媒體匯入工具加入素材。", "protected_action", 403)
        if action not in EDIT_ACTIONS:
            raise ServiceError("不支援此編輯操作，智能剪輯請使用提案與套用入口。", "unknown_action")
        params = data.get("params", {})
        if not isinstance(params, dict):
            raise ServiceError("params 必須為物件")
        validate_action(action, params)
        expected = _required(data, "expected_version", int)
        before = self._project(project_id, expected)
        project = self.store.mutate(project_id, expected, action, params)
        result = self._decorate(project)
        from .understanding import describe_edit
        effects = describe_edit(before, project)
        result["affected_ids"] = effects["affected_ids"]
        result["warnings"] = effects["warnings"]
        if action == "caption_update":
            caption_id = params.get("caption_id", params.get("id"))
            caption = next(c for c in project["captions"] if c["id"] == caption_id)
            result["side_effects"] = {"caption_id": caption_id,
                "alignment_status": caption.get("alignment_status", "valid" if caption.get("words") else "missing"),
                "requires_alignment_review": not bool(caption.get("words"))}
            if not caption.get("words"):
                result["warnings"].append("此字幕沒有有效逐字時間；局部刪文剪片前請先用 editor_review_caption 複核。")
        return result

    def validate_import(self, project_id: str, expected_version: int, name: str):
        self._project(project_id, expected_version)
        if Path(name).suffix.lower() not in MEDIA_EXTENSIONS:
            raise ServiceError("不支援此素材副檔名；請匯入影片、音訊或圖片。", "unsupported_media", 415)

    def import_media(self, project_id: str, data: dict):
        from . import media_engine as media
        expected = _required(data, "expected_version", int)
        path = Path(_required(data, "path")).expanduser().resolve()
        self.validate_import(project_id, expected, path.name)
        if not path.is_file():
            raise ServiceError("找不到素材檔案", "file_not_found", 404)
        item = media.import_media(path, self.assets)
        try:
            result = self.store.mutate(project_id, expected, "media_add", {"media": item})
        except Exception:
            # Reclaim only this import's generated copies if a concurrent edit
            # invalidated its version. The user's original is never removed.
            item_id = str(item.get("id", ""))
            if SAFE_ID.fullmatch(item_id):
                for field in ("path", "thumbnail"):
                    if not isinstance(item.get(field), str):
                        continue
                    copied = Path(item[field]).resolve()
                    if (copied != path and copied.is_relative_to(self.assets)
                            and copied.name.startswith(item_id + ".")):
                        try:
                            copied.unlink(missing_ok=True)
                        except OSError:
                            pass
            raise
        return self._decorate(result)

    def _media(self, project: dict, media_id: str):
        for item in project.get("media", []):
            if item["id"] == media_id:
                return item
        raise ServiceError("找不到素材", "media_not_found", 404)

    def import_captions(self, project_id: str, data: dict):
        from .captions import parse_captions
        expected = _required(data, "expected_version", int)
        project = self._project(project_id, expected)
        media_id = _required(data, "media_id")
        self._media(project, media_id)
        captions = parse_captions(_required(data, "text"), data.get("format", "srt"))
        for caption in captions:
            caption["media_id"] = media_id
        return self._decorate(self.store.mutate(project_id, expected, "captions_set",
                                               {"media_id": media_id, "captions": captions}))

    def export_captions(self, project_id: str, format: str = "srt"):
        from .captions import export_captions
        return {"format": format, "text": export_captions(self._project(project_id), format)}

    def get_plan(self, project_id: str, plan_id: str):
        return self.store.get_plan(project_id, plan_id)

    def prepare_plan(self, project_id: str, data: dict):
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ServiceError("metadata 必須為物件")
        return self.store.prepare_plan(project_id, _required(data, "expected_version", int),
                                       _required(data, "candidates", list), metadata)

    def apply_smart_cut(self, project_id: str, data: dict):
        selected = _required(data, "candidate_ids", list)
        if not all(isinstance(item, str) for item in selected):
            raise ServiceError("candidate_ids 必須是字串陣列")
        project = self.store.apply_plan(project_id, _required(data, "expected_version", int),
                                        _required(data, "plan_id"), selected)
        return self._decorate(project)

    def _enqueue(self, kind: str, project_id: str, expected: int, task: Callable):
        if not self._slots.acquire(blocking=False):
            raise ServiceError("工作佇列已滿，請等待目前工作完成。", "queue_full", 429)
        job = {"id": uuid.uuid4().hex, "kind": kind, "project_id": project_id,
               "project_version": expected, "status": "queued", "progress": 0,
               "created_at": time.time(), "updated_at": time.time()}
        with self._lock:
            self._jobs[job["id"]] = job
            try:
                self._save_job(job)
            except Exception:
                self._slots.release()
                self._jobs.pop(job["id"], None)
                raise

        def update(value=0, message=None, **kwargs):
            if isinstance(value, dict):
                message = value.get("message", message)
                value = value.get("progress", 0) * 100
            try:
                progress = float(value)
                if not math.isfinite(progress):
                    return
            except (TypeError, ValueError):
                return
            with self._lock:
                job.update(progress=min(99, max(0, progress)), updated_at=time.time())
                if message:
                    job["message"] = str(message)

        def run():
            try:
                try:
                    with self._lock:
                        job.update(status="running", updated_at=time.time())
                        self._save_job(job)
                    result = task(job["id"], update)
                    with self._lock:
                        job.update(status="succeeded", result=result, progress=100, updated_at=time.time())
                except Exception as exc:
                    with self._lock:
                        job.update(status="failed", error=error_payload(exc), updated_at=time.time())
                try:
                    with self._lock:
                        self._save_job(job)
                except Exception as exc:
                    with self._lock:
                        job.pop("result", None)
                        job.update(status="failed", error={"code": "job_persistence_failed",
                                   "message": f"無法保存工作結果：{exc}"}, updated_at=time.time())
            finally:
                self._slots.release()
                with self._job_changed:
                    self._job_changed.notify_all()

        try:
            self._executor.submit(run)
        except Exception as exc:
            try:
                with self._lock:
                    job.update(status="failed", error=error_payload(exc), updated_at=time.time())
                    self._save_job(job)
            finally:
                self._slots.release()
            raise
        return self.job_status(job["id"])

    def job_status(self, job_id: str, wait_ms: int = 0):
        if isinstance(wait_ms, bool) or not isinstance(wait_ms, int) or not 0 <= wait_ms <= 20000:
            raise ServiceError("wait_ms 需介於 0 與 20000。")
        with self._job_changed:
            if job_id not in self._jobs:
                raise ServiceError("找不到工作", "job_not_found", 404)
            if wait_ms and self._jobs[job_id]["status"] in {"queued", "running"}:
                self._job_changed.wait_for(lambda: self._jobs[job_id]["status"] not in {"queued", "running"}, wait_ms / 1000)
            return copy.deepcopy(self._jobs[job_id])

    def list_jobs(self, project_id: str | None = None):
        with self._lock:
            jobs = [copy.deepcopy(j) for j in self._jobs.values()
                    if project_id is None or j["project_id"] == project_id]
            return {"jobs": sorted(jobs, key=lambda j: j["created_at"], reverse=True)[:50]}

    def prepare_smart_cut(self, project_id: str, data: dict):
        from . import media_engine as media
        expected = _required(data, "expected_version", int)
        project = self._project(project_id, expected)
        item = self._media(project, _required(data, "media_id"))
        clips = [clip for clip in project["clips"]
                 if clip["media_id"] == item["id"] and clip["track"] == "video"]
        if not clips:
            raise ServiceError("請先將口播素材加入主影片軌，再執行智能剪口播。")
        options = data.get("options", {})
        if not isinstance(options, dict):
            raise ServiceError("options 必須為物件")
        source_captions = [c for c in project.get("captions", []) if c.get("media_id") == item["id"]]

        def task(job_id, progress):
            progress(10, "分析口播停頓與逐字稿")
            analysis = media.analyze_speech(item, options, source_captions)
            candidates = [candidate for candidate in analysis.get("candidates", [])
                          if any(candidate["start"] < clip["end"] and candidate["end"] > clip["start"]
                                 for clip in clips)]
            for candidate in candidates:
                candidate.setdefault("media_id", item["id"])
            progress(90, "建立可審閱剪輯提案")
            plan = self.store.prepare_plan(project_id, expected, candidates,
                                           {"media_id": item["id"], "options": options,
                                            **{k: v for k, v in analysis.items() if k != "candidates"}})
            return {"plan": plan}
        return self._enqueue("smart_cut", project_id, expected, task)

    def transcribe(self, project_id: str, data: dict):
        from . import media_engine as media
        expected = _required(data, "expected_version", int)
        project = self._project(project_id, expected)
        item = self._media(project, _required(data, "media_id"))
        options = data.get("options", {})
        if not isinstance(options, dict):
            raise ServiceError("options 必須為物件")

        def task(job_id, progress):
            progress(5, "執行本地語音辨識")
            folder = self.work / job_id
            folder.mkdir(exist_ok=True)
            result = media.transcription(item, options, folder)
            captions = result.get("captions", []) if isinstance(result, dict) else result
            for caption in captions:
                caption["media_id"] = item["id"]
            project = self.store.mutate(project_id, expected, "captions_set",
                                        {"media_id": item["id"], "captions": captions})
            return {"project": self._decorate(project), "caption_count": len(captions)}
        return self._enqueue("transcribe", project_id, expected, task)

    def export(self, project_id: str, data: dict):
        from . import media_engine as media
        expected = _required(data, "expected_version", int)
        project = self._project(project_id, expected)
        options = data.get("options", {})
        if not isinstance(options, dict):
            raise ServiceError("options 必須為物件")

        def task(job_id, progress):
            folder = self.exports / job_id
            folder.mkdir(exist_ok=True)
            result = media.render_project(project, folder, options, progress_callback=progress)
            if not isinstance(result, dict):
                result = {"path": str(result)}
            path = Path(result.get("path", "")).resolve()
            if not path.is_relative_to(folder.resolve()) or not path.is_file():
                raise ServiceError("輸出未產生有效檔案", "export_missing", 500)
            return {**result, "path": str(path), "url": f"/api/exports/{job_id}/{path.name}",
                    "project_version": expected,
                    "current_version": self._project(project_id)["version"]}
        return self._enqueue("export", project_id, expected, task)

    def media_file(self, project_id: str, media_id: str, kind: str):
        item = self._media(self._project(project_id), media_id)
        field = {"file": "path", "thumbnail": "thumbnail", "waveform": "waveform"}.get(kind)
        value = item.get(field) if field else None
        if not isinstance(value, str):
            raise ServiceError("找不到素材檔案", "file_not_found", 404)
        path = Path(value).resolve()
        if not path.is_relative_to(self.assets) or not path.is_file():
            raise ServiceError("素材不在受管理目錄中", "file_not_found", 404)
        return path

    def waveform_peaks(self, project_id: str, media_id: str, chunk: int):
        from .waveforms import source_peaks

        item = self._media(self._project(project_id), media_id)
        path = self.media_file(project_id, media_id, "file")
        if not item.get("has_audio"):
            return {"start": 0, "end": 0, "bucket_seconds": .01, "peaks": []}
        return source_peaks(path, self.work / "waveforms", chunk, float(item["duration"]))

    def export_file(self, job_id: str, filename: str):
        job = self.job_status(job_id)
        result = job.get("result", {})
        path = Path(result.get("path", "")).resolve()
        if (job.get("kind") != "export" or job.get("status") != "succeeded"
                or filename != path.name or not path.is_relative_to(self.exports / job_id)
                or not path.is_file()):
            raise ServiceError("找不到輸出檔案", "file_not_found", 404)
        return path
