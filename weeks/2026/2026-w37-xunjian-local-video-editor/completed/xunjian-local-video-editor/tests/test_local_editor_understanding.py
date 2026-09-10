"""Acceptance contracts for observations and reversible batch proposals."""
import copy
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from local_editor.core import EditorError, ProjectStore, mapped_captions, project_duration
from local_editor.service import EditorService
from local_editor.understanding import (analyze_structure, cut_boundaries, inspect_structure,
                                        normalize_range, verify_project)


class UnderstandingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ProjectStore(self.tmp.name)
        self.project = self.store.create_project("Agent 可觀察專案")
        self.edit("media_add", media={"id": "media", "name": "示範.mp4", "path": "private/source.mp4",
                                      "kind": "video", "duration": 90, "width": 1920,
                                      "height": 1080, "has_audio": True})
        self.edit("clip_add", clip={"id": "clip", "media_id": "media", "end": 90})

    def edit(self, action, **params):
        self.project = self.store.mutate(self.project["id"], self.project["version"], action, params)
        return self.project

    def propose(self, operations):
        return self.store.prepare_edit(self.project["id"], self.project["version"], operations,
                                       intent="保留示範內容並縮短冗長停頓")

    def aligned_caption(self):
        self.edit("captions_set", media_id="media", captions=[{
            "id": "caption", "start": 0, "end": 6, "text": "保留重要內容",
            "words": [{"text": "保留", "start": 0, "end": 2},
                      {"text": "重要", "start": 2, "end": 4},
                      {"text": "內容", "start": 4, "end": 6}]}])

    def test_batch_preview_and_apply_share_generated_ids_and_single_undo(self):
        before = copy.deepcopy(self.project)
        proposal = self.propose([
            {"action": "clip_split", "params": {"clip_id": "clip", "at": 30}},
            {"action": "title_add", "params": {"text": "重點", "start": 1, "end": 5}},
            {"action": "brief_update", "params": {"goal": "完整保留教學操作", "must_keep": ["設定畫面"]}},
        ])
        self.assertEqual(self.store.get_project(before["id"]), before)
        self.assertNotIn("_after_snapshot", proposal)
        self.assertNotIn("private/source.mp4", json.dumps(proposal))
        preview = self.store.preview_edit(before["id"], proposal["id"])
        self.assertEqual(preview["version"], before["version"] + 1)
        self.assertEqual(len(preview["clips"]), 2)
        self.project = self.store.apply_edit(before["id"], before["version"], proposal["id"])
        self.assertEqual(self.project["clips"], preview["clips"])
        self.assertEqual(self.project["titles"], preview["titles"])
        self.assertEqual(self.project["history"]["undo_count"], before["history"]["undo_count"] + 1)
        receipt = self.store.get_edit(before["id"], proposal["id"])
        self.assertEqual(receipt["status"], "applied")
        self.assertEqual(receipt["undo_ref"], f"{before['id']}:{self.project['version']}")
        self.edit("undo")
        self.assertEqual(self.project["clips"], before["clips"])
        self.assertEqual(self.project["titles"], [])
        self.assertNotIn("brief", self.project)

    def test_failed_batch_has_no_partial_changes_or_proposal(self):
        before = copy.deepcopy(self.project)
        with self.assertRaises(EditorError):
            self.propose([{"action": "rename", "params": {"name": "不能留下"}},
                          {"action": "clip_update", "params": {"clip_id": "clip", "changes": {"speed": 0}}}])
        self.assertEqual(self.store.get_project(before["id"]), before)
        self.assertEqual(self.store.list_edits(before["id"]), [])

    def test_preview_survives_restart_and_stale_apply_cannot_overwrite(self):
        proposal = self.propose([{"action": "clip_split", "params": {"clip_id": "clip", "at": 30}}])
        preview = self.store.preview_edit(self.project["id"], proposal["id"])
        self.store = ProjectStore(self.tmp.name)
        self.assertEqual(self.store.preview_edit(self.project["id"], proposal["id"]), preview)
        self.edit("rename", name="使用者新修改")
        with self.assertRaises(EditorError) as error:
            self.store.apply_edit(self.project["id"], self.project["version"], proposal["id"])
        self.assertEqual(error.exception.code, "version_conflict")
        self.assertFalse(self.store.list_edits(self.project["id"])[0]["can_apply"])
        self.assertEqual(self.store.get_project(self.project["id"])["name"], "使用者新修改")

    def test_duplicate_apply_is_rejected_even_after_undo(self):
        proposal = self.propose([{"action": "rename", "params": {"name": "套用一次"}}])
        self.project = self.store.apply_edit(self.project["id"], self.project["version"], proposal["id"])
        for undo in (False, True):
            if undo:
                self.edit("undo")
            with self.assertRaises(EditorError) as error:
                self.store.apply_edit(self.project["id"], self.project["version"], proposal["id"])
            self.assertEqual(error.exception.code, "edit_already_applied")

    def test_concurrent_apply_allows_one_writer(self):
        proposal = self.propose([{"action": "rename", "params": {"name": "唯一套用"}}])
        def apply():
            try:
                ProjectStore(self.tmp.name).apply_edit(self.project["id"], self.project["version"], proposal["id"])
                return "ok"
            except EditorError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: apply(), range(2)))
        self.assertEqual(sorted(results), ["ok", "version_conflict"])

    def test_batch_rejects_history_import_unknown_and_malformed_actions(self):
        for action in ("undo", "redo", "media_add", "run_shell", []):
            with self.subTest(action=action), self.assertRaises(EditorError):
                self.propose([{"action": action, "params": {}}])

    def test_word_ids_are_stable_and_manual_edit_exposes_alignment_loss(self):
        self.aligned_caption()
        original = copy.deepcopy(self.project["captions"][0])
        self.assertEqual(original["alignment_status"], "valid")
        self.assertEqual(len(set(w["id"] for w in original["words"])), 3)
        reloaded = ProjectStore(self.tmp.name).get_project(self.project["id"])
        self.assertEqual(reloaded["captions"][0]["words"], original["words"])
        proposal = self.propose([{"action": "caption_update", "params": {
            "caption_id": "caption", "changes": {"text": "保留主要內容"}}}])
        self.assertIn("caption_alignment_invalidated", [w["code"] for w in proposal["warnings"]])
        after = self.store.preview_edit(self.project["id"], proposal["id"])["captions"][0]
        self.assertEqual(after["alignment_status"], "stale")
        self.assertNotIn("words", after)
        self.assertEqual(self.project["captions"][0]["words"], original["words"])

    def test_legacy_alignment_migration_is_stable_without_a_revision_write(self):
        self.aligned_caption()
        legacy = copy.deepcopy(self.project)
        legacy.pop("history")
        legacy["captions"][0].pop("alignment_status")
        for word in legacy["captions"][0]["words"]:
            word.pop("id")
        with closing(sqlite3.connect(self.store.db_path)) as connection:
            with connection:
                connection.execute("UPDATE projects SET snapshot=? WHERE id=?", (json.dumps(legacy), legacy["id"]))
        first = self.store.get_project(legacy["id"])
        second = ProjectStore(self.tmp.name).get_project(legacy["id"])
        self.assertEqual(first["version"], legacy["version"])
        self.assertEqual(first["captions"], second["captions"])
        self.assertEqual(first["captions"][0]["alignment_status"], "valid")
        self.assertTrue(all(word["id"] for word in first["captions"][0]["words"]))

    def test_validated_words_can_replace_text_and_timing_in_one_operation(self):
        self.aligned_caption()
        self.edit("caption_update", caption_id="caption", changes={"text": "新內容", "start": 2, "end": 4,
                  "words": [{"id": "reviewed-word", "text": "新內容", "start": 2, "end": 4, "probability": .8}]})
        caption = self.project["captions"][0]
        self.assertEqual(caption["alignment_status"], "valid")
        self.assertEqual(caption["words"][0]["id"], "reviewed-word")
        before = copy.deepcopy(self.project)
        with self.assertRaises(EditorError):
            self.edit("caption_update", caption_id="caption", changes={
                "words": [{"text": "新內容", "start": 1, "end": 6}]})
        self.assertEqual(self.store.get_project(before["id"]), before)

    def test_source_and_timeline_inspection_map_speed_duplicates_and_layers(self):
        self.aligned_caption()
        self.edit("clip_update", clip_id="clip", changes={"start": 2, "end": 6, "offset": 4, "speed": 2})
        self.edit("clip_add", clip={"id": "overlay", "media_id": "media", "track": "overlay", "start": 2, "end": 4, "offset": 4})
        self.edit("clip_add", clip={"id": "again", "media_id": "media", "start": 2, "end": 6, "offset": 9})
        scope = inspect_structure(self.project, {"range": {"start": 4, "end": 5}, "detail": "review"})
        self.assertEqual([l["clip_id"] for l in scope["layers"]], ["clip", "overlay"])
        self.assertEqual(scope["placements"][0]["source_range"], {"start": 2, "end": 4})
        self.assertEqual(scope["captions"][0]["words"][0]["source_start"], 2)
        self.assertNotIn("private/source.mp4", json.dumps(scope))
        source = inspect_structure(self.project, {"time_space": "source", "media_id": "media", "range": {"start": 2, "end": 4}, "detail": "review"})
        self.assertEqual(len(source["placements"]), 3)
        self.assertEqual(source["captions"][0]["id"], "caption")
        self.assertEqual(source["layers"][0]["source_visual_content"]["status"], "unexamined")

    def test_verification_separates_word_cuts_gaps_layout_and_unheard_audio(self):
        self.aligned_caption()
        self.edit("clip_update", clip_id="clip", changes={"start": 1, "end": 5, "offset": 2})
        report = verify_project(self.project)
        self.assertEqual(report["structure"]["status"], "passed")
        self.assertEqual(report["timeline_gaps"]["gaps"], [{"start": 0., "end": 2}])
        self.assertEqual([i["code"] for i in report["caption_alignment"]["issues"]], ["partial_word_at_cut"] * 2)
        self.assertEqual(report["subtitle_layout"]["status"], "estimated")
        self.assertFalse(report["subtitle_layout"]["rendered_checked"])
        self.assertEqual(report["audiovisual"]["naturalness"], "unchecked")
        self.assertEqual(report["audiovisual"]["reviewed_ranges"], [])
        self.assertEqual(report["overall_status"], "needs_review")
        source = verify_project(self.project, {"time_space": "source", "media_id": "media", "range": {"start": 0, "end": 6}})
        self.assertEqual(len(source["caption_alignment"]["issues"]), 2)

    def test_missing_caption_alignment_never_becomes_valid_from_timing_only(self):
        self.edit("captions_set", media_id="media", captions=[{"id": "plain", "text": "只有句級時間", "start": 0, "end": 4}])
        self.assertEqual(self.project["captions"][0]["alignment_status"], "missing")
        report = verify_project(self.project)
        self.assertEqual(report["caption_alignment"]["issues"][0]["code"], "caption_alignment_missing")
        self.edit("captions_set", media_id="media", captions=[])
        self.assertEqual(verify_project(self.project)["caption_alignment"]["status"], "unchecked")

    def test_retake_candidates_include_distant_context_and_never_authorize_deletion(self):
        self.edit("captions_set", media_id="media", captions=[
            {"id": "first", "text": "接下來開啟設定畫面", "start": 0, "end": 4},
            {"id": "middle", "text": "這裡需要等待載入完成", "start": 8, "end": 12},
            {"id": "retake", "text": "接下來我們開啟設定畫面", "start": 50, "end": 54},
            {"id": "next", "text": "選擇輸出解析度", "start": 56, "end": 60},
        ])
        analysis = analyze_structure(self.project, {"range": {"start": 0, "end": 10}})
        candidate = next(c for c in analysis["retake_candidates"] if c["caption_ids"] == ["first:clip", "retake:clip"])
        self.assertEqual(candidate["edit_recommendation"], "review_only")
        self.assertIsNone(candidate["safe_to_delete"])
        self.assertEqual(candidate["context_after"], "選擇輸出解析度")
        self.assertNotIn("confidence", candidate)
        self.assertEqual(analysis["silence"]["status"], "not_analyzed")

    def test_public_short_analysis_uses_distant_transcript_without_expanding_media_capture(self):
        service = EditorService(self.tmp.name + "/service")
        self.addCleanup(service.close)
        project = service.create_project({"name": "短區間與跨段重述"})
        project = service.store.mutate(project["id"], project["version"], "media_add", {
            "media": {"id": "media", "name": "字幕契約測試.mp4", "path": str(service.assets / "unused.mp4"),
                      "kind": "video", "duration": 300, "width": 320, "height": 180, "has_audio": True}})
        project = service.store.mutate(project["id"], project["version"], "clip_add", {
            "clip": {"id": "clip", "media_id": "media", "end": 300}})
        cues = [{"id": "first", "text": "接下來開啟設定畫面", "start": 1, "end": 4},
                {"id": "retake", "text": "接下來我們開啟設定畫面", "start": 50, "end": 54},
                {"id": "unrelated-a", "text": "按下儲存完成輸出", "start": 65, "end": 68},
                {"id": "unrelated-b", "text": "按下儲存完成輸出", "start": 75, "end": 78},
                {"id": "too-far", "text": "接下來開啟設定畫面", "start": 250, "end": 254}]
        project = service.edit(project["id"], {"expected_version": project["version"],
            "action": "captions_set", "params": {"media_id": "media", "captions": cues}})
        # Only replace the media renderer. Contract validation, snapshot lookup,
        # job execution, structural analysis and registered results remain real.
        for time_space in ("timeline", "source"):
            for window in ({"start": 0, "end": 10}, {"start": 49, "end": 55}):
                with self.subTest(time_space=time_space, window=window):
                    request = {"expected_version": project["version"], "time_space": time_space,
                               "range": window, "max_frames": 1}
                    if time_space == "source":
                        request["media_id"] = "media"
                    with patch("local_editor.evidence.analyze_media", return_value={
                            "files": [], "range": window, "time_space": time_space}) as render:
                        job = service.analyze_range(project["id"], request)
                        job = service.job_status(job["id"], wait_ms=20000)
                    self.assertEqual(job["status"], "succeeded", job)
                    self.assertEqual(render.call_args.args[1]["range"], window)
                    result = job["result"]
                    self.assertEqual(result["structure"]["counts"]["captions"], 1)
                    self.assertEqual(result["evidence"]["range"], window)
                    analysis = result["evidence"]["structural_analysis"]
                    suffix = ":clip" if time_space == "timeline" else ""
                    self.assertEqual([c["caption_ids"] for c in analysis["retake_candidates"]],
                                     [["first" + suffix, "retake" + suffix]])
                    candidate = analysis["retake_candidates"][0]
                    self.assertEqual(len(candidate["outside_observation_ranges"]), 1)
                    self.assertIsNone(candidate["safe_to_delete"])
                    self.assertEqual(candidate["edit_recommendation"], "review_only")
                    coverage = analysis["analysis_coverage"]
                    self.assertEqual(coverage["caption_count"], 1)
                    self.assertEqual(coverage["speech_pace_and_layout_range"], window)
                    self.assertEqual(coverage["transcript_context"]["caption_count"], 4)
                    self.assertEqual(coverage["transcript_context"]["media_evidence_coverage"], "observation_range_only")
                    self.assertEqual(len(analysis["subtitle_layout"]), 1)
        with self.assertRaises(ValueError):
            service.analyze_range(project["id"], {"expected_version": project["version"],
                "time_space": "timeline", "range": {"start": 0, "end": 60}})

    def test_retake_context_cap_keeps_selected_cues_and_exposes_incomplete_search(self):
        self.edit("captions_set", media_id="media", captions=[
            {"id": f"prior-{i}", "text": "甲", "start": i / 100, "end": (i + .5) / 100}
            for i in range(1001)] + [
            {"id": "first", "text": "清楚顯示設定畫面", "start": 50, "end": 51},
            {"id": "again", "text": "清楚顯示設定畫面", "start": 60, "end": 61}])
        analysis = analyze_structure(self.project, {"range": {"start": 49, "end": 52}})
        coverage = analysis["analysis_coverage"]
        self.assertTrue(coverage["truncated"])
        self.assertEqual(coverage["transcript_context"]["analyzed_caption_count"], 1000)
        self.assertEqual(analysis["retake_candidates"][0]["caption_ids"], ["first:clip", "again:clip"])
        self.assertEqual(len(analysis["subtitle_layout"]), 1)

    def test_long_subtitle_is_estimate_with_no_rendered_or_occlusion_pass(self):
        self.edit("settings", width=390, height=844)
        self.edit("captions_set", media_id="media", captions=[{"id": "long", "text": "非常長的字幕" * 10, "start": 0, "end": 2}])
        layout = analyze_structure(self.project)["subtitle_layout"][0]
        self.assertGreater(layout["estimated_lines"], 2)
        self.assertIn("estimated_more_than_two_lines", layout["concerns"])
        self.assertFalse(layout["rendered_bounds_checked"])
        self.assertFalse(layout["occlusion_checked"])

    def test_range_and_revision_validation_and_empty_project(self):
        for request in ({"revision": 1}, {"time_space": "source"}, {"range": {"start": 5, "end": 2}},
                        {"range": {"start": 0, "end": 91}}, {"range": {"start": float("nan"), "end": 1}},
                        {"time_space": "frames"}):
            with self.subTest(request=request), self.assertRaises(EditorError):
                normalize_range(self.project, request)
        empty = self.store.create_project()
        self.assertEqual(inspect_structure(empty)["range"], {"start": 0, "end": 0})

    def test_brief_is_versioned_validated_and_not_inferred(self):
        self.assertEqual(inspect_structure(self.project)["brief"], {})
        self.edit("brief_update", brief={"goal": "教學短片", "target_duration": 60,
                                         "audience": "初學者", "pacing": "保留操作停頓", "notes": "重點需完整", "must_keep": ["確認畫面"]})
        self.assertEqual(inspect_structure(self.project)["brief"]["target_duration"], 60)
        for bad in ({"unknown": True}, {"must_keep": "一段"}, {"target_duration": -1}, {"notes": []}):
            with self.subTest(bad=bad), self.assertRaises(EditorError):
                self.edit("brief_update", brief=bad)
        self.edit("undo")
        self.assertNotIn("brief", self.project)

    def test_stable_cut_ids_survive_unrelated_rename(self):
        self.edit("clip_split", clip_id="clip", at=30)
        boundaries = cut_boundaries(self.project)
        self.edit("rename", name="不影響剪接")
        self.assertEqual(cut_boundaries(self.project), boundaries)

    def test_smart_cut_inside_batch_uses_persisted_plan_and_exact_result(self):
        plan = self.store.prepare_plan(self.project["id"], self.project["version"],
            [{"id": "cut", "media_id": "media", "start": 3, "end": 5}])
        proposal = self.propose([{"action": "smart_cut_apply", "params": {"plan_id": plan["id"], "candidate_ids": ["cut"]}}])
        preview = self.store.preview_edit(self.project["id"], proposal["id"])
        self.assertEqual(project_duration(preview), 88)
        self.project = self.store.apply_edit(self.project["id"], self.project["version"], proposal["id"])
        self.assertEqual(self.project["clips"], preview["clips"])


if __name__ == "__main__":
    unittest.main()
