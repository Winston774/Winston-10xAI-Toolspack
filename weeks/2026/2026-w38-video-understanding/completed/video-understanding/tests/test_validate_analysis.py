import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("validate_analysis", Path(__file__).parents[1] / "scripts" / "validate_analysis.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ValidateAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        (self.base / "clip.mp4").write_bytes(b"test only, not audiovisual evidence")
        self.data = {
            "schema_version": "1.0",
            "source": {"path": "test.mp4", "sha256": "a" * 64, "duration_seconds": 2, "clock": "video_start", "audio_present": False},
            "inspection": {"video": [{"start": 0, "end": 2, "method": "playback", "evidence_ids": ["E1"]}], "audio": []},
            "evidence": [{"id": "E1", "path": "clip.mp4", "kind": "clip", "start": 0, "end": 2, "reviewed": True}],
            "systems": [{"id": "S1", "role": "mg_ui", "description": "test shape"}],
            "events": [{"id": "V1", "start": 0, "end": 2, "system_ids": ["S1"], "anchor": {"kind": "clock", "cue": "opening", "occurrence": None, "timing_precision": "estimated"}, "observed": "test", "interpretation": "test", "confidence": "low", "evidence_ids": ["E1"]}],
            "assets": [{"id": "A1", "kind": "graphic", "description": "test", "event_ids": ["V1"], "depends_on": [], "generation_brief": "test"}],
            "unknowns": [], "handoff": {"status": "ready", "invariants": ["test"], "changeable": [], "next_steps": []}
        }

    def errors(self):
        return MODULE.validate(self.data, self.base)

    def test_consistent_index(self):
        self.assertEqual(self.errors(), [])

    def test_ready_rejects_timeline_gap(self):
        self.data["events"][0]["end"] = 1.9
        self.assertTrue(any("full-duration" in e for e in self.errors()))

    def test_ready_rejects_sampled_only_and_unheard_audio(self):
        self.data["inspection"]["video"][0]["method"] = "sampled_frames"
        self.data["source"]["audio_present"] = True
        errors = self.errors()
        self.assertTrue(any("inspection.video" in e for e in errors))
        self.assertTrue(any("listening" in e for e in errors))

    def test_partial_preserves_missing_modalities(self):
        self.data["handoff"].update(status="partial", next_steps=["listen and inspect"])
        self.data["source"]["audio_present"] = True
        self.data["inspection"]["video"] = []
        self.data["unknowns"] = [{"id": "U1", "question": "audio unread", "start": 0, "end": 2, "blocks_generation": True}]
        self.assertEqual(self.errors(), [])

    def test_bad_refs_duplicates_and_cycle(self):
        self.data["assets"][0]["depends_on"] = ["A1"]
        self.data["events"][0]["system_ids"] = ["missing"]
        self.data["systems"].append(copy.deepcopy(self.data["systems"][0]))
        errors = self.errors()
        self.assertTrue(any("cyclic" in e for e in errors))
        self.assertTrue(any("unknown systems" in e for e in errors))
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_rejects_nan_bool_and_bad_shapes_without_crash(self):
        for value in (float("nan"), True, "2", 10 ** 1000):
            with self.subTest(value=value):
                self.data["events"][0]["end"] = value
                self.assertTrue(self.errors())
        self.data["inspection"]["video"][0]["method"] = []
        self.assertTrue(self.errors())
        self.assertTrue(MODULE.validate([], self.base))

    def test_missing_or_escaping_evidence(self):
        for path in ("missing.jpg", "../outside.jpg", str(self.base / "clip.mp4")):
            with self.subTest(path=path):
                self.data["evidence"][0]["path"] = path
                self.assertTrue(any(".path" in e for e in self.errors()))

    def test_unreviewed_evidence_cannot_support_observation(self):
        self.data["evidence"][0]["reviewed"] = False
        self.assertTrue(any("not been reviewed" in e for e in self.errors()))

    def test_transcript_cannot_claim_listening(self):
        self.data["source"]["audio_present"] = True
        self.data["evidence"][0]["kind"] = "transcript"
        self.data["inspection"]["audio"] = [{"start": 0, "end": 2, "method": "listened", "evidence_ids": ["E1"]}]
        self.assertTrue(any("does not support listened" in e for e in self.errors()))

    def test_ready_rejects_blocking_unknown(self):
        self.data["unknowns"] = [{"id": "U1", "question": "unread title", "start": 0.5, "end": 1, "blocks_generation": True}]
        self.assertTrue(any("blocking" in e for e in self.errors()))

    def test_inspection_cannot_exceed_cited_media_span(self):
        self.data["evidence"][0]["start"] = 1.9
        self.assertTrue(any("does not cover" in e for e in self.errors()))

    def test_event_requires_some_evidence_in_its_interval(self):
        self.data["events"][0]["end"] = 1
        self.data["evidence"][0]["start"] = 1.9
        self.assertTrue(any("overlaps" in e for e in self.errors()))

    def test_dense_frames_requires_multiple_points_and_measured_gap(self):
        self.data["evidence"][0].update(kind="frame", start=0, end=0)
        row = self.data["inspection"]["video"][0]
        row.update(method="dense_frames", max_gap_seconds=0.1)
        self.assertTrue(any("at least two" in e for e in self.errors()))
        for n in range(1, 20):
            self.data["evidence"].append({"id": f"F{n}", "path": "clip.mp4", "kind": "frame", "start": n / 10, "end": n / 10, "reviewed": True})
            row["evidence_ids"].append(f"F{n}")
        self.assertEqual(self.errors(), [])
        row["max_gap_seconds"] = 0.01
        self.assertTrue(any("max_gap_seconds" in e for e in self.errors()))

    def test_frame_at_end_is_rejected(self):
        self.data["evidence"][0].update(kind="frame", start=2, end=2)
        self.assertTrue(any("strictly before" in e for e in self.errors()))

    def test_small_timing_gaps_cannot_accumulate(self):
        self.data["inspection"]["video"] = [
            {"start": a, "end": b, "method": "playback", "evidence_ids": ["E1"]}
            for a, b in ((0, 0.1), (0.1009, 0.2), (0.2009, 2))]
        self.assertTrue(any("full-duration" in e for e in self.errors()))

    def test_source_option_handles_malformed_source_object(self):
        import json
        analysis = self.base / "analysis.json"
        analysis.write_text(json.dumps({"source": None}), encoding="utf-8")
        with mock.patch("sys.argv", ["validate", str(analysis), "--source", str(self.base / "clip.mp4")]), mock.patch("sys.stderr"):
            self.assertEqual(MODULE.main(), 1)


if __name__ == "__main__":
    unittest.main()
