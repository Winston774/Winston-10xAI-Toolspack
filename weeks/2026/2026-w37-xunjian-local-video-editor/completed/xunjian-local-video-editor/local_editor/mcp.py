"""Newline-delimited UTF-8 stdio MCP, backed by the running local HTTP host.

Protocol reference: https://modelcontextprotocol.io/specification/2025-11-25
The HTTP API is an internal bridge, not a Streamable HTTP MCP transport.
"""

from __future__ import annotations

import base64
import json
import re
import sys
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from . import __version__
from .contracts import (EDIT_ACTIONS, CANONICAL_ACTION_PARAMS, ASR_OPTIONS, EXPORT_OPTIONS,
                        ID, INSPECT_SCHEMA, ANALYZE_SCHEMA, PREPARE_EDIT_SCHEMA, APPLY_EDIT_SCHEMA,
                        VERIFY_EDIT_SCHEMA, REVIEW_CAPTION_SCHEMA, RECORD_REVIEW_SCHEMA,
                        obj, validate as _validate, validate_request)


PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_VERSIONS = {PROTOCOL_VERSION, "2025-06-18"}
MAX_MESSAGE = 4 * 1024 * 1024
MAX_EVIDENCE_BYTES = 12 * 1024 * 1024
EVIDENCE_MIMES = {"image/jpeg", "image/png", "image/webp", "audio/wav", "audio/x-wav",
                  "audio/mpeg", "audio/mp4", "audio/ogg", "video/mp4", "video/webm"}
S = {"type": "string", "minLength": 1}
P = {"project_id": {**ID, "description": "專案 ID，先呼叫 editor_get_context 或 editor_list_projects 取得。"}}
V = {**P, "expected_version": {"type": "integer", "minimum": 1, "description": "最近讀取的精確版本；衝突時重新讀取。"}}
OPTIONS = {"type": "object"}


def _tool(name, description, properties=None, required=(), *, read_only=False, schema=None, idempotent=None):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", **schema} if schema else obj(properties, required),
            "annotations": {"readOnlyHint": read_only, "destructiveHint": False,
                            "idempotentHint": read_only if idempotent is None else idempotent, "openWorldHint": False}}


