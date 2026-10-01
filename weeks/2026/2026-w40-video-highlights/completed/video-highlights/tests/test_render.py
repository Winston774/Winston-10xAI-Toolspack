"""Unit checks and optional real FFmpeg integration checks for the local renderer."""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import vh_render as render
import vh_plan


class RenderUnitTests(unittest.TestCase):
    def test_subtitles_clip_to_local_zero_and_duration(self):
        segments = [{"start": 0, "end": 2, "text": "第一句"},
                    {"start": 2, "end": 4, "text": "第二句"},
                    {"start": 4, "end": 5, "text": "不應出現"}]
        text = render.clip_subtitles(segments, 1.25, 3.5)
        self.assertIn("00:00:00,000 --> 00:00:00,750", text)
        self.assertIn("00:00:00,750 --> 00:00:02,250", text)
        self.assertNotIn("不應出現", text)
        warnings = render.crossing_subtitle_cues(segments, 1.25, 3.5)
        self.assertEqual([warning["crosses"] for warning in warnings], [["start"], ["end"]])

    def test_crop_requires_visual_evidence_and_bounded_position(self):
        candidate = {"framing": {"mode": "crop", "x": .5, "y": .5, "reason": "主體固定"}}
        with self.assertRaises(render.RenderError):
            render.framing_filter(candidate, 180, 320, 640, 360)
        candidate["review"] = {"visual": "sampled", "evidence": ["frames/a.jpg"]}
        self.assertIn("crop=180:320", render.framing_filter(candidate, 180, 320, 640, 360))
        candidate["framing"]["x"] = 1.1
        with self.assertRaises(render.RenderError):
            render.framing_filter(candidate, 180, 320, 640, 360)

    def test_unsafe_id_and_nonfinite_times_rejected(self):
        self.assertIsNone(render.ID_RE.fullmatch("../target"))
        self.assertIsNone(render.ID_RE.fullmatch("a;echo"))
        for value in (True, float("nan"), float("inf"), "1"):
            with self.assertRaises(render.RenderError):
                render.number(value, "start")

    def test_dimensions_account_for_rotation_and_sar(self):
        self.assertEqual(render.display_size({"width": 320, "height": 180,
            "sample_aspect_ratio": "2:1", "side_data_list": [{"rotation": 90}]}), (180, 640))
        self.assertEqual(render.canvas("portrait", 320, 640, 360), (180, 320))
        self.assertEqual(render.canvas("source", 320, 640, 360), (568, 320))


FFMPEG = os.environ.get("VH_FFMPEG") or shutil.which("ffmpeg")
FFPROBE = os.environ.get("VH_FFPROBE") or shutil.which("ffprobe")


