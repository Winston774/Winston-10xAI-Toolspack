from __future__ import annotations

import copy
import array
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_editor.evidence import _request, analyze_media, inspect_media, review_caption
from local_editor.media_engine import _run, _tool, analyze_speech, doctor, probe, render_project


class EvidenceContractTests(unittest.TestCase):
    def setUp(self):
        self.project = {"id": "p", "version": 3, "width": 320, "height": 180, "fps": 20,
                        "media": [{"id": "m", "duration": 300, "kind": "video", "has_audio": True}],
                        "clips": [{"id": "c", "media_id": "m", "start": 0, "end": 300, "offset": 0, "speed": 1}]}

    def test_bounds_and_unknown_inputs_are_rejected_before_media_access(self):
        bad_requests = [{"range": {"start": 0, "end": 31}}, {"range": {"start": 1, "end": 1}},
                        {"range": {"start": -1, "end": 3}}, {"range": {"start": 0, "end": float("nan")}},
                        {"range": {"start": 0, "end": 1}, "max_frames": 9},
                        {"range": {"start": 0, "end": 1}, "max_frames": 1.5},
                        {"range": {"start": 0, "end": 1}, "include": ["mystery"]},
                        {"range": {"start": 0, "end": 1}, "time_space": "source", "media_id": "missing"}]
        for request in bad_requests:
            with self.subTest(request=request), self.assertRaises(ValueError):
                _request(self.project, request)
        result = _request(self.project, {"range": {"start": 270, "end": 300}, "include": ["composite_frames"]})
        self.assertIn("frames", result["include"])

    def test_rule_confidence_is_not_presented_as_probability_of_safe_deletion(self):
        result = analyze_speech({"id": "m", "duration": 3, "has_audio": False}, {},
                                [{"id": "s", "media_id": "m", "start": 0, "end": .4, "text": "嗯"}])
        self.assertNotIn("confidence", result["candidates"][0])
        self.assertIsNone(result["candidates"][0]["edit_assessment"]["confidence"])
        self.assertEqual(result["candidates"][0]["detection"]["status"], "matched")


