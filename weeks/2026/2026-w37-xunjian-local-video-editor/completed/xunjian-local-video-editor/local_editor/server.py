"""Loopback-only, same-origin HTTP host with bounded streamed uploads and Range."""

from __future__ import annotations

import hmac
import json
import mimetypes
import re
import secrets
import sys
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import __version__
from .contracts import validate_request
from .media_engine import MediaError
from .service import EditorService, ServiceError, error_payload


MAX_JSON = 4 * 1024 * 1024
MAX_UPLOAD = 10 * 1024 * 1024 * 1024
WEB_ROOT = Path(__file__).parent / "web"


class EditorHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, service: EditorService):
        if server_address[0] != "127.0.0.1":
            raise ValueError("剪輯工作台僅允許綁定 127.0.0.1")
        self.service = service
        self.token = secrets.token_urlsafe(32)
        super().__init__(server_address, EditorHandler)


class EditorHandler(BaseHTTPRequestHandler):
    server_version = "LocalEditor/" + __version__
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(120)

    def log_message(self, format, *args):
        # Never log tokens, file contents or request bodies.
        print(f"[local-editor] {self.command} {urlsplit(self.path).path} {args[1] if len(args) > 1 else ''}",
              file=sys.stderr)

    @property
    def service(self):
        return self.server.service

    def _guard(self, mutation=False):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:
            hosts |= {"127.0.0.1", "localhost"}
        host_headers = self.headers.get_all("Host", [])
        if len(host_headers) != 1 or host_headers[0].lower() not in hosts:
            raise ServiceError("此 Host 無法存取本地工作台", "invalid_host", 403)
        origin = self.headers.get("Origin")
        if origin is not None and origin != "http://" + host_headers[0].lower():
            raise ServiceError("禁止跨來源存取本地工作台", "invalid_origin", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise ServiceError("禁止跨網站存取本地工作台", "invalid_origin", 403)
        if mutation:
            supplied = self.headers.get("X-Editor-Token", "")
            if not hmac.compare_digest(supplied, self.server.token):
                raise ServiceError("工作階段已失效，請重新整理工作台", "invalid_session", 403)

    def _headers(self, status, content_type, length, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        if self.command != "HEAD":
            self.wfile.write(body)

    def _error(self, exc):
        # Close the connection: an early rejection may leave an unread body.
        self.close_connection = True
        status = getattr(exc, "status", 422 if isinstance(exc, MediaError) else 400)
        self._json({"error": error_payload(exc)}, status if isinstance(status, int) else 400)

    def _length(self, maximum):
        if self.headers.get("Transfer-Encoding"):
            raise ServiceError("請提供 Content-Length 上傳檔案", "length_required", 411)
        values = self.headers.get_all("Content-Length", [])
        if len(values) != 1:
            raise ServiceError("請提供單一 Content-Length", "length_required", 411)
        try:
            length = int(values[0])
        except ValueError as exc:
            raise ServiceError("Content-Length 格式錯誤") from exc
        if length < 0 or length > maximum:
            raise ServiceError("資料大小超過上限", "payload_too_large", 413)
        return length

    def _body(self):
        if self.headers.get_content_type() != "application/json":
            raise ServiceError("請使用 application/json", "unsupported_content_type", 415)
        length = self._length(MAX_JSON)
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ServiceError("資料傳輸不完整")
        try:
            data = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("不允許非有限數值")))
        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
            raise ServiceError("JSON 格式錯誤") from exc
        if not isinstance(data, dict):
            raise ServiceError("JSON 內容必須為物件")
        return data

    def _file(self, path: Path):
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        extra = {"Accept-Ranges": "bytes"}
        requested = self.headers.get("Range")
        if requested:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested.strip())
            valid = bool(match and any(match.groups()) and size)
            if valid:
                left, right = match.groups()
                if left:
                    start = int(left)
                    end = min(int(right), size - 1) if right else size - 1
                    valid = start <= end and start < size
                else:
                    suffix = int(right)
                    valid = suffix > 0
                    start = max(0, size - suffix)
            if not valid:
                self._headers(416, "application/octet-stream", 0, {"Content-Range": f"bytes */{size}"})
                return
            status = 206
            extra["Content-Range"] = f"bytes {start}-{end}/{size}"
        count = max(0, end - start + 1)
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if path.suffix == ".js":
            mime = "text/javascript"
        if mime.startswith("text/") or mime == "application/json":
            mime += "; charset=utf-8"
        self._headers(status, mime, count, extra)
        if self.command == "HEAD":
            return
        with path.open("rb") as source:
            source.seek(start)
            while count:
                chunk = source.read(min(count, 1024 * 1024))
                if not chunk:
                    break
                self.wfile.write(chunk)
                count -= len(chunk)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            self._guard()
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            parts = path.strip("/").split("/")
            query = parse_qs(parsed.query)
            if path == "/api/session":
                self._json({"token": self.server.token, "version": __version__})
            elif path == "/api/doctor":
                self._json(self.service.doctor())
            elif path == "/api/projects":
                self._json(self.service.list_projects())
            elif path == "/api/events":
                self._json(self.service.events())
            elif path == "/api/context":
                self._json(self.service.get_context({key: values[0] for key, values in query.items()}))
            elif path == "/api/jobs":
                self._json(self.service.list_jobs(query.get("project_id", [None])[0]))
            elif len(parts) == 3 and parts[:2] == ["api", "jobs"]:
                wait_ms = int(query.get("wait_ms", ["0"])[0])
                if not 0 <= wait_ms <= 20000:
                    raise ServiceError("wait_ms 必須介於 0 至 20000")
                self._json(self.service.job_status(parts[2], wait_ms=wait_ms) if wait_ms else self.service.job_status(parts[2]))
            elif len(parts) == 3 and parts[:2] == ["api", "evidence"]:
                self._json(self.service.evidence_manifest(parts[2]))
            elif len(parts) == 5 and parts[:2] == ["api", "evidence"] and parts[3] == "files":
                self._file(self.service.evidence_file(parts[2], parts[4]))
            elif len(parts) == 4 and parts[:2] == ["api", "exports"]:
                self._file(self.service.export_file(parts[2], parts[3]))
            elif len(parts) >= 3 and parts[:2] == ["api", "projects"]:
                project_id = parts[2]
                if len(parts) == 3:
                    self._json(self.service.get_project(project_id))
                elif len(parts) == 6 and parts[3] == "media" and parts[5] == "peaks":
                    chunk = query.get("chunk", ["0"])[0]
                    if not re.fullmatch(r"\d{1,7}", chunk):
                        raise ServiceError("波形區間格式不正確")
                    self._json(self.service.waveform_peaks(project_id, parts[4], int(chunk)))
                elif len(parts) == 6 and parts[3] == "media":
                    self._file(self.service.media_file(project_id, parts[4], parts[5]))
                elif len(parts) == 5 and parts[3] == "plans":
                    self._json(self.service.get_plan(project_id, parts[4]))
                elif len(parts) == 5 and parts[3] == "edits":
                    self._json(self.service.get_edit(project_id, parts[4]))
                elif parts[3:] == ["captions", "export"]:
                    self._json(self.service.export_captions(project_id, query.get("format", ["srt"])[0]))
                else:
                    raise ServiceError("找不到 API", "not_found", 404)
            elif path.startswith("/api/"):
                raise ServiceError("找不到 API", "not_found", 404)
            else:
                relative = "index.html" if path == "/" else path.lstrip("/")
                asset = (WEB_ROOT / relative).resolve()
                if (not asset.is_relative_to(WEB_ROOT.resolve()) or not asset.is_file()
                        or asset.suffix.lower() not in {".html", ".css", ".js", ".svg", ".png", ".ico", ".woff2"}):
                    raise ServiceError("找不到頁面", "not_found", 404)
                self._file(asset)
        except ConnectionError:
            return
        except (ValueError, OSError, MediaError) as exc:
            self._error(exc)
        except Exception as exc:
            print(f"[local-editor] internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
            self._error(ServiceError("伺服器處理失敗，請查看本地終端機紀錄", "internal_error", 500))

    def _upload(self, project_id, query):
        try:
            expected = int(query.get("expected_version", [""])[0])
        except ValueError as exc:
            raise ServiceError("expected_version 必須為整數") from exc
        filename = query.get("name", [""])[0]
        if (not filename or len(filename) > 255 or any(char in filename for char in '<>:"/\\|?*\x00')
                or filename.endswith((".", " "))):
            raise ServiceError("素材檔名格式錯誤")
        self.service.validate_import(project_id, expected, filename)
        length = self._length(MAX_UPLOAD)
        if not length:
            raise ServiceError("素材檔案不可為空")
        directory = self.service.uploads / uuid.uuid4().hex
        directory.mkdir()
        destination = directory / filename
        try:
            remaining = length
            with destination.open("xb") as target:
                while remaining:
                    chunk = self.rfile.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise ServiceError("素材上傳中斷")
                    target.write(chunk)
                    remaining -= len(chunk)
            return self.service.import_media(project_id, {"expected_version": expected, "path": str(destination)})
        finally:
            destination.unlink(missing_ok=True)
            directory.rmdir()

    def do_POST(self):
        try:
            self._guard(mutation=True)
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            parts = path.strip("/").split("/")
            actor = "agent" if self.headers.get("X-Editor-Client") == "mcp" else "ui"
            project_id = parts[2] if len(parts) > 2 and parts[:2] == ["api", "projects"] else None
            if path == "/api/projects":
                result = self.service.create_project(self._body())
                project_id = result["id"]
            elif path == "/api/context":
                result = self.service.update_context(self._body())
            elif path == "/api/agents":
                result = self.service.record_agent(self._body())
            elif project_id:
                operation = "/".join(parts[3:])
                if operation == "media/upload":
                    result = self._upload(project_id, parse_qs(parsed.query))
                else:
                    actions = {"edit": "edit", "media/import": "import_media", "plans": "prepare_plan",
                               "smart-cut": "prepare_smart_cut", "smart-cut/apply": "apply_smart_cut",
                               "captions/import": "import_captions", "transcribe": "transcribe", "export": "export",
                               "inspect": "inspect_range", "analyze": "analyze_range", "edits": "prepare_edit",
                               "edits/apply": "apply_edit", "verify": "verify_edit",
                               "captions/review": "review_caption", "reviews": "record_review"}
                    if operation not in actions:
                        raise ServiceError("找不到 API", "not_found", 404)
                    data = self._body()
                    validate_request(operation, data)
                    result = getattr(self.service, actions[operation])(project_id, data)
            else:
                raise ServiceError("找不到 API", "not_found", 404)
            if path not in {"/api/context", "/api/agents"}:
                self.service.record_event(path, project_id, actor)
            self._json(result)
        except ConnectionError:
            return
        except (ValueError, OSError, MediaError) as exc:
            self._error(exc)
        except Exception as exc:
            print(f"[local-editor] internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
            self._error(ServiceError("伺服器處理失敗，請查看本地終端機紀錄", "internal_error", 500))

    def do_OPTIONS(self):
        self._error(ServiceError("本地 API 不允許跨來源呼叫", "invalid_origin", 403))


def make_server(data_dir: str | Path, port: int = 8321):
    service = EditorService(data_dir)
    try:
        return EditorHTTPServer(("127.0.0.1", port), service)
    except Exception:
        service.close()
        raise


def serve_forever(data_dir: str | Path, port: int = 8321, *, open_browser=False):
    server = make_server(data_dir, port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"本地剪輯工作台：{url}\n專案資料：{server.service.root}\n按 Ctrl+C 結束。", file=sys.stderr)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        server.service.close()
