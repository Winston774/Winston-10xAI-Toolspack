"""Shared context, evidence and review workflow for HTTP, UI and MCP callers."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import time
import uuid
from pathlib import Path

from .core import EditorError, project_duration


def _number(value, name, low=0, high=86400):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise EditorError(f"{name} 數值超出範圍。")
    return value


def _identifier(value):
    from .service import SAFE_ID
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise EditorError("識別碼格式錯誤。")
    return value


def _public(value):
    if isinstance(value, list):
        return [_public(v) for v in value]
    if isinstance(value, dict):
        return {k: _public(v) for k, v in value.items()
                if k not in {"path", "model_path", "thumbnail", "cache_key"} and not k.startswith("_")}
    return value


class ObservationServiceMixin:
    """A narrow interface keeps media plumbing out of every Agent workflow."""

    def _init_observation(self):
        self.evidence_root = self.root / "evidence"
        self.evidence_root.mkdir(exist_ok=True)
        self._contexts = {}
        self._agents = {}
        self._evidence_cache = {}
        self._reviews = []
        self._review_path = self.root / "reviews.json"
        try:
            records = json.loads(self._review_path.read_text(encoding="utf-8"))
            if isinstance(records, list):
                self._reviews = records[-2000:]
        except (OSError, ValueError):
            pass
        # Session context deliberately expires on restart. A stored project is
        # not evidence that a browser is still focused on it.
        for path in self.evidence_root.glob("*/manifest.json"):
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                if manifest.get("cache_key"):
                    self._evidence_cache[manifest["cache_key"]] = manifest["evidence_id"]
            except (OSError, ValueError, KeyError):
                continue

    def update_context(self, data):
        client_id = _identifier(data.get("client_id"))
        sequence = data.get("sequence", 0)
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise EditorError("sequence 必須為非負整數。")
        project_id = data.get("project_id")
        project = self._project(_identifier(project_id)) if project_id else None
        playhead = _number(data.get("playhead", 0), "播放頭")
        selection = data.get("selected")
        if selection is not None:
            if not isinstance(selection, dict) or selection.get("type") not in {"clip", "caption", "title"}:
                raise EditorError("選取項目格式錯誤。")
            collection = {"clip": "clips", "caption": "captions", "title": "titles"}[selection["type"]]
            if not project or not any(i["id"] == selection.get("id") for i in project[collection]):
                selection = None
        selected_range = data.get("range")
        if selected_range is not None:
            if not isinstance(selected_range, dict):
                raise EditorError("range 必須為物件。")
            start = _number(selected_range.get("start"), "區間起點")
            end = _number(selected_range.get("end"), "區間終點")
            if not project or end <= start or end > project_duration(project) + 1e-6:
                raise EditorError("選取區間必須位於時間軸內。")
            selected_range = {"start": start, "end": end}
        observed_version = data.get("project_version")
        media_id = data.get("media_id")
        if media_id is not None and (not project or not any(m["id"] == media_id for m in project["media"])):
            media_id = None
        if project and (isinstance(observed_version, bool) or not isinstance(observed_version, int) or observed_version < 1):
            raise EditorError("project_version 必須為 UI 實際顯示的版本。")
        focused = data.get("focused", False)
        if not isinstance(focused, bool):
            raise EditorError("focused 必須為布林值。")
        with self._lock:
            previous = self._contexts.get(client_id)
            if previous and sequence <= previous["sequence"]:
                return {"accepted": False, "reason": "out_of_order", "sequence": previous["sequence"]}
            self._contexts[client_id] = {
                "client_id": client_id, "sequence": sequence, "project_id": project_id,
                "project_version": observed_version, "selected": copy.deepcopy(selection),
                "playhead": playhead, "range": selected_range, "mode": str(data.get("mode", ""))[:100],
                "media_id": media_id, "focused": focused, "updated_at": time.time(),
            }
            self._contexts = dict(sorted(self._contexts.items(), key=lambda item: item[1]["updated_at"])[-20:])
        return {"accepted": True, "sequence": sequence, "project_id": project_id}

    def record_agent(self, data):
        client_id = _identifier(data.get("client_id"))
        info = data.get("client_info", {})
        if not isinstance(info, dict):
            raise EditorError("client_info 必須為物件。")
        with self._lock:
            self._agents[client_id] = {"client_id": client_id, "name": str(info.get("name", "Agent"))[:120],
                "version": str(info.get("version", ""))[:80], "transport": "stdio",
                "status": "disconnected" if data.get("status") == "disconnected" else "connected",
                "last_tool": str(data.get("last_tool") or "")[:100], "last_seen": time.time()}
            self._agents = dict(sorted(self._agents.items(), key=lambda item: item[1]["last_seen"])[-40:])
        return {"registered": True, "client_id": client_id}

    def get_context(self, data=None):
        from .mcp import TOOLS
        data = data or {}
        now = time.time()
        with self._lock:
            sessions = copy.deepcopy(list(self._contexts.values()))
            agents = copy.deepcopy(list(self._agents.values()))
        for session in sessions:
            session["stale"] = now - session["updated_at"] > 60
        live = [s for s in sessions if not s["stale"]]
        if data.get("client_id"):
            live = [s for s in live if s["client_id"] == data["client_id"]]
        if data.get("project_id"):
            live = [s for s in live if s["project_id"] == data["project_id"]]
        focused = [s for s in live if s["focused"]]
        choices = focused or live
        active = max(choices, key=lambda s: s["updated_at"]) if choices else None
        project_id = data.get("project_id") or (active or {}).get("project_id")
        project = self._project(project_id) if project_id else None
        for agent in agents:
            agent["status"] = "recently_active" if agent["status"] != "disconnected" and now - agent["last_seen"] <= 60 else "inactive"
        if active:
            active["version_matches"] = bool(project and active["project_version"] == project["version"])
        result = {"schema_version": "editor.context.v2", "context_status": "available" if active else "no_live_ui",
            "selection_policy": "explicit client, otherwise most recently focused live tab; 60 second expiry",
            "ambiguous": len({s["project_id"] for s in choices if s["project_id"]}) > 1,
            "ui": active, "sessions": sessions, "agents": agents,
            "project": None, "brief": {}, "jobs": [],
            "capabilities": {"tools": [{"name": t["name"], "description": t["description"]} for t in TOOLS],
                "source_and_composite_evidence": True, "native_mcp_image_audio": True,
                "atomic_edit_proposals": True, "max_observation_seconds": 30, "max_frames": 8,
                "cut_boundary_sampling": True, "decoded_black_frame_scan": True,
                "acceptance_checks": ["no_timeline_gaps", "duration_between", "no_black_frames"],
                "caption_alignment": "ASR word estimates or supplied word times; forced alignment unavailable",
                "visual_understanding": "Agent interprets supplied frames; local motion metrics are non-semantic",
                "unavailable": ["OCR", "person_detection", "cursor_action_recognition", "semantic_retake_judgement", "automatic_audio_naturalness_verdict"]},
            "missing_analysis": [], "next_steps": []}
        if project:
            from .understanding import inspect_structure
            result["project"] = {"id": project["id"], "name": project["name"], "version": project["version"],
                "duration": project_duration(project), "width": project["width"], "height": project["height"],
                "fps": project["fps"], "clip_count": len(project["clips"]), "caption_count": len(project["captions"]),
                "media": [{k: m.get(k) for k in ("id", "name", "kind", "duration", "width", "height", "has_audio")} for m in project["media"]]}
            result["brief"] = project.get("brief", {})
            result["proposals"] = self.store.list_edits(project_id, limit=8)
            if not result["brief"].get("goal"):
                result["missing_analysis"].append({"kind": "editing_direction", "reason": "尚未記錄剪輯目標，請確認需求後以 brief_update 保存。"})
            if not project["captions"]:
                result["missing_analysis"].append({"kind": "transcript", "reason": "尚無字幕或逐字稿。"})
            result["jobs"] = [{k: j[k] for k in ("id", "kind", "status", "progress", "project_version")} for j in self.list_jobs(project_id)["jobs"][:8]]
            with self._lock:
                result["review_count_at_revision"] = sum(r["project_id"] == project_id and r["revision"] == project["version"] for r in self._reviews)
            result["missing_analysis"].append({"kind": "audiovisual_semantics", "reason": "場景意義與聽感需檢視區間聲畫；資料或證據生成不等同已審閱。"})
            if active and active.get("range") and active["version_matches"]:
                result["selection_structure"] = inspect_structure(project, {"time_space": "timeline", "range": active["range"], "detail": "summary"})
            result["next_steps"] = ["editor_inspect_range", "editor_read_evidence", "editor_analyze_range", "editor_prepare_edit", "editor_apply_edit", "editor_verify_edit"]
        else:
            result["next_steps"] = ["editor_list_projects", "editor_get_context(project_id=明確專案)"]
        return _public(result)

    def _observation_project(self, project_id, data):
        expected = data.get("expected_version")
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 1:
            raise EditorError("expected_version 必須為最近讀取的精確版本。")
        project = self._project(project_id, expected)
        if data.get("edit_id"):
            edit = self.store.get_edit(project_id, data["edit_id"])
            if edit["base_version"] != expected or edit.get("status") != "prepared":
                raise EditorError("提案已過期或已套用，請重新提案。", "version_conflict", 409)
            project = self.store.preview_edit(project_id, data["edit_id"], side=data.get("preview_side", "after"))
        return project

    def _register_evidence(self, manifest, evidence_id, folder, cache_key):
        manifest = copy.deepcopy(manifest)
        manifest.update(evidence_id=evidence_id, cache_key=cache_key, created_at=time.time())
        files = manifest.get("files", [])
        if not isinstance(files, list) or len(files) > 24:
            raise EditorError("證據檔案清單不合法。")
        ids = set()
        for item in files:
            file_id = _identifier(item.get("id"))
            path = Path(item.get("path", "")).resolve()
            if file_id in ids or not path.is_relative_to(folder.resolve()) or not path.is_file():
                raise EditorError("證據檔案必須位於該工作受管理目錄。")
            if item.get("mime_type") not in {"image/jpeg", "image/png", "audio/wav", "audio/x-wav", "video/mp4"}:
                raise EditorError("證據媒體格式不支援。")
            ids.add(file_id)
            item.update(path=str(path), size=path.stat().st_size,
                url=f"/api/evidence/{evidence_id}/files/{file_id}", uri=f"evidence://{evidence_id}/{file_id}")
        path = folder / "manifest.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        temporary.replace(path)
        with self._lock:
            self._evidence_cache[cache_key] = evidence_id
        return _public(manifest)

    def _evidence_raw(self, evidence_id):
        _identifier(evidence_id)
        path = self.evidence_root / evidence_id / "manifest.json"
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise EditorError("找不到區間證據。", "evidence_not_found", 404) from exc
        if result.get("evidence_id") != evidence_id:
            raise EditorError("證據識別不符。", "evidence_not_found", 404)
        return result

    def evidence_manifest(self, evidence_id):
        return _public(self._evidence_raw(evidence_id))

    def evidence_file(self, evidence_id, file_id):
        _identifier(file_id)
        manifest = self._evidence_raw(evidence_id)
        item = next((f for f in manifest.get("files", []) if f.get("id") == file_id), None)
        if item:
            path = Path(item.get("path", "")).resolve()
            if path.is_relative_to((self.evidence_root / evidence_id).resolve()) and path.is_file():
                return path
        raise EditorError("找不到已登錄證據檔案。", "evidence_not_found", 404)

    def _observe(self, kind, project_id, data):
        from . import evidence
        from .contracts import validate_request
        from .understanding import inspect_structure, analyze_structure
        validate_request({"inspect": "inspect", "analyze": "analyze", "caption_review": "captions/review"}[kind], data)
        project = self._observation_project(project_id, data)
        expected = data["expected_version"]
        if kind != "caption_review":
            structure = inspect_structure(project, data)
            structure.update(base_version=expected, snapshot_version=project["version"],
                snapshot_kind="proposal" if data.get("edit_id") else "saved_project",
                edit_id=data.get("edit_id"), preview_side=data.get("preview_side", "after") if data.get("edit_id") else None)
            requested = data.get("range", {})
            if requested.get("end", 0) - requested.get("start", 0) > 30 + 1e-6:
                raise EditorError("聲畫觀察每次最多 30 秒，請按區間分段取得。")
        else:
            structure = None
        key = hashlib.sha256(json.dumps({"engine": "observation-v3-cut-review-1", "kind": kind,
            "project": project, "request": data}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

        def task(job_id, progress):
            with self._lock:
                cached = self._evidence_cache.get(key)
            if cached:
                try:
                    manifest = self.evidence_manifest(cached)
                    for item in manifest["files"]:
                        self.evidence_file(cached, item["id"])
                    current_version = self._project(project_id)["version"]
                    return {"evidence": manifest, "structure": structure, "cache_hit": True,
                        "current_version": current_version, "stale": current_version != expected}
                except (EditorError, OSError):
                    pass
            evidence_id = uuid.uuid4().hex
            folder = self.evidence_root / evidence_id
            folder.mkdir()
            method = {"inspect": evidence.inspect_media, "analyze": evidence.analyze_media,
                      "caption_review": evidence.review_caption}[kind]
            manifest = method(project, data, folder, progress_callback=progress)
            manifest["project_id"] = project_id
            manifest["project_version"] = expected
            manifest["snapshot_version"] = project["version"]
            manifest["edit_id"] = data.get("edit_id")
            manifest["preview_side"] = data.get("preview_side", "after") if data.get("edit_id") else None
            manifest["snapshot_kind"] = "proposal" if data.get("edit_id") else "saved_project"
            for finding in manifest.get("findings", []):
                finding.update(project_version=expected, snapshot_version=project["version"],
                    edit_id=manifest["edit_id"], preview_side=manifest["preview_side"], evidence_id=evidence_id)
            if kind == "analyze":
                manifest["structural_analysis"] = analyze_structure(project, data)
            registered = self._register_evidence(manifest, evidence_id, folder, key)
            current_version = self._project(project_id)["version"]
            return {"evidence": registered, "structure": structure, "cache_hit": False,
                "current_version": current_version, "stale": current_version != expected}
        return self._enqueue(kind, project_id, expected, task)

    def inspect_range(self, project_id, data):
        return self._observe("inspect", project_id, data)

    def analyze_range(self, project_id, data):
        return self._observe("analyze", project_id, data)

    def review_caption(self, project_id, data):
        return self._observe("caption_review", project_id, data)

    def prepare_edit(self, project_id, data):
        from .contracts import validate_action, validate_request
        validate_request("edits", data)
        operations = data.get("operations")
        if not isinstance(operations, list) or not 1 <= len(operations) <= 100:
            raise EditorError("operations 需包含 1 至 100 項操作。")
        for op in operations:
            if not isinstance(op, dict):
                raise EditorError("每項操作必須為物件。")
            validate_action(op.get("action"), op.get("params", {}), batch=True)
        result = self.store.prepare_edit(project_id, data.get("expected_version"), operations, data.get("intent", ""), data.get("checks"))
        result["preview_instruction"] = {"tool": "editor_inspect_range", "project_id": project_id,
            "expected_version": data["expected_version"], "edit_id": result["edit_id"],
            "time_space": "timeline", "preview_side": "before or after", "range": data.get("preview_range"),
            "note": "指定各側有效時間軸區間；預覽使用與正式匯出相同的合成引擎。"}
        return result

    def get_edit(self, project_id, edit_id):
        return self.store.get_edit(project_id, edit_id)

    def apply_edit(self, project_id, data):
        from .contracts import validate_request
        validate_request("edits/apply", data)
        project = self.store.apply_edit(project_id, data.get("expected_version"), data.get("edit_id"))
        result = self._decorate(project)
        result["edit_id"] = data["edit_id"]
        result["undo_receipt"] = {"action": "undo", "expected_version": project["version"], "one_step": True}
        result["verification"] = self.verify_edit(project_id, {"expected_version": project["version"]})
        return result

    def verify_edit(self, project_id, data):
        from .contracts import validate_request
        from .understanding import verify_project
        validate_request("verify", data)
        project = self._observation_project(project_id, data)
        result = verify_project(project, data)
        result.update(base_version=data["expected_version"], snapshot_version=project["version"],
            snapshot_kind="proposal" if data.get("edit_id") else "saved_project", edit_id=data.get("edit_id"),
            preview_side=data.get("preview_side", "after") if data.get("edit_id") else None)
        with self._lock:
            reviews = [copy.deepcopy(r) for r in self._reviews if r["project_id"] == project_id
                and r["revision"] == data["expected_version"] and r.get("edit_id") == data.get("edit_id")
                and r.get("preview_side") == (data.get("preview_side", "after") if data.get("edit_id") else None)]
        result["review_records"] = reviews
        continuous, sampled = [], []
        for record in reviews:
            try:
                manifest = self._evidence_raw(record["evidence_id"])
                selected = [f for f in manifest["files"] if f["id"] in record["file_ids"]]
            except EditorError:
                continue
            for file in selected:
                visual_checks = [c for c in record["checks"] if c in {"visual", "subtitle_layout"}]
                entry = {"evidence_id": record["evidence_id"], "file_id": file["id"],
                    "time_space": record["time_space"], "outcome": record["outcome"], "basis": "reviewer_self_report"}
                if file["kind"] == "image" and visual_checks:
                    sampled.append({**entry, "time": file.get("time"), "checks": visual_checks})
                elif file["kind"] in {"audio", "video"}:
                    checks = visual_checks if file["kind"] == "video" else []
                    if "audio" in record["checks"] and (file["kind"] == "audio" or file.get("has_audio")):
                        checks = checks + ["audio"]
                    if checks:
                        continuous.append({**entry, "range": file.get("range", record["range"]), "checks": checks})
        result["audiovisual_review"] = {"status": "partially_reviewed" if reviews else "not_reviewed",
            "basis": "explicit reviewer self-report for cited evidence; generated evidence alone is not a review",
            "reviewed_ranges": continuous, "sampled_frames": sampled,
            "unchecked": "所有未明列的區間與未完成的聲音／畫面檢查；抽樣影格不代表完整觀看。"}
        from .acceptance import evaluate_checks
        checks, evidence = [], []
        if data.get("edit_id"):
            checks = self.store.get_edit(project_id, data["edit_id"]).get("checks", [])
        else:
            applied = next((e for e in self.store.list_edits(project_id, limit=100)
                            if e.get("applied_version") == project["version"]), None)
            if applied:
                checks = self.store.get_edit(project_id, applied["id"]).get("checks", [])
        with self._lock:
            evidence_ids = list(set(self._evidence_cache.values()))
        for evidence_id in evidence_ids:
            try:
                item = self.evidence_manifest(evidence_id)
            except EditorError:
                continue
            if (item.get("project_id") == project_id and item.get("project_version") == data["expected_version"]
                    and item.get("edit_id") == data.get("edit_id") and item.get("preview_side") == result["preview_side"]):
                evidence.append(item)
        result["acceptance"] = evaluate_checks(project, checks, evidence)
        result["findings"] = [f for item in evidence for f in item.get("findings", [])]
        return result

    def record_review(self, project_id, data):
        from .contracts import validate_request
        validate_request("reviews", data)
        project = self._observation_project(project_id, data)
        manifest = self._evidence_raw(data.get("evidence_id"))
        if manifest.get("project_id") != project_id or manifest.get("project_version") != data["expected_version"] or manifest.get("edit_id") != data.get("edit_id"):
            raise EditorError("證據與目前專案版本或提案不符，請重新取得證據。", "version_conflict", 409)
        side = data.get("preview_side", "after") if data.get("edit_id") else None
        if manifest.get("preview_side") != side:
            raise EditorError("修改前與修改後的證據不可互相認證，請指定一致的 preview_side。")
        checks = data.get("checks")
        if not isinstance(checks, list) or not checks or set(checks) - {"visual", "audio", "subtitle_layout"}:
            raise EditorError("請指定實際完成的聲畫或字幕版面檢查。")
        file_ids = data.get("file_ids")
        if not isinstance(file_ids, list) or not file_ids or not all(isinstance(i, str) for i in file_ids):
            raise EditorError("請明確指定已觀看或聆聽的 file_ids。")
        files = [f for f in manifest["files"] if f["id"] in file_ids]
        if len(files) != len(set(file_ids)):
            raise EditorError("審閱包含不存在的證據。")
        kinds = {f["kind"] for f in files}
        has_audio = any(f["kind"] == "audio" or (f["kind"] == "video" and f.get("has_audio")) for f in files)
        if ("audio" in checks and not has_audio) or (set(checks) & {"visual", "subtitle_layout"} and not kinds & {"image", "video"}):
            raise EditorError("指定的證據未包含此項檢查需要的聲畫。")
        if "subtitle_layout" in checks and manifest.get("time_space") != "timeline":
            raise EditorError("來源證據未套用時間軸字幕；請取得合成時間軸證據檢查字幕版面。")
        notes, reviewer = data.get("notes"), data.get("reviewer")
        if not isinstance(notes, str) or not notes.strip() or len(notes) > 4000 or not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
            raise EditorError("請填寫審閱者與具體審閱紀錄。")
        if data.get("outcome") not in {"pass", "issue"}:
            raise EditorError("outcome 需為 pass 或 issue。")
        record = {"id": uuid.uuid4().hex, "project_id": project_id, "revision": data["expected_version"],
            "edit_id": data.get("edit_id"), "preview_side": side, "evidence_id": manifest["evidence_id"], "file_ids": file_ids,
            "range": manifest["range"], "time_space": manifest["time_space"], "checks": checks,
            "outcome": data["outcome"], "reviewer": reviewer, "notes": notes, "created_at": time.time(),
            "basis": "reviewer_self_report", "evidence_coverage": manifest.get("coverage", {}),
            "observed_files": [{k: f[k] for k in ("id", "kind", "time", "range", "has_audio") if k in f} for f in files]}
        with self._lock:
            self._reviews.append(record)
            self._reviews = self._reviews[-2000:]
            temporary = self._review_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self._reviews, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            temporary.replace(self._review_path)
        return record