@unittest.skipUnless(FFMPEG and FFPROBE, "設 VH_FFMPEG/VH_FFPROBE 或安裝 FFmpeg 才執行真實媒體測試")
class RenderIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="video-highlights-render-")
        cls.root = Path(cls.temp.name)
        cls.audio_source = cls.root / "interview with spaces.mp4"
        cls.silent_source = cls.root / "silent.mp4"
        render.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i",
            "testsrc2=size=320x180:rate=25:duration=3", "-f", "lavfi", "-i",
            "sine=frequency=440:sample_rate=48000:duration=3", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.audio_source)])
        render.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-i", str(cls.audio_source),
                    "-map", "0:v:0", "-an", "-c:v", "copy", str(cls.silent_source)])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def fixture(self, name, audio=True, source=None):
        source = source or (self.audio_source if audio else self.silent_source)
        copied = self.root / f"{name}-input.mp4"
        shutil.copyfile(source, copied)
        source = copied
        info = render.probe(source, FFPROBE)
        video = render.chosen_stream(info, "video")
        sw, sh = render.display_size(video)
        project = {"schema_version": 1, "source": {"path": str(source), "sha256": render.sha256(source),
            "duration": render.media_duration(info), "width": sw, "height": sh, "has_audio": audio,
            "clock": "zero_based_media"},
            "transcript": {"segments": [{"id": "S000001", "start": 0, "end": 2, "text": "測試訪談字幕"}]}}
        candidate = {"id": "H001", "title": "測試標題", "start": .32, "end": 1.88,
            "topic": "合成素材測試", "summary": "驗證媒體輸出", "hook": "測試用字幕",
            "reason": "測試時間切點與輸出規格", "confidence": "medium",
            "scores": {key: 4 for key in vh_plan.WEIGHTS},
            "gates": {key: True for key in vh_plan.GATES},
            "quotes": [{"segment_id": "S000001", "text": "測試訪談字幕"}],
            "review": {"visual": "sampled", "audio": "transcript_only" if audio else "no_audio",
                       "evidence": [source.name]},
            "unresolved": ["合成測試素材，未做人工驗收"], "framing": {"mode": "pad"}}
        project_path = self.root / f"{name}-project.json"
        render.write_json(project_path, project)
        data = {"schema_version": 1, "source_sha256": project["source"]["sha256"],
            "coverage": [{"start": 0, "end": project["source"]["duration"], "kind": "speech",
                          "summary": "合成視訊、正弦波及測試字幕；本測試只驗證程式流程"}],
            "candidates": [candidate]}
        plan = vh_plan.select(data, project_path, min_seconds=.1, max_seconds=3, count=1)
        args = argparse.Namespace(plan=str(self.root / f"{name}-plan.json"), out=str(self.root / name),
            formats=["portrait", "landscape", "square", "source"], height=180,
            ffmpeg=FFMPEG, ffprobe=FFPROBE, burn_subtitles=False)
        self.save(args, plan, project)
        return args, plan, project

    def save(self, args, plan, project):
        Path(plan["project"]).write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
        Path(args.plan).write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    def test_real_render_all_formats_audio_and_clipped_subtitles(self):
        args, plan, project = self.fixture("with-audio")
        with patch.object(render, "load_validated_plan", wraps=render.load_validated_plan) as validate:
            result = render.render(args)
        validate.assert_called_once()
        self.assertEqual(result["status"], "rendered")
        self.assertEqual(result["review_status"], "partial")
        self.assertEqual(len(result["files"]), 4)
        for item in result["files"]:
            self.assertTrue(item["specifications"]["has_audio"])
            self.assertTrue(item["subtitle_boundary_review_required"])
            self.assertEqual(item["crossing_subtitle_cues"][0]["crosses"], ["start", "end"])
            self.assertIn("00:00:00,000 --> 00:00:01,560", (Path(args.out) / item["subtitles"]).read_text(encoding="utf-8"))
        self.assertTrue((Path(args.out) / "metadata" / "render.json").exists())
        with self.assertRaisesRegex(render.RenderError, "新目錄"):
            render.render(args)

    def test_silent_source_crop(self):
        args, plan, project = self.fixture("silent-crop", audio=False)
        args.formats = ["portrait"]
        plan["selected"][0]["framing"] = {"mode": "crop", "x": .2, "y": .5, "reason": "測試固定取景"}
        self.save(args, plan, project)
        result = render.render(args)
        self.assertFalse(result["files"][0]["specifications"]["has_audio"])

    def test_hash_mismatch_stops_before_output(self):
        args, plan, project = self.fixture("bad-hash")
        plan["source_sha256"] = "0" * 64
        project["source"]["sha256"] = "0" * 64
        self.save(args, plan, project)
        with self.assertRaisesRegex(render.RenderError, "SHA256"):
            render.render(args)
        self.assertFalse(Path(args.out).exists())

    def test_encode_failure_only_publishes_failure_report(self):
        args, plan, project = self.fixture("failed-encode")
        args.ffmpeg = str(self.root / "missing-ffmpeg")
        with self.assertRaises(render.RenderError):
            render.render(args)
        self.assertFalse((Path(args.out) / "metadata" / "render.json").exists())
        failure = json.loads((Path(args.out) / "metadata" / "render.failed.json").read_text(encoding="utf-8"))
        self.assertEqual(failure["status"], "failed")

    def test_burn_subtitles_or_explicit_libass_error(self):
        args, plan, project = self.fixture("burn-subtitles")
        args.formats = ["landscape"]
        args.burn_subtitles = True
        if "subtitles" not in render.run([FFMPEG, "-hide_banner", "-filters"]):
            with self.assertRaisesRegex(render.RenderError, "libass"):
                render.render(args)
        else:
            result = render.render(args)
            self.assertTrue(result["files"][0]["subtitles_burned"])

    def test_non_square_pixels_are_normalized(self):
        source = self.root / "anamorphic.mp4"
        render.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-i", str(self.silent_source),
                    "-vf", "setsar=2/1", "-c:v", "libx264", "-an", str(source)])
        args, plan, project = self.fixture("anamorphic-render", audio=False, source=source)
        args.formats = ["source"]
        result = render.render(args)
        self.assertEqual(result["files"][0]["specifications"]["width"], 640)

    def test_rotation_is_applied_before_framing(self):
        source = self.root / "rotated.mp4"
        render.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-display_rotation:v:0", "90",
                    "-i", str(self.silent_source), "-c", "copy", str(source)])
        args, plan, project = self.fixture("rotated-render", audio=False, source=source)
        self.assertEqual((project["source"]["width"], project["source"]["height"]), (180, 320))
        args.formats = ["source"]
        result = render.render(args)
        self.assertEqual(result["files"][0]["specifications"]["width"], 102)

    def test_unreviewed_coverage_keeps_overall_partial(self):
        args, plan, project = self.fixture("partial-coverage")
        args.formats = ["square"]
        plan["selected"][0]["review"].update(visual="watched", audio="listened")
        plan["selected"][0]["unresolved"] = []
        plan["selected"][0]["review_status"] = "reviewed"
        plan["coverage"] = [
            {"start": 0, "end": 2, "kind": "speech", "summary": "合成測試的已檢視範圍"},
            {"start": 2, "end": project["source"]["duration"], "kind": "unreviewed", "summary": "測試未檢視區域"}]
        self.save(args, plan, project)
        result = render.render(args)
        self.assertEqual(result["files"][0]["review_status"], "reviewed")
        self.assertEqual(result["review_status"], "partial")


if __name__ == "__main__":
    unittest.main()