TOOLS = [
    _tool("editor_doctor", "檢查本地 FFmpeg、字幕辨識依賴與服務狀態。", read_only=True),
    _tool("editor_list_projects", "列出本地專案的 ID、版本、時長與摘要。", read_only=True),
    _tool("editor_create_project", "建立本地專案。預設 1920×1080、30 fps，主要語言繁體中文。",
          {"name": S, "width": {"type": "integer", "minimum": 128},
           "height": {"type": "integer", "minimum": 128}, "fps": {"type": "number", "minimum": 1}}, ["name"]),
    _tool("editor_get_project", "讀取時間軸、素材、來源字幕與精確版本；省略波形及縮圖資料降低 token。", P, ["project_id"], read_only=True),
    _tool("editor_import_media", "把明確指定的本機影片、音訊或圖片複製到受管理素材目錄。回傳新版本與 media_id；再以 clip_add 加入時間軸。",
          {**V, "path": {**S, "description": "本機素材絕對路徑。"}}, [*V, "path"]),
    _tool("editor_edit", "版本化剪輯，可復原。clip_add: params={media_id,track,start,end,offset}; clip_update: {clip_id,changes:{...}}; clip_split: {clip_id,at:時間軸秒}; clip_delete: {clip_id,ripple:false}; rename: {name}; settings:{width,height,fps}; caption_update:{caption_id,changes:{text,start,end}}; undo/redo: {}。start/end 是來源秒、offset 是時間軸秒。",
          schema={"oneOf": [obj({**V, "action": {"const": action}, "params": CANONICAL_ACTION_PARAMS[action]},
                                 [*V, "action", "params"]) for action in EDIT_ACTIONS]}),
    _tool("editor_prepare_smart_cut", "智能剪口播：背景分析停頓、語助詞與相鄰重複字幕，建立候選提案，保留時間軸。素材須已在主影片軌。以 editor_job_status 輪詢完成後審閱 plan；只有明確選擇 candidate_ids 才套用。",
          {**V, "media_id": S, "options": {"type": "object", "properties": {
              "threshold_db": {"type": "number", "minimum": -80, "maximum": -5},
              "min_silence": {"type": "number", "minimum": .1, "maximum": 10},
              "keep_pause": {"type": "number", "minimum": 0, "maximum": 5},
              "detect_silence": {"type": "boolean"}, "detect_fillers": {"type": "boolean"},
              "detect_repeats": {"type": "boolean"}}, "additionalProperties": False}}, [*V, "media_id"]),
    _tool("editor_get_smart_cut_plan", "讀取智能剪口播提案與候選原因，不修改時間軸。",
          {**P, "plan_id": S}, [*P, "plan_id"], read_only=True),
    _tool("editor_prepare_plan", "根據已讀取逐字稿，將明確的素材來源時間區間建立為剪輯提案。候選必須落在主影片軌；建立後審閱，再以 editor_apply_smart_cut 套用。可用於刪文剪片。",
          {**V, "candidates": {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {
              "media_id": S, "start": {"type": "number", "minimum": 0},
              "end": {"type": "number", "minimum": 0}, "reason": S, "text": {"type": "string"},
              "kind": {"type": "string"}}, "required": ["media_id", "start", "end"], "additionalProperties": False}},
           "metadata": OPTIONS}, [*V, "candidates"]),
    _tool("editor_apply_smart_cut", "套用已審閱提案中明確指定的候選；同步壓縮多軌時間軸並映射字幕，可 undo。提案版本過期時拒絕執行。",
          {**V, "plan_id": S, "candidate_ids": {"type": "array", "items": S, "minItems": 1, "uniqueItems": True}},
          [*V, "plan_id", "candidate_ids"]),
    _tool("editor_import_captions", "匯入 SRT/VTT 為素材來源字幕；取代此素材既有字幕，依 source time 儲存。",
          {**V, "media_id": S, "text": S, "format": {"type": "string", "enum": ["srt", "vtt"]}}, [*V, "media_id", "text", "format"]),
    _tool("editor_export_captions", "輸出經剪輯、變速、位移映射後的時間軸字幕文字，支援 SRT/VTT/TXT。",
          {**P, "format": {"type": "string", "enum": ["srt", "vtt", "txt"]}}, [*P], read_only=True),
    _tool("editor_transcribe", "背景執行本機 faster-whisper 語音辨識，完成後寫入來源字幕。需要已安裝套件與已快取模型；不會自動下載。options 可指定 model_path,model,device,compute_type,language,timeout。專案版本已變更時拒絕寫入。",
          {**V, "media_id": ID, "options": ASR_OPTIONS}, [*V, "media_id"]),
    _tool("editor_export", "背景輸出 MP4；渲染呼叫當下的精確專案快照，保留來源檔。options 可設 width,height,fps,crf,preset,burn_captions,denoise,normalize_audio（單遍響度正規化）。回傳 job_id；完成後取得本地 path 與下載 url。",
          {**V, "options": EXPORT_OPTIONS}, [*V]),
    _tool("editor_job_status", "讀取 queued/running/succeeded/failed 狀態、進度與結果。wait_ms 0..20000 可等待完成，避免頻繁輪詢。證據工作 result.evidence 可交給 editor_read_evidence 直接取得畫面與音訊。",
          {"job_id": ID, "wait_ms": {"type": "integer", "minimum": 0, "maximum": 20000}}, ["job_id"], read_only=True),
    _tool("editor_get_context", "第一個呼叫：取得目前 UI 專案、精確版本、選取項目、播放頭、選取區間、剪輯方向 brief、工作狀態、Agent 連線、可用能力及未知。未開啟或過期 UI 會明確回報，不會猜測目前專案。可指定 project_id 讀取背景專案。",
          {**P, "client_id": ID}, read_only=True),
]


