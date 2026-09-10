"""Live loopback HTTP and real stdio subprocess protocol integration tests."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

from local_editor.mcp import HTTPBridge, MCPServer, run_stdio
from local_editor.server import make_server
from local_editor.service import EditorService, ServiceError


class EditorAPITest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.server = make_server(self.directory.name, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.opener = build_opener(ProxyHandler({}))
        self.token = self.request("/api/session")[1]["token"]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server.service.close()
        self.thread.join(timeout=3)
        self.directory.cleanup()

    def request(self, path, data=None, headers=None, *, raw=None, method=None):
        request_headers = dict(headers or {})
        body = raw
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
            request_headers.setdefault("X-Editor-Token", self.token)
        request = Request(self.url + path, data=body, headers=request_headers, method=method)
        try:
            response = self.opener.open(request, timeout=5)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            value = json.loads(body) if body and "application/json" in response.headers.get("Content-Type", "") else body
            return response.status, value, response.headers

    def project(self):
        status, project, _ = self.request("/api/projects", {"name": "繁體中文口播測試"})
        self.assertEqual(status, 200)
        return project

    def fixture_media(self, project):
        path = self.server.service.assets / "sample.mp4"
        path.write_bytes(b"0123456789abcdef")
        media = {"id": "sample", "name": "sample.mp4", "path": str(path), "kind": "video",
                 "duration": 10, "width": 320, "height": 180, "has_audio": True}
        project = self.server.service.store.mutate(project["id"], project["version"], "media_add", {"media": media})
        return self.server.service.store.mutate(project["id"], project["version"], "clip_add", {"media_id": "sample"})

    def wait_job(self, job_id):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            job = self.request(f"/api/jobs/{job_id}")[1]
            if job["status"] in {"succeeded", "failed"}:
                return job
            threading.Event().wait(.01)
        self.fail("background job did not finish")

    def test_project_mutation_conflict_and_persistence(self):
        project = self.project()
        endpoint = f"/api/projects/{project['id']}/edit"
        status, updated, _ = self.request(endpoint, {"expected_version": project["version"], "action": "rename", "params": {"name": "新版口播"}})
        self.assertEqual(status, 200)
        self.assertEqual(updated["version"], project["version"] + 1)
        status, error, _ = self.request(endpoint, {"expected_version": project["version"], "action": "rename", "params": {"name": "過期寫入"}})
        self.assertEqual(status, 409)
        self.assertEqual(error["error"]["code"], "version_conflict")
        other = EditorService(self.directory.name)
        try:
            self.assertEqual(other.get_project(project["id"])["name"], "新版口播")
        finally:
            other.close()

    def test_origin_host_token_and_unsafe_media_record_are_rejected(self):
        self.assertEqual(self.request("/api/session", headers={"Origin": "https://evil.invalid"})[0], 403)
        self.assertEqual(self.request("/api/session", headers={"Host": "evil.invalid"})[0], 403)
        self.assertEqual(self.request("/api/session", headers={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.request("/api/projects", {"name": "x"}, {"X-Editor-Token": "wrong"})[0], 403)
        project = self.project()
        status, error, _ = self.request(f"/api/projects/{project['id']}/edit", {
            "expected_version": project["version"], "action": "media_add", "params": {"path": "C:/secret.mp4"}})
        self.assertEqual(status, 403)
        self.assertEqual(error["error"]["code"], "protected_action")
        self.assertEqual(self.request("/%2e%2e/pyproject.toml")[0], 404)
        self.assertEqual(self.request("/api/files?path=C:/Windows/win.ini")[0], 404)

    def test_registered_media_ranges_and_security_headers(self):
        project = self.fixture_media(self.project())
        endpoint = f"/api/projects/{project['id']}/media/sample/file"
        status, body, headers = self.request(endpoint, headers={"Range": "bytes=2-5"})
        self.assertEqual((status, body), (206, b"2345"))
        self.assertEqual(headers["Content-Range"], "bytes 2-5/16")
        self.assertEqual(headers["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request(endpoint, headers={"Range": "bytes=-3"})[:2], (206, b"def"))
        self.assertEqual(self.request(endpoint, headers={"Range": "bytes=90-"})[0], 416)
        self.assertEqual(self.request(endpoint, headers={"Range": "bytes=0-2,4-6"})[0], 416)
        self.assertEqual(self.request(endpoint, method="HEAD")[1], b"")
        self.assertEqual(self.request(f"/api/projects/{project['id']}/media/sample/../file")[0], 404)
        self.assertEqual(self.request(f"/api/projects/{project['id']}/media/nope/file")[0], 404)

    def test_streamed_upload_validates_type_and_registers_bytes(self):
        project = self.project()
        endpoint = f"/api/projects/{project['id']}/media/upload?expected_version={project['version']}&name="
        headers = {"Content-Type": "application/octet-stream", "X-Editor-Token": self.token}
        self.assertEqual(self.request(endpoint + "secret.txt", raw=b"secret", headers=headers)[0], 415)

        def fake_import(source, asset_dir):
            target = Path(asset_dir) / "uploaded.mp4"
            shutil.copy2(source, target)
            return {"id": "uploaded", "name": Path(source).name, "path": str(target), "kind": "video",
                    "duration": 1, "width": 320, "height": 180, "has_audio": True}
        with patch("local_editor.media_engine.import_media", side_effect=fake_import):
            status, uploaded, _ = self.request(endpoint + quote("口播.mp4"), raw=b"media-bytes", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(uploaded["media"][0]["name"], "口播.mp4")
        self.assertEqual(self.request(uploaded["media"][0]["url"])[1], b"media-bytes")
        self.assertEqual(list(self.server.service.uploads.iterdir()), [])

    def test_caption_import_text_cut_plan_and_undo(self):
        project = self.fixture_media(self.project())
        base = f"/api/projects/{project['id']}"
        _, project, _ = self.request(base + "/captions/import", {"expected_version": project["version"], "media_id": "sample",
                       "format": "srt", "text": "1\n00:00:01,000 --> 00:00:02,000\n這句要剪除\n\n2\n00:00:03,000 --> 00:00:04,000\n保留字幕\n"})
        version = project["version"]
        status, plan, _ = self.request(base + "/plans", {"expected_version": version, "candidates": [
            {"media_id": "sample", "start": 1, "end": 2, "reason": "刪文剪片"}]})
        self.assertEqual(status, 200)
        status, updated, _ = self.request(base + "/smart-cut/apply", {"expected_version": version,
                          "plan_id": plan["id"], "candidate_ids": [plan["candidates"][0]["id"]]})
        self.assertEqual(status, 200)
        self.assertEqual(updated["duration"], 9)
        exported = self.request(base + "/captions/export?format=srt")[1]["text"]
        self.assertNotIn("這句要剪除", exported)
        self.assertIn("00:00:02,000 --> 00:00:03,000", exported)
        status, restored, _ = self.request(base + "/edit", {"expected_version": updated["version"], "action": "undo", "params": {}})
        self.assertEqual((status, restored["duration"]), (200, 10))

    def test_stale_transcription_job_does_not_overwrite_new_edit(self):
        project = self.fixture_media(self.project())
        started, release = threading.Event(), threading.Event()

        def fake_transcription(*args):
            started.set()
            release.wait(3)
            return [{"start": 1, "end": 2, "text": "遲到字幕"}]

        with patch("local_editor.media_engine.transcription", side_effect=fake_transcription):
            status, job, _ = self.request(f"/api/projects/{project['id']}/transcribe", {
                "expected_version": project["version"], "media_id": "sample"})
            self.assertEqual(status, 200)
            self.assertTrue(started.wait(2))
            self.request(f"/api/projects/{project['id']}/edit", {"expected_version": project["version"],
                         "action": "rename", "params": {"name": "使用者正在編輯"}})
            release.set()
            result = self.wait_job(job["id"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "version_conflict")
        self.assertEqual(self.server.service.get_project(project["id"])["captions"], [])

    def test_smart_cut_filters_candidates_outside_trimmed_timeline(self):
        project = self.fixture_media(self.project())
        project = self.server.service.edit(project["id"], {"expected_version": project["version"], "action": "clip_update",
                   "params": {"clip_id": project["clips"][0]["id"], "changes": {"start": 2, "end": 8}}})
        with patch("local_editor.media_engine.analyze_speech", return_value={"candidates": [
                {"start": 0, "end": 1}, {"start": 3, "end": 4}], "warnings": []}):
            status, job, _ = self.request(f"/api/projects/{project['id']}/smart-cut", {
                "expected_version": project["version"], "media_id": "sample"})
            self.assertEqual(status, 200)
            result = self.wait_job(job["id"])
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(len(result["result"]["plan"]["candidates"]), 1)
        self.assertEqual(result["result"]["plan"]["removed_duration"], 1)

    def test_failed_import_reclaims_only_new_managed_copies(self):
        project = self.project()
        source = Path(self.directory.name) / "original.mp4"
        source.write_bytes(b"source must stay")
        imported_path = self.server.service.assets / "newmedia.mp4"
        thumbnail = self.server.service.assets / "newmedia.thumb.jpg"

        def delayed_import(path, asset_dir):
            shutil.copy2(path, imported_path)
            thumbnail.write_bytes(b"thumbnail")
            self.server.service.edit(project["id"], {"expected_version": project["version"],
                "action": "rename", "params": {"name": "Concurrent edit"}})
            return {"id": "newmedia", "name": source.name, "path": str(imported_path), "thumbnail": str(thumbnail),
                    "kind": "video", "duration": 1, "width": 320, "height": 180, "has_audio": True}
        with patch("local_editor.media_engine.import_media", side_effect=delayed_import):
            status, result, _ = self.request(f"/api/projects/{project['id']}/media/import", {
                "expected_version": project["version"], "path": str(source)})
        self.assertEqual(status, 409)
        self.assertEqual(result["error"]["code"], "version_conflict")
        self.assertEqual(source.read_bytes(), b"source must stay")
        self.assertFalse(imported_path.exists())
        self.assertFalse(thumbnail.exists())

    def test_export_snapshot_and_registered_download(self):
        project = self.fixture_media(self.project())

        def fake_render(snapshot, directory, options, progress_callback):
            path = Path(directory) / "output.mp4"
            path.write_bytes(b"rendered")
            progress_callback({"progress": .5, "message": "渲染中"})
            return {"path": str(path)}
        with patch("local_editor.media_engine.render_project", side_effect=fake_render):
            status, job, _ = self.request(f"/api/projects/{project['id']}/export", {"expected_version": project["version"]})
            self.assertEqual(status, 200)
            result = self.wait_job(job["id"])
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(self.request(result["result"]["url"])[1], b"rendered")
        self.assertEqual(self.request(f"/api/exports/{job['id']}/other.mp4")[0], 404)

    def test_real_stdio_subprocess_shares_live_api_and_validates_protocol(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "editor_create_project", "arguments": {"name": "Agent 建立專案"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "ping"},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "editor_edit", "arguments": {"project_id": "x", "action": "undo", "params": {}}}},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "editor_get_project", "arguments": {"project_id": "missing"}}},
        ]
        completed = subprocess.run([sys.executable, "-m", "local_editor", "mcp", "--url", self.url],
                                   input="".join(json.dumps(m, ensure_ascii=False) + "\n" for m in messages),
                                   encoding="utf-8", capture_output=True, timeout=15,
                                   cwd=Path(__file__).resolve().parent.parent)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(responses), 6)  # Notifications have no response.
        self.assertEqual(responses[0]["result"]["protocolVersion"], "2025-11-25")
        tool_names = {t["name"] for t in responses[1]["result"]["tools"]}
        self.assertTrue({"editor_prepare_smart_cut", "editor_apply_smart_cut", "editor_prepare_plan"} <= tool_names)
        created = responses[2]["result"]["structuredContent"]
        self.assertEqual(self.request(f"/api/projects/{created['id']}")[1]["name"], "Agent 建立專案")
        self.assertEqual(responses[4]["error"]["code"], -32602)
        self.assertTrue(responses[5]["result"]["isError"])
        self.assertEqual(self.request("/api/events")[1]["events"][0]["actor"], "agent")


class MCPAndQueueTest(unittest.TestCase):
    def test_stdio_parse_errors_and_initialization_guard(self):
        source = io.BytesIO(b'not-json\n{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n')
        output = io.BytesIO()
        run_stdio("http://127.0.0.1:8321", source, output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(responses[0]["error"]["code"], -32700)
        self.assertEqual(responses[1]["error"]["code"], -32002)
        for url in ("https://127.0.0.1:8321", "http://evil.invalid:8321", "http://127.0.0.1:8321/anything"):
            with self.assertRaises(ValueError):
                HTTPBridge(url)

    def test_bounded_job_queue_and_restart_interruption(self):
        with tempfile.TemporaryDirectory() as directory:
            service = EditorService(directory, workers=1, max_jobs=1)
            release = threading.Event()
            try:
                job = service._enqueue("test", "project", 1, lambda *args: release.wait(3))
                with self.assertRaises(ServiceError) as raised:
                    service._enqueue("test", "project", 1, lambda *args: None)
                self.assertEqual(raised.exception.code, "queue_full")
                release.set()
            finally:
                service.close()
            interrupted = {"id": "interrupted", "kind": "test", "project_id": "project", "project_version": 1,
                           "status": "running", "created_at": 0}
            (Path(directory) / "jobs" / "interrupted.json").write_text(json.dumps(interrupted), encoding="utf-8")
            restored = EditorService(directory)
            try:
                self.assertEqual(restored.job_status(job["id"])["status"], "succeeded")
                self.assertEqual(restored.job_status("interrupted")["error"]["code"], "interrupted")
            finally:
                restored.close()

    def test_large_integer_validation_keeps_stdio_alive(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "editor_prepare_smart_cut",
                "arguments": {"project_id": "p", "expected_version": 1, "media_id": "m", "options": {"threshold_db": 10 ** 500}}}},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
        ]
        source = io.BytesIO("".join(json.dumps(m) + "\n" for m in messages).encode())
        target = io.BytesIO()
        self.assertEqual(run_stdio("http://127.0.0.1:8321", source, target), 0)
        responses = [json.loads(line) for line in target.getvalue().splitlines()]
        self.assertEqual(responses[1]["error"]["code"], -32602)
        self.assertEqual(responses[2]["result"], {})

    def test_job_persistence_failure_releases_queue_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            service = EditorService(directory, workers=1, max_jobs=1)
            original_save = service._save_job
            count = 0

            def fail_worker_save(job):
                nonlocal count
                count += 1
                if count > 1:
                    raise OSError("disk full")
                original_save(job)
            try:
                with patch.object(service, "_save_job", side_effect=fail_worker_save):
                    job = service._enqueue("test", "project", 1, lambda *args: None)
                    deadline = time.monotonic() + 2
                    while service.job_status(job["id"])["status"] != "failed" and time.monotonic() < deadline:
                        threading.Event().wait(.01)
                self.assertEqual(service.job_status(job["id"])["status"], "failed")
                # First worker's semaphore release follows its final memory update.
                service._executor.submit(lambda: None).result(timeout=2)
                second = service._enqueue("test", "project", 1, lambda *args: {"ok": True})
                self.assertNotEqual(second["id"], job["id"])
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
