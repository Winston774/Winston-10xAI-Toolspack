"""End-user evidence workflows through the shared service, using real media."""
from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from local_editor.core import EditorError
from local_editor.evidence import inspect_media
from local_editor.media_engine import _run, _tool, doctor, probe
from local_editor.service import EditorService, ServiceError


@unittest.skipUnless(doctor()["ready"], "需要本機 FFmpeg 與 FFprobe")
class ObservationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory(prefix="observation-fixture-")
        cls.fixture = Path(cls.fixture_directory.name) / "signal.mp4"
        _run([_tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=green:s=320x180:r=20:d=3",
              "-f", "lavfi", "-i", "sine=f=440:r=48000:d=3", "-c:v", "libx264", "-preset", "ultrafast",
              "-pix_fmt", "yuv420p", "-c:a", "aac", str(cls.fixture)], timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="observation-service-")
        self.service = EditorService(self.directory.name, workers=1)
        self.project = self.service.create_project({"name": "聲畫觀察合成驗收", "width": 320, "height": 180, "fps": 20})
        self.project = self.service.import_media(self.project["id"], {"expected_version": self.project["version"],
                                                                    "path": str(self.fixture)})
        self.media_id = self.project["media"][0]["id"]
        self.change("clip_add", {"media_id": self.media_id, "start": 0, "end": 3})
        self.change("captions_set", {"media_id": self.media_id, "captions": [
            {"id": "caption", "media_id": self.media_id, "start": .2, "end": 2.8, "text": "Synthetic caption"}]})

    def tearDown(self):
        self.service.close()
        self.directory.cleanup()

    def change(self, action, params):
        self.project = self.service.edit(self.project["id"], {"expected_version": self.project["version"],
                                                            "action": action, "params": params})
        return self.project

    def request(self, **overrides):
        return {"expected_version": self.project["version"], "time_space": "timeline",
                "range": {"start": .5, "end": 2.5}, "include": ["frames", "audio"], "max_frames": 2, **overrides}

    def result(self, job):
        for _ in range(4):
            job = self.service.job_status(job["id"], wait_ms=20000)
            if job["status"] in {"succeeded", "failed"}:
                break
        self.assertEqual(job["status"], "succeeded", job)
        return job["result"]

    def capture(self, **overrides):
        return self.result(self.service.inspect_range(self.project["id"], self.request(**overrides)))

    def review(self, evidence, **overrides):
        return self.service.record_review(self.project["id"], {"expected_version": self.project["version"],
            "evidence_id": evidence["evidence_id"], "file_ids": [f["id"] for f in evidence["files"]],
            "reviewer": "test-reviewer", "checks": ["visual"], "outcome": "pass",
            "notes": "Automated synthetic workflow record; this tests scope bookkeeping, not human perception.", **overrides})

    def test_capture_returns_opaque_native_files_and_restores_cache_after_restart(self):
        first = self.capture()
        self.assertFalse(first["cache_hit"])
        manifest = first["evidence"]
        self.assertEqual(manifest["project_version"], self.project["version"])
        self.assertNotIn("path", json.dumps(manifest))
        self.assertNotIn(str(Path(self.directory.name)), json.dumps(first))
        for item in manifest["files"]:
            self.assertTrue(item["uri"].startswith("evidence://"))
            self.assertGreater(self.service.evidence_file(manifest["evidence_id"], item["id"]).stat().st_size, 0)
        audio = next(f for f in manifest["files"] if f["kind"] == "audio")
        self.assertAlmostEqual(probe(self.service.evidence_file(manifest["evidence_id"], audio["id"]))["duration"], 2, delta=.05)
        cached = self.capture()
        self.assertTrue(cached["cache_hit"])
        self.assertFalse(cached["stale"])
        self.assertEqual(cached["evidence"]["evidence_id"], manifest["evidence_id"])
        self.service.close()
        self.service = EditorService(self.directory.name, workers=1)
        restored = self.capture()
        self.assertTrue(restored["cache_hit"])
        self.assertEqual(restored["evidence"]["evidence_id"], manifest["evidence_id"])
        with self.assertRaises(EditorError):
            self.service.evidence_file(manifest["evidence_id"], "../projects")

    def test_missing_cached_file_is_regenerated_and_new_revision_never_reuses_old_evidence(self):
        first = self.capture()["evidence"]
        self.service.evidence_file(first["evidence_id"], first["files"][0]["id"]).unlink()
        second = self.capture()
        self.assertFalse(second["cache_hit"])
        self.assertNotEqual(first["evidence_id"], second["evidence"]["evidence_id"])
        with self.assertRaises(EditorError):
            self.service.evidence_file(first["evidence_id"], second["evidence"]["files"][0]["id"])
        old_version = self.project["version"]
        self.change("caption_update", {"caption_id": "caption", "changes": {"text": "Changed actual overlay"}})
        with self.assertRaises(ServiceError):
            self.service.inspect_range(self.project["id"], self.request(expected_version=old_version))
        third = self.capture()
        self.assertFalse(third["cache_hit"])
        self.assertNotEqual(second["evidence"]["evidence_id"], third["evidence"]["evidence_id"])

    def test_capture_finishing_after_a_concurrent_edit_is_explicitly_stale(self):
        entered, release = threading.Event(), threading.Event()
        def delayed(project, request, output_dir, progress_callback=None):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Concurrency test timed out")
            return inspect_media(project, request, output_dir, progress_callback)
        old_version = self.project["version"]
        with patch("local_editor.evidence.inspect_media", side_effect=delayed):
            job = self.service.inspect_range(self.project["id"], self.request())
            try:
                self.assertTrue(entered.wait(5))
                self.change("rename", {"name": "Concurrent edit"})
            finally:
                release.set()
            result = self.result(job)
        self.assertTrue(result["stale"])
        self.assertEqual(result["evidence"]["project_version"], old_version)
        self.assertEqual(result["current_version"], self.project["version"])
        with self.assertRaises(EditorError):
            self.review(result["evidence"])

    def test_evidence_generation_does_not_count_as_review_and_reviews_are_version_scoped(self):
        manifest = self.capture()["evidence"]
        before = self.service.verify_edit(self.project["id"], {"expected_version": self.project["version"]})
        self.assertEqual(before["audiovisual_review"]["status"], "not_reviewed")
        self.review(manifest, checks=["visual", "audio", "subtitle_layout"])
        after = self.service.verify_edit(self.project["id"], {"expected_version": self.project["version"]})
        self.assertEqual(after["audiovisual_review"]["status"], "partially_reviewed")
        self.assertEqual(len(after["review_records"]), 1)
        self.change("rename", {"name": "A new revision"})
        new = self.service.verify_edit(self.project["id"], {"expected_version": self.project["version"]})
        self.assertEqual(new["audiovisual_review"]["status"], "not_reviewed")

    def test_source_frames_cannot_certify_timeline_subtitle_layout(self):
        source = self.capture(time_space="source", media_id=self.media_id, include=["frames"])["evidence"]
        with self.assertRaises(EditorError):
            self.review(source, checks=["subtitle_layout"])
        self.review(source, checks=["visual"])

    def test_single_selected_image_reviews_only_its_timestamp_and_no_continuous_range(self):
        manifest = self.capture()["evidence"]
        images = [item for item in manifest["files"] if item["kind"] == "image"]
        self.assertEqual(len(images), 2)
        selected = images[0]
        self.review(manifest, file_ids=[selected["id"]], checks=["visual", "subtitle_layout"])
        verification = self.service.verify_edit(self.project["id"], {"expected_version": self.project["version"]})
        reviewed = verification["audiovisual_review"]
        self.assertEqual(reviewed["reviewed_ranges"], [])
        self.assertEqual([frame["time"] for frame in reviewed["sampled_frames"]], [selected["time"]])
        self.assertNotIn(images[1]["time"], [frame["time"] for frame in reviewed["sampled_frames"]])
        self.assertTrue(all("audio" not in frame["checks"] for frame in reviewed["sampled_frames"]))

    def test_selected_audio_reviews_only_audio_and_does_not_certify_available_images(self):
        manifest = self.capture()["evidence"]
        selected = next(item for item in manifest["files"] if item["kind"] == "audio")
        self.review(manifest, file_ids=[selected["id"]], checks=["audio"])
        verification = self.service.verify_edit(self.project["id"], {"expected_version": self.project["version"]})
        reviewed = verification["audiovisual_review"]
        self.assertEqual(reviewed["sampled_frames"], [])
        self.assertEqual(len(reviewed["reviewed_ranges"]), 1)
        self.assertEqual(reviewed["reviewed_ranges"][0]["range"], selected["range"])
        self.assertEqual(reviewed["reviewed_ranges"][0]["checks"], ["audio"])
        self.assertNotIn("visual", reviewed["reviewed_ranges"][0]["checks"])
        self.assertNotIn("subtitle_layout", reviewed["reviewed_ranges"][0]["checks"])

    def test_silent_source_video_cannot_be_recorded_as_an_audio_review(self):
        silent = Path(self.directory.name) / "silent.mp4"
        _run([_tool("ffmpeg"), "-v", "error", "-i", str(self.fixture), "-an", "-c:v", "copy", str(silent)], timeout=30)
        self.project = self.service.import_media(self.project["id"], {"expected_version": self.project["version"],
                                                                    "path": str(silent)})
        silent_id = self.project["media"][-1]["id"]
        evidence = self.capture(time_space="source", media_id=silent_id, include=["video"])["evidence"]
        self.assertFalse(evidence["files"][0]["has_audio"])
        with self.assertRaises(EditorError):
            self.review(evidence, checks=["audio"])

    def test_proposal_before_after_preview_is_reproducible_without_mutating_saved_project(self):
        original = copy.deepcopy(self.service.get_project(self.project["id"]))
        proposal = self.service.prepare_edit(self.project["id"], {"expected_version": self.project["version"],
            "intent": "Review a smaller subtitle before applying", "operations": [
                {"action": "caption_style", "params": {"font_size": 20}}]})
        before = self.capture(edit_id=proposal["edit_id"], preview_side="before")["evidence"]
        after = self.capture(edit_id=proposal["edit_id"], preview_side="after")["evidence"]
        self.assertEqual(self.service.get_project(self.project["id"]), original)
        self.assertEqual(after["snapshot_kind"], "proposal")
        self.assertEqual(after["project_version"], original["version"])
        self.assertNotEqual(before["evidence_id"], after["evidence_id"])
        first_image = next(f for f in before["files"] if f["kind"] == "image")
        next_image = next(f for f in after["files"] if f["kind"] == "image")
        self.assertNotEqual(first_image["sha256"], next_image["sha256"])

    def test_caption_recheck_preserves_authored_text_and_registers_source_audio_proposal(self):
        mock_asr = [{"id": "candidate", "media_id": self.media_id, "start": .3, "end": 2.7,
                     "text": "A proposed correction", "words": [{"start": .3, "end": 2.7, "text": "A proposed correction"}]}]
        with patch("local_editor.evidence.transcription", return_value=mock_asr):
            result = self.result(self.service.review_caption(self.project["id"], {
                "expected_version": self.project["version"], "caption_id": "caption", "options": {"padding": 0}}))
        manifest = result["evidence"]
        self.assertEqual(manifest["time_space"], "source")
        self.assertEqual(manifest["range"], {"start": .2, "end": 2.8})
        self.assertFalse(manifest["proposal"]["applied"])
        self.assertLessEqual(manifest["proposal"]["captions"][0]["end"], manifest["range"]["end"])
        self.assertTrue(manifest["alignment"]["timing_adjustments"])
        self.assertEqual(manifest["authored"]["text"], "Synthetic caption")
        current = self.service.get_project(self.project["id"])
        self.assertEqual(current["captions"][0]["text"], "Synthetic caption")
        self.assertEqual(current["version"], self.project["version"])
        self.assertNotIn("path", json.dumps(manifest))

    def test_bounded_audio_analysis_returns_real_rms_without_asserting_speech(self):
        result = self.result(self.service.analyze_range(self.project["id"], {
            "expected_version": self.project["version"], "time_space": "timeline",
            "range": {"start": .5, "end": 2.5}, "max_frames": 1}))
        audio = result["evidence"]["analysis"]["audio"]
        self.assertEqual(audio["speech_activity"]["status"], "unknown")
        self.assertGreater(len(audio["waveform"]["rms"]), 0)
        self.assertLessEqual(len(audio["waveform"]["rms"]), 120)


if __name__ == "__main__":
    unittest.main()