def _project_schema(schema):
    return {**schema, "properties": {**P, **schema["properties"]},
            "required": ["project_id", *schema.get("required", [])]}


TOOLS.extend([
    _tool("editor_inspect_range", "取得精確版本最多 30 秒區間的聲畫證據、逐字稿、圖層及切點。source 必須給 media_id；timeline 使用匯出合成器。max_frames 最多 8。sampling.strategy=cut_boundaries 搭配 offset_frames 取樣切點；scan_black_frames=true 逐影格掃描近黑候選，附 findings 與來源映射。提供 edit_id 可觀察未套用提案。回傳 job；完成後用 editor_read_evidence 讀取原生媒體。抽樣或掃描通過不等於完整視聽確認；證據保存在本機快取。",
          schema=_project_schema(INSPECT_SCHEMA)),
    _tool("editor_analyze_range", "分析最多 30 秒來源或時間軸區間：停頓、語速、重複候選、畫面變化、字幕問題，並附原始證據及未知。偵測可靠度與可刪除判斷分開；不保證畫面操作或跨段語意已理解。回傳 job，分析與證據保存在本機快取。",
          schema=_project_schema(ANALYZE_SCHEMA)),
    _tool("editor_prepare_edit", "將 operations 試剪成版本綁定提案，回傳差異、時長與字幕副作用。checks 可指定 no_timeline_gaps、duration_between、no_black_frames（需 range）；以 verify_edit 更新驗收，缺少證據維持 pending。以 inspect_range 加 edit_id 比較提案，再明確 apply_edit。caption_update 提供 words 可保留對齊，只改文字／時間標 stale；詞時間有效仍需聽覺複核。",
          schema=_project_schema(PREPARE_EDIT_SCHEMA)),
    _tool("editor_get_edit", "讀取已保存提案差異、intent、版本與套用狀態。", {**P, "edit_id": ID}, [*P, "edit_id"], read_only=True),
    _tool("editor_apply_edit", "將已審閱提案原子套用為一個可復原步驟。expected_version 與提案 base_version 必須匹配；批次中任一失敗不會部分寫入。回傳修改摘要、警告、復原識別與新版本。",
          schema=_project_schema(APPLY_EDIT_SCHEMA)),
    _tool("editor_verify_edit", "檢查精確版本的結構、剪點、字幕對齊與版面風險；分別列出已通過、待看畫面、待聽音訊、未知及已登錄複核覆蓋範圍。此工具不會自動宣稱聽感自然或畫面語意正確。需要聲畫時再 inspect_range / read_evidence。",
          schema=_project_schema(VERIFY_EDIT_SCHEMA), read_only=True),
    _tool("editor_review_caption", "指定 caption_id 在本機擷取短音訊並重新辨識，回傳候選文字、詞時間、對齐狀態與證據。只保存複核結果，不直接取代字幕。以 prepare_edit 的 caption_update 明確選用候選；尚未提供任意文字的強制對齊。options.padding 最多 2 秒。回傳 job。",
          schema=_project_schema(REVIEW_CAPTION_SCHEMA)),
    _tool("editor_record_review", "在實際看過／聽過 editor_read_evidence 證據後登錄複核。需指定 evidence_id、檢查類型、reviewer、outcome 及 notes；只代表 reviewer 的自述確認。服務驗證證據版本及媒體類型，不能以生成證據冒充已複核，也不能擴張到未讀區間。",
          schema=_project_schema(RECORD_REVIEW_SCHEMA)),
    _tool("editor_read_evidence", "讀取已登錄證據清單，直接回傳 MCP image/audio 區塊及影片 resource_link，無需本機路徑或自行 FFmpeg。預設最多 3 張影格、1 段音訊及影片連結；可明確給 file_ids 指定其他檔案。單次二進位總上限 12 MiB；JSON 僅保留 metadata，不含 base64。",
          {"evidence_id": ID, "file_ids": {"type": "array", "items": ID, "minItems": 1, "maxItems": 12, "uniqueItems": True}},
          ["evidence_id"], read_only=True),
])
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}
for _name in ("editor_edit", "editor_apply_smart_cut", "editor_import_captions", "editor_transcribe", "editor_apply_edit"):
    TOOL_BY_NAME[_name]["annotations"]["destructiveHint"] = True


