"""Context and preview acceptance without media processes or user project writes."""
import copy
import json
import tempfile
import unittest
from unittest.mock import patch

from local_editor.observation_service import _public
from local_editor.service import EditorService


class ContextWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = EditorService(self.tmp.name)
        self.addCleanup(self.service.close)
        self.project = self.service.create_project({"name": "情境驗收"})
        self.project = self.service.store.mutate(self.project["id"], self.project["version"], "media_add", {
            "media": {"id": "media", "name": "範例.mp4", "path": str(self.service.assets / "private.mp4"),
                      "kind": "video", "duration": 12, "width": 320, "height": 180, "has_audio": True}})
        self.project = self.service.store.mutate(self.project["id"], self.project["version"], "clip_add", {
            "clip": {"id": "clip", "media_id": "media"}})
        self.other = self.service.create_project({"name": "另一個專案"})

    def context(self, client="tab-a", project=None, *, at=100., **changes):
        project = project or self.project
        data = {"client_id": client, "sequence": 1, "project_id": project["id"],
                "project_version": project["version"], "focused": True, "playhead": 2., **changes}
        with patch("local_editor.observation_service.time.time", return_value=at):
            return self.service.update_context(data)

    def read(self, *, at=110., **request):
        with patch("local_editor.observation_service.time.time", return_value=at):
            return self.service.get_context(request)

    def proposal(self):
        return self.service.prepare_edit(self.project["id"], {"expected_version": self.project["version"],
            "intent": "拆段後檢查銜接", "operations": [
                {"action": "clip_split", "params": {"clip_id": "clip", "at": 5}},
                {"action": "brief_update", "params": {"goal": "清楚展示操作", "must_keep": ["確認步驟"]}}]})

    def test_focused_tab_wins_and_explicit_client_selects_other_tab(self):
        self.context(at=100)
        self.context("tab-b", self.other, at=105, focused=False)
        result = self.read()
        self.assertEqual(result["ui"]["client_id"], "tab-a")
        self.assertEqual(result["project"]["id"], self.project["id"])
        self.assertFalse(result["ambiguous"])
        explicit = self.read(client_id="tab-b")
        self.assertEqual(explicit["project"]["id"], self.other["id"])

    def test_multiple_focused_projects_report_ambiguity(self):
        self.context(at=100)
        self.context("tab-b", self.other, at=105)
        result = self.read()
        self.assertTrue(result["ambiguous"])
        self.assertEqual(result["ui"]["client_id"], "tab-b")
        self.assertFalse(self.read(project_id=self.project["id"])["ambiguous"])

    def test_out_of_order_heartbeat_preserves_selection_and_playhead(self):
        self.context(sequence=5, playhead=4, selected={"type": "clip", "id": "clip"}, range={"start": 3, "end": 6})
        result = self.context(at=105, sequence=4, playhead=9, selected=None)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "out_of_order")
        current = self.read()["ui"]
        self.assertEqual(current["playhead"], 4)
        self.assertEqual(current["selected"]["id"], "clip")
        self.assertEqual(current["range"], {"start": 3, "end": 6})

    def test_expired_sessions_never_infer_active_project(self):
        self.context(at=100)
        result = self.read(at=161)
        self.assertEqual(result["context_status"], "no_live_ui")
        self.assertIsNone(result["project"])
        self.assertIsNone(result["ui"])
        self.assertTrue(result["sessions"][0]["stale"])
        explicit = self.read(at=161, project_id=self.project["id"])
        self.assertEqual(explicit["project"]["id"], self.project["id"])
        self.assertIsNone(explicit["ui"])

    def test_stale_ui_version_is_visible_and_does_not_apply_old_range(self):
        self.context(range={"start": 2, "end": 4})
        self.project = self.service.edit(self.project["id"], {"expected_version": self.project["version"],
            "action": "rename", "params": {"name": "Agent 新版本"}})
        result = self.read()
        self.assertFalse(result["ui"]["version_matches"])
        self.assertNotIn("selection_structure", result)
        self.assertEqual(result["project"]["version"], self.project["version"])

    def test_active_selection_exposes_exact_structure_without_private_paths(self):
        self.context(selected={"type": "clip", "id": "clip"}, range={"start": 2, "end": 4})
        result = self.read()
        self.assertEqual(result["selection_structure"]["placements"][0]["source_range"], {"start": 2, "end": 4})
        self.assertNotIn("private.mp4", json.dumps(result))
        self.assertNotIn(str(self.service.root), json.dumps(result))
        redacted = _public({"path": "private", "nested": [{"model_path": "secret", "_snapshot": {"x": 1},
                              "id": "evidence", "url": "/api/evidence/id/files/frame"}], "cache_key": "internal"})
        self.assertEqual(redacted, {"nested": [{"id": "evidence", "url": "/api/evidence/id/files/frame"}]})

    def test_invalid_selection_is_cleared_and_invalid_time_data_rejected(self):
        self.context(selected={"type": "clip", "id": "deleted"})
        self.assertIsNone(self.read()["ui"]["selected"])
        for fields in ({"range": {"start": 0, "end": 20}}, {"playhead": float("nan")},
                       {"project_version": True}, {"sequence": -1}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.context(at=105, **fields)

    def test_restart_preserves_projects_and_proposals_but_not_ui_focus(self):
        self.context()
        proposal = self.proposal()
        self.service.close()
        restarted = EditorService(self.tmp.name)
        self.addCleanup(restarted.close)
        self.assertEqual(restarted.get_context()["context_status"], "no_live_ui")
        result = restarted.get_context({"project_id": self.project["id"]})
        self.assertEqual(result["proposals"][0]["edit_id"], proposal["edit_id"])
        self.assertTrue(result["proposals"][0]["can_apply"])
        self.assertEqual(result["brief"], {})

    def test_preview_uses_persisted_proposal_while_saved_project_remains_unchanged(self):
        proposal = self.proposal()
        base = self.project["version"]
        before = self.service._observation_project(self.project["id"], {
            "expected_version": base, "edit_id": proposal["edit_id"], "preview_side": "before"})
        after = self.service._observation_project(self.project["id"], {
            "expected_version": base, "edit_id": proposal["edit_id"], "preview_side": "after"})
        self.assertEqual(len(before["clips"]), 1)
        self.assertEqual(len(after["clips"]), 2)
        self.assertEqual(before["version"], base)
        self.assertEqual(after["version"], base + 1)
        self.assertEqual(after["brief"]["goal"], "清楚展示操作")
        self.assertEqual(self.service.get_project(self.project["id"])["version"], base)
        applied = self.service.apply_edit(self.project["id"], {"expected_version": base, "edit_id": proposal["edit_id"]})
        self.assertEqual(applied["clips"], after["clips"])
        self.assertTrue(applied["undo_receipt"]["one_step"])
        self.assertEqual(applied["verification"]["audiovisual"]["naturalness"], "unchecked")
        with self.assertRaises(ValueError):
            self.service._observation_project(self.project["id"], {
                "expected_version": applied["version"], "edit_id": proposal["edit_id"]})

    def test_review_of_before_evidence_cannot_count_towards_after_preview(self):
        proposal = self.proposal()
        evidence_id = "before_evidence"
        folder = self.service.evidence_root / evidence_id
        folder.mkdir()
        frame = folder / "frame.jpg"
        frame.write_bytes(b"test fixture: review association only")
        self.service._register_evidence({"project_id": self.project["id"], "project_version": self.project["version"],
            "edit_id": proposal["edit_id"], "preview_side": "before", "time_space": "timeline", "range": {"start": 0, "end": 2},
            "files": [{"id": "frame", "path": str(frame), "kind": "image", "mime_type": "image/jpeg"}]}, evidence_id, folder, "test-cache")
        data = {"expected_version": self.project["version"], "edit_id": proposal["edit_id"], "evidence_id": evidence_id,
                "file_ids": ["frame"], "checks": ["visual"], "outcome": "pass", "reviewer": "test-reviewer", "notes": "僅驗證證據與提案側關聯"}
        with self.assertRaises(ValueError):
            self.service.record_review(self.project["id"], data)
        record = self.service.record_review(self.project["id"], {**data, "preview_side": "before"})
        self.assertEqual(record["preview_side"], "before")
        after_report = self.service.verify_edit(self.project["id"], {"expected_version": self.project["version"], "edit_id": proposal["edit_id"]})
        before_report = self.service.verify_edit(self.project["id"], {"expected_version": self.project["version"], "edit_id": proposal["edit_id"], "preview_side": "before"})
        self.assertEqual(after_report["review_records"], [])
        self.assertEqual(len(before_report["review_records"]), 1)


if __name__ == "__main__":
    unittest.main()
