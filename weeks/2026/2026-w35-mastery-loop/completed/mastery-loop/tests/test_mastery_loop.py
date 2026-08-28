from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ui = load_module("mastery_click_ui", ROOT / "scripts" / "click_choice_ui.py")


def knowledge_spec(question_id: str = "audit-q1", mode: str = "audit") -> dict:
    data = {
        "schema_version": 2,
        "question_id": question_id,
        "kind": "knowledge",
        "mode": mode,
        "concept_id": "handoff-contract",
        "knowledge_kernel_id": "handoff.explicit-contract",
        "scenario_id": "youtube-facebook-pipeline",
        "core_proposition": "A handoff requires explicit inputs, outputs, validation, and failure behavior.",
        "scenario_context": "A workflow turns YouTube subtitles and a thumbnail into a Facebook post.",
        "question_family": "application",
        "title": "交接缺少影片 ID",
        "prompt": "字幕已回傳，但來源影片 ID 缺失。下一個代理應該怎麼做？",
        "options": [
            {
                "id": "stop-and-validate",
                "label": "停止並要求補齊必要欄位",
                "description": "先驗證交接契約。",
                "explanation": "影片 ID 是內容溯源與縮圖取得的必要欄位；缺少時停止可避免錯誤跨代理擴散。",
                "misconception_tag": "",
            },
            {
                "id": "guess-id",
                "label": "從標題猜測影片 ID",
                "description": "先讓流程繼續。",
                "explanation": "標題無法唯一定位影片，猜測會破壞溯源，也可能擷取到錯誤圖片。",
                "misconception_tag": "implicit-handoff-data",
            },
            {
                "id": "skip-image",
                "label": "省略圖片直接發布文字",
                "description": "避免流程阻塞。",
                "explanation": "驗收條件要求文字與縮圖同時交付，省略圖片會形成不完整成果。",
                "misconception_tag": "partial-output-is-complete",
            },
        ],
        "correct_option_ids": ["stop-and-validate"],
    }
    if mode == "review":
        data["review_of"] = "audit-q1"
        data["question_family"] = "sequence"
        data["prompt"] = "同一條工作流發現來源 ID 缺失，請選出可靠的處理順序。"
        data["options"] = [
            {
                "id": "new-guess-sequence",
                "label": "推測來源、產生縮圖、最後驗證",
                "description": "先追求流程完成。",
                "explanation": "驗證被放到最後，錯誤資料會先流入後續階段。",
                "misconception_tag": "implicit-handoff-data",
            },
            {
                "id": "new-validate-sequence",
                "label": "停止交接、補齊來源、驗證後續跑",
                "description": "把契約驗證放在交接邊界。",
                "explanation": "先阻止不完整輸出離開交接邊界，再補值與驗證，能保持溯源和縮圖正確性。",
                "misconception_tag": "",
            },
            {
                "id": "new-partial-sequence",
                "label": "先發布文字、補齊來源、再補圖片",
                "description": "把圖片延後處理。",
                "explanation": "發布發生在完整驗收之前，最終結果會在一段時間內違反交付契約。",
                "misconception_tag": "partial-output-is-complete",
            },
        ]
        data["correct_option_ids"] = ["new-validate-sequence"]
    return data