class ToolError(ValueError):
    def __init__(self, message, code="tool_error"):
        super().__init__(message)
        self.code = code


class NativeResult:
    """Keep multimodal content out of structured JSON and its serialized copy."""
    def __init__(self, value, content):
        self.value, self.content = value, content


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTPBridge:
    def __init__(self, url: str):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or not parsed.port):
            raise ValueError("MCP --url 必須是 http://127.0.0.1:埠號 或 http://localhost:埠號")
        self.url = url.rstrip("/")
        self.token = None
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())
        self.client_id = uuid.uuid4().hex
        self.client_info = {}
        self.known_resources = {}

    def record_agent(self, *, client_info=None, last_tool=None, status="connected"):
        if client_info is not None:
            self.client_info = client_info
        try:
            return self.request("/api/agents", {"client_id": self.client_id,
                "client_info": self.client_info, "status": status, "last_tool": last_tool})
        except ToolError as exc:
            # Discovery works while the workbench is offline; tools report the error when used.
            print(f"[local-editor-mcp] agent presence unavailable: {exc.code}", file=sys.stderr)

    def request(self, path, data=None, *, retried=False):
        if data is not None and self.token is None:
            self.token = self.request("/api/session")["token"]
        headers = {"Accept": "application/json", "X-Editor-Client": "mcp"}
        body = None
        if data is not None:
            headers.update({"Content-Type": "application/json", "X-Editor-Token": self.token})
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        try:
            request = Request(self.url + path, data=body, headers=headers)
            with self.opener.open(request, timeout=120) as response:
                return json.load(response)
        except HTTPError as exc:
            try:
                payload = json.loads(exc.read()).get("error", {})
            except (ValueError, AttributeError):
                payload = {"message": f"本地 API 回傳 HTTP {exc.code}", "code": "http_error"}
            if payload.get("code") == "invalid_session" and data is not None and not retried:
                self.token = None
                return self.request(path, data, retried=True)
            raise ToolError(payload.get("message", "本地 API 呼叫失敗"), payload.get("code", "http_error")) from exc
        except (URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise ToolError("無法連線本地工作台，請先啟動 python -m local_editor serve。", "service_unavailable") from exc

    def evidence_manifest(self, evidence_id):
        _validate(evidence_id, ID, "evidence_id")
        manifest = self.request("/api/evidence/" + evidence_id)
        if not isinstance(manifest, dict) or manifest.get("evidence_id") != evidence_id:
            raise ToolError("證據清單與請求 ID 不一致", "invalid_evidence")
        files = manifest.get("files", [])
        if not isinstance(files, list) or len(files) > 32:
            raise ToolError("證據清單格式或檔案數量不符", "invalid_evidence")
        seen = set()
        for entry in files:
            if not isinstance(entry, dict):
                raise ToolError("證據檔案格式不符", "invalid_evidence")
            _validate(entry.get("id"), ID, "file_id")
            file_id = entry["id"]
            expected_path = f"/api/evidence/{evidence_id}/files/{file_id}"
            if file_id in seen or entry.get("url") != expected_path or entry.get("mime_type") not in EVIDENCE_MIMES:
                raise ToolError("證據 URL、媒體類型或 ID 未符合受管理契約", "invalid_evidence")
            seen.add(file_id)
        return manifest

    def evidence_bytes(self, evidence_id, entry, budget=MAX_EVIDENCE_BYTES):
        # Never follow a caller-supplied path, URL, redirect or filesystem reference.
        path = f"/api/evidence/{evidence_id}/files/{entry['id']}"
        try:
            with self.opener.open(Request(self.url + path, headers={"X-Editor-Client": "mcp"}), timeout=120) as response:
                mime = response.headers.get_content_type()
                expected_mime = entry["mime_type"]
                aliases = {"audio/x-wav": "audio/wav"}
                if aliases.get(mime, mime) != aliases.get(expected_mime, expected_mime):
                    raise ToolError("證據檔案 MIME 與已登錄資料不符", "invalid_evidence")
                length = response.headers.get("Content-Length")
                if length is not None and int(length) > budget:
                    raise ToolError("證據超過 12 MiB 回傳上限；請縮短區間或減少 file_ids", "evidence_too_large")
                data = response.read(budget + 1)
                if len(data) > budget:
                    raise ToolError("證據超過回傳上限；請縮短區間或減少 file_ids", "evidence_too_large")
                return data
        except HTTPError as exc:
            raise ToolError("無法讀取已登錄證據檔案", "evidence_unavailable") from exc
        except (URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise ToolError("本地證據服務無法連線", "service_unavailable") from exc

    def read_evidence(self, evidence_id, file_ids=None):
        manifest = self.evidence_manifest(evidence_id)
        files = manifest["files"]
        by_id = {entry["id"]: entry for entry in files}
        if file_ids is not None:
            if any(file_id not in by_id for file_id in file_ids):
                raise ToolError("指定 file_id 不在此證據清單中", "evidence_file_not_found")
            selected = [by_id[file_id] for file_id in file_ids]
        else:
            images = sorted([f for f in files if f["mime_type"].startswith("image/")],
                            key=lambda f: not bool(f.get("finding_id")))[:3]
            sounds = [f for f in files if f["mime_type"].startswith("audio/")][:1]
            videos = [f for f in files if f["mime_type"].startswith("video/")]
            selected = images + sounds + videos
        content, remaining, delivered, linked = [], MAX_EVIDENCE_BYTES, [], []
        for entry in selected:
            file_id, mime = entry["id"], entry["mime_type"]
            uri = f"evidence://{evidence_id}/{file_id}"
            self.known_resources[uri] = {"uri": uri, "name": file_id, "mimeType": mime,
                                         "description": f"{evidence_id}：{entry.get('kind', mime)}"}
            if mime.startswith("video/"):
                content.append({"type": "resource_link", **self.known_resources[uri]})
                linked.append(file_id)
            else:
                raw = self.evidence_bytes(evidence_id, entry, remaining)
                remaining -= len(raw)
                content.append({"type": "image" if mime.startswith("image/") else "audio",
                                "mimeType": "audio/wav" if mime == "audio/x-wav" else mime,
                                "data": base64.b64encode(raw).decode("ascii")})
                delivered.append(file_id)
        result = {**manifest, "included_file_ids": delivered, "linked_file_ids": linked,
                  "omitted_file_ids": [entry["id"] for entry in files if entry["id"] not in delivered + linked],
                  "review_status": "evidence_delivered_not_reviewed"}
        return NativeResult(result, content)

    def read_resource(self, uri):
        match = re.fullmatch(r"evidence://([A-Za-z0-9_-]{1,100})/([A-Za-z0-9_-]{1,100})", uri or "")
        if not match:
            raise ToolError("僅接受已登錄 evidence:// 證據 URI", "invalid_resource_uri")
        evidence_id, file_id = match.groups()
        manifest = self.evidence_manifest(evidence_id)
        entry = next((item for item in manifest["files"] if item["id"] == file_id), None)
        if entry is None:
            raise ToolError("指定 file_id 不在此證據清單中", "evidence_file_not_found")
        raw = self.evidence_bytes(evidence_id, entry)
        return {"contents": [{"uri": uri, "mimeType": entry["mime_type"],
                              "blob": base64.b64encode(raw).decode("ascii")}]}

    def call(self, name: str, arguments: dict):
        data = dict(arguments)
        project_id = data.pop("project_id", None)
        base = f"/api/projects/{quote(project_id, safe='')}" if project_id else ""
        if name == "editor_doctor":
            result = self.request("/api/doctor")
        elif name == "editor_list_projects":
            result = self.request("/api/projects")
        elif name == "editor_create_project":
            result = self.request("/api/projects", data)
        elif name == "editor_get_project":
            result = self.request(base)
        elif name == "editor_get_context":
            result = self.request("/api/context?" + urlencode(arguments))
        elif name == "editor_read_evidence":
            return self.read_evidence(data["evidence_id"], data.get("file_ids"))
        elif name == "editor_job_status":
            result = self.request("/api/jobs/" + quote(data["job_id"], safe="") + "?" + urlencode({"wait_ms": data.get("wait_ms", 0)}))
        elif name == "editor_get_edit":
            result = self.request(base + "/edits/" + quote(data["edit_id"], safe=""))
        elif name == "editor_get_smart_cut_plan":
            result = self.request(base + "/plans/" + quote(data["plan_id"], safe=""))
        elif name == "editor_export_captions":
            result = self.request(base + "/captions/export?" + urlencode({"format": data.get("format", "srt")}))
        else:
            routes = {"editor_import_media": "media/import", "editor_edit": "edit",
                      "editor_prepare_plan": "plans",
                      "editor_prepare_smart_cut": "smart-cut", "editor_apply_smart_cut": "smart-cut/apply",
                      "editor_import_captions": "captions/import", "editor_transcribe": "transcribe",
                      "editor_export": "export", "editor_inspect_range": "inspect", "editor_analyze_range": "analyze",
                      "editor_prepare_edit": "edits", "editor_apply_edit": "edits/apply", "editor_verify_edit": "verify",
                      "editor_review_caption": "captions/review", "editor_record_review": "reviews"}
            validate_request(routes[name], data)
            result = self.request(base + "/" + routes[name], data)
        result = _compact(result)
        if name not in {"editor_get_project", "editor_job_status"} and isinstance(result, dict) and "clips" in result:
            summary = {key: result[key] for key in ("id", "name", "version", "duration", "can_undo", "can_redo") if key in result}
            summary.update({"media_count": len(result.get("media", [])), "clip_count": len(result.get("clips", [])),
                            "caption_count": len(result.get("captions", []))})
            if name == "editor_import_media" and result.get("media"):
                summary["media"] = result["media"][-1]
            # The compact response must retain edit reliability and review consequences.
            summary.update({key: result[key] for key in ("warnings", "side_effects", "alignment_changes",
                           "undo_id", "undo_ref", "undo_receipt", "applied_version", "edit_id", "diff", "affected_ids", "verification", "brief") if key in result})
            result = summary
        return result


def _compact(value):
    if isinstance(value, list):
        return [_compact(item) for item in value]
    if isinstance(value, dict):
        media_record = isinstance(value.get("kind"), str) and value["kind"] in {"video", "audio", "image"} and "id" in value and "duration" in value
        return {key: _compact(item) for key, item in value.items()
                if key not in {"waveform_url", "thumbnail", "thumbnail_url"}
                and not (key == "waveform" and (media_record or isinstance(item, str)))}
    return value


class MCPServer:
    def __init__(self, bridge: HTTPBridge):
        self.bridge = bridge
        self.initialized = False
        self.ready = False

    @staticmethod
    def error(request_id, code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def handle(self, message):
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return self.error(None, -32600, "Invalid Request")
        has_id = "id" in message
        request_id, method = message.get("id"), message["method"]
        if has_id and (not isinstance(request_id, (str, int)) or isinstance(request_id, bool)):
            return self.error(None, -32600, "Invalid request id")
        params = message.get("params", {})
        if not isinstance(params, dict):
            return self.error(request_id, -32602, "params 必須為物件") if has_id else None
        if not has_id:
            if method == "notifications/initialized" and self.initialized:
                self.ready = True
            return None
        if method == "initialize":
            if self.initialized:
                return self.error(request_id, -32600, "Already initialized")
            if (not isinstance(params.get("protocolVersion"), str)
                    or not isinstance(params.get("capabilities"), dict)
                    or not isinstance(params.get("clientInfo"), dict)):
                return self.error(request_id, -32602, "initialize 缺少 protocolVersion/capabilities/clientInfo")
            version = params["protocolVersion"]
            self.initialized = True
            self.bridge.record_agent(client_info=params["clientInfo"])
            result = {"protocolVersion": version if version in SUPPORTED_VERSIONS else PROTOCOL_VERSION,
                      "capabilities": {"tools": {"listChanged": False}, "resources": {"subscribe": False, "listChanged": False}},
                      "serverInfo": {"name": "local-editor", "title": "本地剪輯工作台", "version": __version__},
                      "instructions": "先 editor_get_context 取得 UI 情境與剪輯方向，再 inspect_range/read_evidence 直接看聽聲畫。analyze_range 明列證據與未知；prepare_edit 取得差異，以 inspect_range 加 edit_id 比較提案，apply_edit 原子套用，verify_edit 分別確認結構與複核覆蓋。所有操作使用精確 expected_version；版本衝突重新讀取。長工作回傳 job_id，job_status 支援 wait_ms<=20000。畫面與音訊透過原生媒體區塊，影片透過 evidence:// 資源；勿自行找素材路徑或另寫 FFmpeg。證據已產生不表示已複核，實際檢查後才 record_review。"}
        elif method == "ping":
            result = {}
        elif not self.ready:
            return self.error(request_id, -32002, "請先 initialize 並傳送 notifications/initialized")
        elif method == "tools/list":
            if params.get("cursor"):
                return self.error(request_id, -32602, "Invalid cursor")
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments", {})
            if not isinstance(name, str) or name not in TOOL_BY_NAME:
                return self.error(request_id, -32602, "Unknown tool")
            try:
                _validate(arguments, TOOL_BY_NAME[name]["inputSchema"])
            except (ValueError, RecursionError) as exc:
                return self.error(request_id, -32602, str(exc))
            try:
                self.bridge.record_agent(last_tool=name)
                value = self.bridge.call(name, arguments)
                media_content = []
                if isinstance(value, NativeResult):
                    media_content, value = value.content, value.value
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, separators=(",", ":"))}],
                          "structuredContent": value, "isError": False}
                result["content"].extend(media_content)
            except (ToolError, ValueError) as exc:
                value = {"code": getattr(exc, "code", "tool_error"), "message": str(exc)}
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                          "structuredContent": value, "isError": True}
            except Exception as exc:
                print(f"[local-editor-mcp] {type(exc).__name__}: {exc}", file=sys.stderr)
                result = {"content": [{"type": "text", "text": "工具執行失敗，請查看本地服務紀錄。"}], "isError": True}
        elif method == "resources/list":
            if params.get("cursor"):
                return self.error(request_id, -32602, "Invalid cursor")
            result = {"resources": list(self.bridge.known_resources.values())}
        elif method == "resources/read":
            if not isinstance(params.get("uri"), str):
                return self.error(request_id, -32602, "uri 必須為文字")
            try:
                result = self.bridge.read_resource(params["uri"])
            except (ToolError, ValueError) as exc:
                return self.error(request_id, -32602, str(exc))
        else:
            return self.error(request_id, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}


def run_stdio(url: str, input_stream=None, output_stream=None):
    server = MCPServer(HTTPBridge(url))
    source = input_stream if input_stream is not None else sys.stdin.buffer
    target = output_stream if output_stream is not None else sys.stdout.buffer
    while True:
        line = source.readline(MAX_MESSAGE + 1)
        if not line:
            if server.initialized:
                server.bridge.record_agent(status="disconnected")
            return 0
        if len(line) > MAX_MESSAGE:
            response = server.error(None, -32700, "Message too large")
            target.write((json.dumps(response) + "\n").encode("utf-8"))
            target.flush()
            if server.initialized:
                server.bridge.record_agent(status="disconnected")
            return 1
        try:
            message = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (ValueError, UnicodeDecodeError, RecursionError):
            response = server.error(None, -32700, "Parse error")
        else:
            response = server.handle(message)
        if response is not None:
            try:
                target.write((json.dumps(response, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8"))
                target.flush()
            except (BrokenPipeError, ConnectionResetError):
                return 0
