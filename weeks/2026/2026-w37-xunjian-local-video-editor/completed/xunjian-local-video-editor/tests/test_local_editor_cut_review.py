import copy
import tempfile
import unittest
from pathlib import Path

from local_editor.acceptance import evaluate_checks
from local_editor.contracts import validate_request
from local_editor.cut_review import sample_cuts
from local_editor.evidence import inspect_media
from local_editor.media_engine import _run, _tool, doctor, probe
from local_editor.service import EditorService


class CutReviewContracts(unittest.TestCase):
    def test_rejects_wrong_time_space_and_invalid_checks(self):
        with self.assertRaises(ValueError):
            validate_request("inspect", {"expected_version": 1, "time_space": "source", "media_id": "m",
                "range": {"start": 0, "end": 2}, "sampling": {"strategy": "cut_boundaries"}})
        for check in [{"kind": "duration_between", "min": 4, "max": 2},
                      {"kind": "no_black_frames", "range": {"start": 0, "end": 31}},
                      {"kind": "pretend_watched"}]:
            with self.subTest(check=check), self.assertRaises(ValueError):
                validate_request("edits", {"expected_version": 1, "intent": "test",
                    "operations": [{"action": "rename", "params": {"name": "test"}}], "checks": [check]})

    def test_missing_media_evidence_never_passes(self):
        project = {"clips": [], "titles": [{"end": 4}]}
        result = evaluate_checks(project, [{"kind": "no_black_frames", "range": {"start": 0, "end": 2}}])
        self.assertEqual(result["status"], "pending")
        check = {"kind": "no_black_frames", "range": {"start": 0, "end": 2}}
        for scan in [{"status": "completed", "range": {"start": 0, "end": 1}, "findings": []},
                     {"status": "completed", "range": check["range"], "findings": [], "truncated": True}]:
            self.assertEqual(evaluate_checks(project, [check], [{"black_scan": scan}])["status"], "pending")

    def test_cut_grid_is_relative_to_partial_render_and_reports_omissions(self):
        project = {"fps": 20, "titles": [], "clips": [
            {"id": "a", "media_id": "m", "track": "video", "start": 0, "end": 2, "offset": 0, "speed": 1},
            {"id": "b", "media_id": "m", "track": "video", "start": 4, "end": 6, "offset": 2, "speed": 1}]}
        samples, coverage = sample_cuts(project, {"range": {"start": 1.03, "end": 3},
            "sampling": {"strategy": "cut_boundaries"}, "max_frames": 3})
        self.assertEqual([s["index"] for s in samples], [19, 20, 21])
        self.assertEqual(coverage["omitted_frame_count"], 2)
        self.assertAlmostEqual(1.03 + samples[1]["relative_time"], 2.03)


