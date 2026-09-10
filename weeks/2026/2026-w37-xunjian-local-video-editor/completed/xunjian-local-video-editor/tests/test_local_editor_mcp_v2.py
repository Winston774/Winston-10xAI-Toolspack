"""Live v2 protocol tests: formal observation, atomic edits and native evidence.

Binary fixtures test the transport, not media rendering. Real FFmpeg evidence
generation is covered separately by test_local_editor_evidence.py.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from local_editor.contracts import validate_action, validate_request
from local_editor.mcp import HTTPBridge, MAX_EVIDENCE_BYTES, TOOLS, ToolError, _compact
from local_editor.server import make_server


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jMZkAAAAASUVORK5CYII=")


class AgentProtocolV2Test(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.server = make_server(self.directory.name, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.bridge = HTTPBridge(f"http://127.0.0.1:{self.server.server_port}")
        self.service = self.server.service
        self.project = self.service.create_project({"name": "Agent 契約驗收"})
        path = self.service.assets / "fixture.mp4"
        path.write_bytes(b"transport-only-fixture")
        self.project = self.service.store.mutate(self.project["id"], self.project["version"], "media_add", {
            "media": {"id": "media-one", "name": "fixture.mp4", "path": str(path), "kind": "video",
                      "duration": 6, "width": 320, "height": 180, "has_audio": True}})
        self.project = self.service.store.mutate(self.project["id"], self.project["version"], "clip_add", {"media_id": "media-one"})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.service.close()
        self.thread.join(timeout=3)
        self.directory.cleanup()

    def evidence(self):
        folder = self.service.evidence_root / "fixture-evidence"
        folder.mkdir()
        (folder / "frame.png").write_bytes(PNG)
        with wave.open(str(folder / "audio.wav"), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(8000)
            target.writeframes(b"\0\0" * 800)
        (folder / "clip.mp4").write_bytes(b"registered-video-transport")
        manifest = {"project_id": self.project["id"], "project_version": self.project["version"],
                    "time_space": "timeline", "range": {"start": 0, "end": .1},
                    "coverage": {"complete_watch": False}, "unknowns": {"speech": "not reviewed"},
                    "files": [{"id": "frame-1", "kind": "image", "path": str(folder / "frame.png"), "mime_type": "image/png"},
                              {"id": "audio-1", "kind": "audio", "path": str(folder / "audio.wav"), "mime_type": "audio/wav"},
                              {"id": "video-1", "kind": "video", "path": str(folder / "clip.mp4"), "mime_type": "video/mp4"}]}
        return self.service._register_evidence(manifest, folder.name, folder, "transport-test")

    def stdio(self, messages):
        initialization = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "fresh-agent", "version": "2"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"}]
        result = subprocess.run([sys.executable, "-B", "-m", "local_editor", "mcp", "--url", self.bridge.url],
            input="".join(json.dumps(message) + "\n" for message in initialization + messages),
            capture_output=True, encoding="utf-8", timeout=20, cwd=Path(__file__).resolve().parent.parent)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_stdio_native_image_audio_and_registered_video_resource(self):
        manifest = self.evidence()
        responses = self.stdio([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "editor_read_evidence", "arguments": {"evidence_id": manifest["evidence_id"]}}},
            {"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "evidence://fixture-evidence/video-1"}},
            {"jsonrpc": "2.0", "id": 3, "method": "resources/list"}])
        self.assertIn("resources", responses[0]["result"]["capabilities"])
        evidence = responses[1]["result"]
        self.assertFalse(evidence["isError"], evidence)
        self.assertEqual([c["type"] for c in evidence["content"]], ["text", "image", "audio", "resource_link"])
        self.assertEqual(base64.b64decode(evidence["content"][1]["data"]), PNG)
        self.assertTrue(base64.b64decode(evidence["content"][2]["data"]).startswith(b"RIFF"))
        summary = evidence["structuredContent"]
        self.assertEqual(summary["included_file_ids"], ["frame-1", "audio-1"])
        self.assertEqual(summary["linked_file_ids"], ["video-1"])
        self.assertNotIn("data", json.dumps(summary))
        self.assertNotIn("path", json.dumps(summary))
        self.assertEqual(base64.b64decode(responses[2]["result"]["contents"][0]["blob"]), b"registered-video-transport")
        self.assertEqual(len(responses[3]["result"]["resources"]), 3)
        context = self.bridge.call("editor_get_context", {})
        agent = next(agent for agent in context["agents"] if agent["name"] == "fresh-agent")
        self.assertEqual(agent["status"], "inactive")  # EOF explicitly disconnects.

    def test_context_reports_current_ui_without_browser_guessing(self):
        self.assertEqual(self.bridge.call("editor_get_context", {})["context_status"], "no_live_ui")
        self.bridge.request("/api/context", {"client_id": "workbench-tab", "project_id": self.project["id"],
            "project_version": self.project["version"], "selected": {"type": "clip", "id": self.project["clips"][0]["id"]},
            "playhead": 2.2, "range": {"start": 1, "end": 3}, "focused": True, "sequence": 1,
            "mode": "smart", "media_id": "media-one"})
        context = self.bridge.call("editor_get_context", {})
        self.assertEqual(context["project"]["id"], self.project["id"])
        self.assertEqual(context["ui"]["playhead"], 2.2)
        self.assertEqual(context["ui"]["selected"]["id"], self.project["clips"][0]["id"])
        self.assertTrue(context["ui"]["version_matches"])
        self.assertIn("OCR", context["capabilities"]["unavailable"])
        self.assertEqual(len(TOOLS), 25)

    def test_batch_edit_exact_diff_apply_receipt_and_stale_rejection(self):
        arguments = {"project_id": self.project["id"], "expected_version": self.project["version"],
                     "intent": "把片尾縮短一秒並記錄方向", "operations": [
            {"action": "clip_update", "params": {"clip_id": self.project["clips"][0]["id"], "changes": {"end": 5}}},
            {"action": "brief_update", "params": {"goal": "保留重要示範", "must_keep": ["示範步驟"]}}]}
        proposal = self.bridge.call("editor_prepare_edit", arguments)
        self.assertEqual(proposal["before"]["duration"], 6)
        self.assertEqual(proposal["after"]["duration"], 5)
        self.assertEqual(self.service.get_project(self.project["id"])["duration"], 6)
        self.assertEqual(self.bridge.call("editor_get_edit", {"project_id": self.project["id"], "edit_id": proposal["edit_id"]})["id"], proposal["id"])
        result = self.bridge.call("editor_apply_edit", {"project_id": self.project["id"],
            "expected_version": self.project["version"], "edit_id": proposal["edit_id"]})
        self.assertEqual(result["duration"], 5)
        self.assertTrue(result["undo_receipt"]["one_step"])
        self.assertIn("verification", result)
        self.assertEqual(result["brief"]["goal"], "保留重要示範")
        with self.assertRaises(ToolError) as raised:
            self.bridge.call("editor_apply_edit", {"project_id": self.project["id"],
                "expected_version": self.project["version"], "edit_id": proposal["edit_id"]})
        self.assertEqual(raised.exception.code, "version_conflict")

    def test_caption_update_compact_result_keeps_alignment_warning(self):
        current = self.service.store.mutate(self.project["id"], self.project["version"], "captions_set", {
            "media_id": "media-one", "captions": [{"id": "caption-one", "start": 0, "end": 1, "text": "測試",
                "words": [{"text": "測試", "start": .1, "end": .9}]}]})
        result = self.bridge.call("editor_edit", {"project_id": current["id"], "expected_version": current["version"],
            "action": "caption_update", "params": {"caption_id": "caption-one", "changes": {"text": "修改"}}})
        self.assertTrue(result["warnings"])
        # No metadata path or entire transcript is needed to see this edit's consequence.
        self.assertNotIn("captions", result)

    def test_caption_readback_roundtrip_preserves_words_and_recomputes_status(self):
        current = self.service.store.mutate(self.project["id"], self.project["version"], "captions_set", {
            "media_id": "media-one", "captions": [{"id": "caption-one", "start": 0, "end": 1, "text": "測試",
                "words": [{"text": "測試", "start": .1, "end": .9}]}]})
        self.assertEqual(current["captions"][0]["alignment_status"], "valid")
        result = self.bridge.call("editor_edit", {"project_id": current["id"], "expected_version": current["version"],
            "action": "captions_set", "params": {"media_id": "media-one", "captions": current["captions"]}})
        saved = self.service.get_project(current["id"])
        self.assertEqual(saved["version"], result["version"])
        self.assertEqual(saved["captions"][0]["words"], current["captions"][0]["words"])
        self.assertEqual(saved["captions"][0]["alignment_status"], "valid")
        with self.assertRaises(ValueError):
            validate_action("caption_update", {"caption_id": "caption-one", "changes": {"alignment_status": "valid"}})

    def test_compaction_preserves_bounded_analysis_waveform(self):
        result = _compact({"media": [{"id": "m", "kind": "video", "duration": 6, "waveform": [1, 2, 3]}],
                           "analysis": {"audio": {"waveform": {"rms": [.1, .2], "bucket_seconds": .1}}}})
        self.assertNotIn("waveform", result["media"][0])
        self.assertEqual(result["analysis"]["audio"]["waveform"]["rms"], [.1, .2])

    def test_invalid_tool_params_do_not_touch_state_or_kill_stdio(self):
        bad = {"project_id": self.project["id"], "expected_version": self.project["version"],
               "action": "clip_update", "params": {"clip_id": self.project["clips"][0]["id"], "changes": {"speeed": 2}}}
        responses = self.stdio([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "editor_edit", "arguments": bad}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "editor_inspect_range", "arguments": {
                "project_id": self.project["id"], "expected_version": self.project["version"],
                "time_space": "timeline", "range": {"start": 0, "end": 3}, "max_frames": 9}}},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"}])
        self.assertEqual(responses[1]["error"]["code"], -32602)
        self.assertEqual(responses[2]["error"]["code"], -32602)
        self.assertEqual(responses[3]["result"], {})
        self.assertEqual(self.service.get_project(self.project["id"])["version"], self.project["version"])
        with self.assertRaises(ToolError):
            self.bridge.request(f"/api/projects/{self.project['id']}/edit", {k: v for k, v in bad.items() if k != "project_id"})

    def test_evidence_rejects_arbitrary_urls_unknown_ids_and_oversize(self):
        manifest = self.evidence()
        with self.assertRaises(ToolError):
            self.bridge.read_evidence(manifest["evidence_id"], ["unknown"])
        for uri in ("file:///C:/secret.txt", "evidence://fixture-evidence/../secret", "https://evil.invalid/picture"):
            with self.assertRaises(ToolError):
                self.bridge.read_resource(uri)
        manifest["files"][0]["url"] = "/api/exports/x/secret.png"
        with patch.object(self.bridge, "request", return_value=manifest):
            with self.assertRaises(ToolError) as raised:
                self.bridge.read_evidence(manifest["evidence_id"])
            self.assertEqual(raised.exception.code, "invalid_evidence")
        frame = self.service.evidence_root / "fixture-evidence" / "frame.png"
        with frame.open("wb") as target:
            target.truncate(MAX_EVIDENCE_BYTES + 1)
        with self.assertRaises(ToolError) as raised:
            self.bridge.read_evidence("fixture-evidence", ["frame-1"])
        self.assertEqual(raised.exception.code, "evidence_too_large")

    def test_registered_review_requires_matching_evidence_and_exact_files(self):
        evidence = self.evidence()
        base = {"project_id": self.project["id"], "expected_version": self.project["version"],
                "evidence_id": evidence["evidence_id"], "file_ids": ["frame-1"], "checks": ["visual"],
                "reviewer": "測試複核者", "outcome": "pass", "notes": "僅此測試影格的傳輸檢查。"}
        review = self.bridge.call("editor_record_review", base)
        self.assertEqual(review["file_ids"], ["frame-1"])
        report = self.bridge.call("editor_verify_edit", {"project_id": self.project["id"], "expected_version": self.project["version"]})
        self.assertEqual(report["audiovisual_review"]["status"], "partially_reviewed")
        self.assertEqual(report["review_records"][0]["basis"], "reviewer_self_report")
        with self.assertRaises(ToolError):
            self.bridge.call("editor_record_review", {**base, "checks": ["audio"]})

    def test_observation_routes_long_poll_and_revision_binding(self):
        def capture(snapshot, request, folder, progress_callback=None):
            if request.get("scan_black_frames"):
                self.assertEqual(request["sampling"]["strategy"], "cut_boundaries")
            path = folder / "frame.png"
            path.write_bytes(PNG)
            return {"range": request["range"], "time_space": request["time_space"],
                    "coverage": {"sampled": True}, "unknowns": {"visual_semantics": "unknown"},
                    "files": [{"id": "observed-frame", "kind": "image", "path": str(path), "mime_type": "image/png"}]}
        arguments = {"project_id": self.project["id"], "expected_version": self.project["version"],
                     "time_space": "timeline", "range": {"start": 1, "end": 2}}
        for name, method in (("editor_inspect_range", "inspect_media"), ("editor_analyze_range", "analyze_media")):
            with self.subTest(name=name), patch("local_editor.evidence." + method, side_effect=capture):
                extra = {"sampling": {"strategy": "cut_boundaries"}, "scan_black_frames": True} if name == "editor_inspect_range" else {}
                job = self.bridge.call(name, {**arguments, **extra})
                result = self.bridge.call("editor_job_status", {"job_id": job["id"], "wait_ms": 1000})
                self.assertEqual(result["status"], "succeeded", result)
                manifest = result["result"]["evidence"]
                self.assertEqual(manifest["project_version"], self.project["version"])
                self.assertNotIn("path", manifest["files"][0])
                native = self.bridge.call("editor_read_evidence", {"evidence_id": manifest["evidence_id"]})
                self.assertEqual(native.content[0]["type"], "image")
        self.service.edit(self.project["id"], {"expected_version": self.project["version"], "action": "rename", "params": {"name": "新版本"}})
        with self.assertRaises(ToolError) as raised:
            self.bridge.call("editor_inspect_range", arguments)
        self.assertEqual(raised.exception.code, "version_conflict")

    def test_contract_cross_field_limits_and_transaction_action_allowlist(self):
        for operation in ("inspect", "analyze"):
            with self.assertRaises(ValueError):
                validate_request(operation, {"expected_version": 1, "time_space": "timeline", "range": {"start": 0, "end": 31}})
            with self.assertRaises(ValueError):
                validate_request(operation, {"expected_version": 1, "time_space": "source", "range": {"start": 0, "end": 1}})
        for action in ("undo", "redo", "media_add"):
            with self.assertRaises(ValueError):
                validate_action(action, {}, batch=True)
        validate_action("brief_update", {"target_duration": None})
        validate_action("smart_cut_apply", {"plan_id": "p", "candidate_ids": ["c"]}, batch=True)
        with self.assertRaises(ValueError):
            validate_request("verify", {"expected_version": 1, "preview_side": "before"})
        with self.assertRaises(ValueError):
            validate_action("clip_update", {"clip_id": "c", "changes": {"speed": float("nan")}})


if __name__ == "__main__":
    unittest.main()