class SpecTests(unittest.TestCase):
    def test_version_one_remains_readable(self):
        old = {
            "question_id": "old-q",
            "kind": "knowledge",
            "mode": "audit",
            "title": "Legacy",
            "prompt": "Choose.",
            "options": [
                {"id": "one", "label": "One"},
                {"id": "two", "label": "Two"},
                {"id": "three", "label": "Three"},
            ],
            "correct_option_ids": ["one"],
        }
        self.assertEqual(ui.validate_spec(old)["schema_version"], 1)

    def test_version_two_requires_every_explanation(self):
        data = knowledge_spec()
        del data["options"][1]["explanation"]
        with self.assertRaises(ui.SpecError):
            ui.validate_spec(data)

    def test_unknown_mode_is_rejected(self):
        data = knowledge_spec()
        data["mode"] = "retired-mode"
        with self.assertRaises(ui.SpecError):
            ui.validate_spec(data)

    def test_review_preserves_kernel_but_changes_surface(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "choice-sessions").mkdir()
            (workspace / "review-records").mkdir()
            source = ui.validate_spec(knowledge_spec())
            selected = source["options"][1]
            correct = source["options"][0]
            record = ui.build_review_record(source, selected, correct)
            (workspace / "review-records" / "audit-q1.json").write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8"
            )
            path = workspace / "choice-sessions" / "review-q1.json"
            path.write_text(
                json.dumps(knowledge_spec("review-q1", "review"), ensure_ascii=False),
                encoding="utf-8",
            )
            _, loaded = ui.load_spec(workspace, str(path))
            self.assertEqual(loaded["mode"], "review")

    def test_review_rejects_repeated_family(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "choice-sessions").mkdir()
            (workspace / "review-records").mkdir()
            source = ui.validate_spec(knowledge_spec())
            record = ui.build_review_record(
                source, source["options"][1], source["options"][0]
            )
            (workspace / "review-records" / "audit-q1.json").write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8"
            )
            repeated = knowledge_spec("review-q1", "review")
            repeated["question_family"] = "application"
            path = workspace / "choice-sessions" / "review-q1.json"
            path.write_text(json.dumps(repeated, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ui.SpecError):
                ui.load_spec(workspace, str(path))

    def test_review_rejects_any_reused_option_label(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "choice-sessions").mkdir()
            (workspace / "review-records").mkdir()
            source = ui.validate_spec(knowledge_spec())
            record = ui.build_review_record(
                source, source["options"][1], source["options"][0]
            )
            (workspace / "review-records" / "audit-q1.json").write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8"
            )
            reused = knowledge_spec("review-q1", "review")
            reused["options"][0]["label"] = source["options"][1]["label"]
            path = workspace / "choice-sessions" / "review-q1.json"
            path.write_text(json.dumps(reused, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ui.SpecError):
                ui.load_spec(workspace, str(path))

    def test_answer_persists_conservative_evidence_context(self):
        audit = ui.validate_spec(knowledge_spec())
        audit_answer = ui.build_answer(audit, audit["options"][0])
        self.assertEqual(audit_answer["independence"], "independent")
        self.assertFalse(audit_answer["feedback_exposed"])
        self.assertEqual(audit_answer["feedback_timing"], "immediate_after_commit")

        review = ui.validate_spec(knowledge_spec("review-q1", "review"))
        review_answer = ui.build_answer(review, review["options"][1])
        self.assertEqual(review_answer["independence"], "feedback_exposed")
        self.assertTrue(review_answer["feedback_exposed"])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.spec = ui.validate_spec(knowledge_spec())

    def test_initial_page_hides_answer_data(self):
        browser_options = {
            "opaque-a": self.spec["options"][0],
            "opaque-b": self.spec["options"][1],
            "opaque-c": self.spec["options"][2],
        }
        page = ui.render_question(self.spec, "csrf-value", browser_options)
        self.assertNotIn("stop-and-validate", page)
        self.assertNotIn("implicit-handoff-data", page)
        self.assertNotIn(self.spec["options"][0]["explanation"], page)
        self.assertIn("opaque-a", page)
        self.assertIn("Created by Winston", page)
        self.assertIn("<script>(()=>{", page)

    def test_correct_page_explains_and_can_close(self):
        page = ui.render_feedback(self.spec, "stop-and-validate", "csrf")
        self.assertIn("回答正確", page)
        self.assertIn(self.spec["options"][0]["explanation"], page)
        self.assertIn("可以關閉此頁", page)
        self.assertNotIn("記錄這個錯誤", page)

    def test_wrong_page_explains_both_and_gates_close_copy(self):
        page = ui.render_feedback(self.spec, "guess-id", "csrf")
        self.assertIn(self.spec["options"][1]["explanation"], page)
        self.assertIn(self.spec["options"][0]["explanation"], page)
        self.assertIn("記錄這個錯誤", page)
        self.assertNotIn("可以關閉此頁", page)

    def test_recorded_page_has_close_copy_and_footer(self):
        page = ui.render_review_recorded(self.spec)
        self.assertIn("錯誤已記錄", page)
        self.assertIn("可以關閉此頁", page)
        self.assertIn("Created by Winston", page)


class HttpFlowTests(unittest.TestCase):
    def run_server(self, spec: dict, workspace: Path):
        answer_path = ui.answer_path_for(workspace, spec["question_id"])
        review_path = ui.review_record_path_for(workspace, spec["question_id"])
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), ui.make_handler(spec, answer_path, review_path, "csrf")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, answer_path, review_path

    def get(self, url: str):
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.read().decode("utf-8"), response.headers

    def post(self, url: str, payload: dict):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Choice-Token": "csrf"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.read().decode("utf-8"), response.headers

    def test_correct_answer_returns_feedback_and_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            spec = ui.validate_spec(knowledge_spec("correct-flow"))
            server, thread, answer_path, _ = self.run_server(spec, workspace)
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            page, headers = self.get(url)
            tokens = re.findall(r'data-option-token="([^"]+)"', page)
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
            feedback, _ = self.post(url + "answer", {"option_token": tokens[0]})
            self.assertIn("回答正確", feedback)
            thread.join(timeout=3)
            server.server_close()
            self.assertFalse(thread.is_alive())
            self.assertTrue(answer_path.exists())

    def test_wrong_answer_requires_record_then_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            spec = ui.validate_spec(knowledge_spec("wrong-flow"))
            server, thread, answer_path, review_path = self.run_server(spec, workspace)
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            page, _ = self.get(url)
            tokens = re.findall(r'data-option-token="([^"]+)"', page)
            feedback, _ = self.post(url + "answer", {"option_token": tokens[1]})
            self.assertIn("記錄這個錯誤", feedback)
            self.assertTrue(answer_path.exists())
            self.assertFalse(review_path.exists())
            self.assertTrue(thread.is_alive())
            complete, _ = self.post(url + "record", {})
            self.assertIn("錯誤已記錄", complete)
            thread.join(timeout=3)
            server.server_close()
            self.assertFalse(thread.is_alive())
            self.assertTrue(review_path.exists())
            record = json.loads(review_path.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "due")
            self.assertEqual(record["selected_option"]["id"], "guess-id")


class WorkspaceInitTests(unittest.TestCase):
    def test_default_cycle_and_no_overwrite(self):
        script = ROOT / "scripts" / "init_workspace.py"
        with tempfile.TemporaryDirectory() as directory:
            command = [
                sys.executable,
                str(script),
                "--path",
                directory,
                "--topic",
                "Agent Workflow",
                "--why",
                "Deliver an end-to-end workflow",
            ]
            first = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertIn("CREATE MASTERY.md", first.stdout)
            root = Path(directory)
            self.assertTrue((root / "review-records").is_dir())
            self.assertTrue((root / "mastery-sessions").is_dir())
            mastery = (root / "MASTERY.md").read_text(encoding="utf-8")
            self.assertIn("Mode: audit", mastery)
            (root / "MISSION.md").write_text("keep me", encoding="utf-8")
            second = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertIn("SKIP MISSION.md", second.stdout)
            self.assertEqual((root / "MISSION.md").read_text(encoding="utf-8"), "keep me")


if __name__ == "__main__":
    unittest.main()