@unittest.skipUnless(doctor()["ready"], "需要本機 FFmpeg 與 FFprobe")
class CutReviewIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cut-review-")
        self.root = Path(self.temp.name)
        self.service = EditorService(self.root / "data")
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.service.close)
        self.path = self.root / "flash.mp4"
        _run([_tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=20:d=4",
            "-vf", "drawbox=color=blue:t=fill:enable='gte(n,40)',drawbox=color=black:t=fill:enable='between(n,39,40)'",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(self.path)], timeout=60)
        self.project = self.service.store.create_project("合成黑閃驗收")
        self.mutate("settings", {"width": 320, "height": 180, "fps": 20})
        self.mutate("media_add", {"media": {"id": "m", "name": "flash.mp4", "path": str(self.path), **probe(self.path)}})
        self.mutate("clip_add", {"clip": {"id": "a", "media_id": "m", "start": 0, "end": 2}})
        self.mutate("clip_add", {"clip": {"id": "b", "media_id": "m", "start": 2, "end": 4, "offset": 2}})

    def mutate(self, action, params):
        self.project = self.service.store.mutate(self.project["id"], self.project["version"], action, params)

    def wait(self, job):
        import time
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            result = self.service.job_status(job["id"], 1000)
            if result["status"] in {"succeeded", "failed"}:
                self.assertEqual(result["status"], "succeeded", result)
                return result["result"]
        self.fail("區間觀察工作逾時")

    def request(self, **extra):
        return {"expected_version": self.project["version"], "time_space": "timeline",
                "range": {"start": 1, "end": 3}, "sampling": {"strategy": "cut_boundaries"},
                "scan_black_frames": True, "include": ["frames", "video"], "max_frames": 8, **extra}

    def test_detects_two_frame_flash_and_native_frame_mapping(self):
        result = self.wait(self.service.inspect_range(self.project["id"], self.request()))
        evidence = result["evidence"]
        scan = evidence["black_scan"]
        self.assertEqual(scan["decoded_frame_count"], 40)
        self.assertEqual(scan["candidate_count"], 1)
        finding = evidence["findings"][0]
        self.assertEqual(finding["frame_count"], 2)
        self.assertAlmostEqual(finding["time"], 1.95, places=4)
        self.assertEqual(finding["review_status"], "unreviewed")
        self.assertEqual(finding["evidence_id"], evidence["evidence_id"])
        image = next(f for f in evidence["files"] if f.get("finding_id"))
        self.assertEqual(image["source_mapping"][0]["clip_id"], "a")
        raw = _run([_tool("ffmpeg"), "-v", "error", "-i", str(self.service.evidence_file(evidence["evidence_id"], image["id"])),
                    "-vf", "scale=1:1,format=gray", "-f", "rawvideo", "pipe:1"], binary=True).stdout
        self.assertLess(raw[0], 24, "候選圖片必須真的是黑閃影格")
        cached = self.wait(self.service.inspect_range(self.project["id"], self.request()))
        self.assertTrue(cached["cache_hit"])

    def test_detects_single_frame_and_non_grid_aligned_range(self):
        self.mutate("clip_update", {"clip_id": "a", "changes": {"end": 1.95}})
        self.mutate("clip_update", {"clip_id": "b", "changes": {"offset": 1.95}})
        result = self.wait(self.service.inspect_range(self.project["id"], self.request(range={"start": 1.03, "end": 3})))
        finding = result["evidence"]["findings"][0]
        self.assertEqual(finding["frame_count"], 1)
        self.assertGreaterEqual(finding["time"], 1.93)
        self.assertLessEqual(finding["time"], 2.03)
        self.assertTrue(finding["file_ids"])

    def test_proposal_checks_isolate_before_after_and_saved_revision(self):
        checks = [{"kind": "no_timeline_gaps"}, {"kind": "duration_between", "min": 3.89, "max": 3.91},
                  {"kind": "no_black_frames", "range": {"start": 1, "end": 3}}]
        proposal = self.service.prepare_edit(self.project["id"], {"expected_version": self.project["version"],
            "intent": "移除兩個合成黑影格", "checks": checks, "operations": [
                {"action": "clip_update", "params": {"clip_id": "a", "changes": {"end": 1.95}}},
                {"action": "clip_update", "params": {"clip_id": "b", "changes": {"start": 2.05, "offset": 1.95}}}]})
        self.assertEqual(proposal["acceptance"]["status"], "pending")
        self.assertEqual(self.service.get_edit(self.project["id"], proposal["id"])["checks"], checks)
        verify = {"expected_version": self.project["version"], "edit_id": proposal["id"]}
        self.wait(self.service.inspect_range(self.project["id"], self.request(edit_id=proposal["id"], preview_side="before")))
        self.assertEqual(self.service.verify_edit(self.project["id"], verify)["acceptance"]["status"], "pending")
        self.wait(self.service.inspect_range(self.project["id"], self.request(edit_id=proposal["id"], preview_side="after")))
        report = self.service.verify_edit(self.project["id"], verify)
        self.assertEqual(report["acceptance"]["status"], "passed")
        self.assertEqual(report["audiovisual_review"]["status"], "not_reviewed")
        updated = self.service.apply_edit(self.project["id"], verify)
        self.assertEqual(updated["verification"]["acceptance"]["status"], "pending")
        self.project = self.service.store.get_project(self.project["id"])
        self.wait(self.service.inspect_range(self.project["id"], self.request()))
        report = self.service.verify_edit(self.project["id"], {"expected_version": self.project["version"]})
        self.assertEqual(report["acceptance"]["status"], "passed")
        self.assertEqual(report["findings"], [], "正常紅藍硬切不應產生黑畫面候選")