@unittest.skipUnless(doctor()["ready"], "需要本機 FFmpeg 與 FFprobe")
class RealEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="editor-evidence-")
        cls.root = Path(cls.temporary.name)
        cls.path = cls.root / "signal.mp4"
        _run([_tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=20:d=6",
              "-f", "lavfi", "-i", "aevalsrc=if(between(t\\,2\\,3)\\,0\\,0.2*sin(2*PI*440*t)):s=48000:d=6",
              "-vf", "drawbox=x=0:y=0:w=320:h=180:color=blue:t=fill:enable='gte(t,3)'",
              "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(cls.path)], timeout=60)
        cls.media = {"id": "m", "path": str(cls.path), "name": "Synthetic signal", **probe(cls.path)}
        cls.project = {"id": "p", "version": 4, "width": 320, "height": 180, "fps": 20,
                       "media": [cls.media], "clips": [{"id": "c", "media_id": "m", "track": "video",
                       "start": 0, "end": 6, "offset": 0, "speed": 1, "fade_in": 2, "fade_out": 2}],
                       "captions": [{"id": "s", "media_id": "m", "start": .5, "end": 5.5,
                                     "text": "COMPOSITION CAPTION"}], "caption_style": {"font_size": 20},
                       "titles": [{"id": "t", "start": 1, "end": 5, "text": "TITLE", "font_size": 22, "x": 0, "y": -40}]}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def pixels(self, path: str, time: float) -> bytes:
        return _run([_tool("ffmpeg"), "-v", "error", "-ss", str(time), "-i", path,
                     "-frames:v", "1", "-vf", "scale=160:90,format=rgb24", "-f", "rawvideo", "pipe:1"],
                    binary=True, timeout=60).stdout

    def audio_rms(self, path: str, time: float) -> float:
        raw = _run([_tool("ffmpeg"), "-v", "error", "-ss", str(time), "-i", path, "-t", "0.4", "-vn",
                    "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"], binary=True, timeout=60).stdout
        samples = array.array("f", raw)
        return math.sqrt(sum(float(sample) ** 2 for sample in samples) / len(samples))

    def test_bounded_render_matches_full_composition_and_mid_clip_fades(self):
        original = copy.deepcopy(self.project)
        full = render_project(self.project, self.root / "full", {"preset": "ultrafast", "crf": 18})
        for start, end in [(1.2, 2), (4.5, 5.3)]:
            partial = render_project(self.project, self.root / "parts", {"range": {"start": start, "end": end},
                                                                       "preset": "ultrafast", "crf": 18})
            self.assertAlmostEqual(partial["duration"], end - start, delta=.1)
            left, right = self.pixels(full["path"], start + .2), self.pixels(partial["path"], .2)
            self.assertEqual(len(left), len(right))
            self.assertLess(sum(abs(a - b) for a, b in zip(left, right)) / len(left), 4,
                            "預覽應保留原淡入淡出進度與字幕／標題布局")
            self.assertAlmostEqual(self.audio_rms(full["path"], start + .2) /
                                   self.audio_rms(partial["path"], .2), 1, delta=.04,
                                   msg="預覽應保留原音訊淡入淡出進度，容許 AAC 邊界編碼差異")
            _run([_tool("ffmpeg"), "-v", "error", "-i", partial["path"], "-f", "null", "-"], timeout=60)
        self.assertEqual(self.project, original)

    def test_inspection_returns_real_registered_ready_evidence_and_coverage(self):
        manifest = inspect_media(self.project, {"range": {"start": 1, "end": 4},
                                 "include": ["frames", "audio", "video"], "max_frames": 3}, self.root)
        self.assertEqual([f["kind"] for f in manifest["files"]].count("image"), 3)
        self.assertTrue(manifest["render_parity"]["same_composition_rules_as_export"])
        self.assertEqual(manifest["coverage"]["audio"], "complete_requested_range")
        self.assertEqual(manifest["coverage"]["frames"], "sampled_only")
        self.assertEqual(manifest["unknowns"]["cursor_actions"]["status"], "unknown")
        for item in manifest["files"]:
            self.assertGreater(Path(item["path"]).stat().st_size, 100)
            self.assertEqual(len(item["sha256"]), 64)
        audio = next(item for item in manifest["files"] if item["kind"] == "audio")
        self.assertAlmostEqual(probe(audio["path"])["duration"], 3, delta=.05)

    def test_source_analysis_measures_pause_and_visual_change_without_claiming_semantics(self):
        manifest = analyze_media(self.project, {"time_space": "source", "media_id": "m",
                                 "range": {"start": 1, "end": 5}, "max_frames": 2}, self.root)
        analysis = manifest["analysis"]
        self.assertGreaterEqual(len(analysis["audio"]["pauses"]), 1)
        pause = analysis["audio"]["pauses"][0]
        self.assertAlmostEqual(pause["range"]["start"], 2, delta=.1)
        self.assertAlmostEqual(pause["range"]["end"], 3, delta=.1)
        self.assertEqual(pause["edit_safety"], "unknown")
        self.assertGreaterEqual(len(analysis["visual_changes"]["events"]), 1)
        self.assertEqual(analysis["audio"]["speech_activity"]["status"], "unknown")

    def test_local_caption_recheck_preserves_authored_text_and_returns_source_word_times(self):
        original = copy.deepcopy(self.project)
        mock_asr = [{"id": "candidate", "media_id": "m", "start": .1, "end": 1.1,
                     "text": "候選辨識", "words": [{"start": .1, "end": .5, "text": "候選"}]}]
        with patch("local_editor.evidence.transcription", return_value=mock_asr) as recognize:
            manifest = review_caption(self.project, {"caption_id": "s", "options": {"padding": .2}}, self.root)
        self.assertEqual(self.project, original)
        self.assertEqual(manifest["authored"]["text"], "COMPOSITION CAPTION")
        self.assertFalse(manifest["proposal"]["applied"])
        self.assertEqual(manifest["alignment"]["forced_alignment"], "unsupported")
        self.assertAlmostEqual(manifest["proposal"]["captions"][0]["words"][0]["start"], .4)
        self.assertTrue(Path(recognize.call_args.args[0]["path"]).is_file())

    def test_far_timeline_range_seeks_source_without_rendering_prior_minutes(self):
        project = copy.deepcopy(self.project)
        project["clips"][0]["offset"] = 600
        project["titles"] = []
        manifest = inspect_media(project, {"range": {"start": 601, "end": 602}, "include": ["video"]}, self.root)
        self.assertAlmostEqual(probe(manifest["files"][0]["path"])["duration"], 1, delta=.05)


if __name__ == "__main__":
    unittest.main()
