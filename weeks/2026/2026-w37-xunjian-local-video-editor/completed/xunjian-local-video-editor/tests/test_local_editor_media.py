from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from local_editor.media_engine import (MediaError, _ass_text, _ass_time, _atempo, _number,
                                       _run, _tool, analyze_speech, doctor, import_media,
                                       probe, render_project, transcription)
from scripts.create_editor_demo import create_demo


class MediaRulesTests(unittest.TestCase):
    def test_conservative_filler_and_repeated_caption_rules(self):
        media = {"id": "source", "duration": 10, "has_audio": False}
        captions = [{"media_id": "source", "start": 0, "end": .4, "text": "嗯。"},
                    {"media_id": "source", "start": .5, "end": 1.5, "text": "嗯這個方法"},
                    {"media_id": "source", "start": 2, "end": 3, "text": "保留內容"},
                    {"media_id": "source", "start": 3.2, "end": 4.2, "text": "保留內容。"},
                    {"media_id": "other", "start": 5, "end": 6, "text": "呃"}]
        result = analyze_speech(media, {}, captions)
        self.assertEqual([item["kind"] for item in result["candidates"]], ["filler", "repeat"])
        self.assertEqual([item["start"] for item in result["candidates"]], [0, 3.2])
        self.assertTrue(result["requires_review"])
        self.assertTrue(result["warnings"])

    def test_invalid_values_and_subtitle_override_are_rejected(self):
        for value in (math.nan, math.inf, "invalid", -1):
            with self.assertRaises(ValueError):
                _number(value, 0, 0, 1, "值")
        self.assertNotIn("{", _ass_text("{\\pos(2,3)}測試"))
        self.assertEqual(_ass_time(3661.25), "1:01:01.25")
        self.assertEqual(_atempo(4), "atempo=2,atempo=2.00000000")

    def test_transcription_requires_local_audio_and_model(self):
        with self.assertRaises(ValueError):
            transcription({"has_audio": False}, {}, ".")


@unittest.skipUnless(doctor()["ready"], "需要本機 FFmpeg 與 FFprobe")
class RealMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="editor-media-smoke-")
        cls.root = Path(cls.temporary.name)
        cls.demo = create_demo(cls.root / "demo")
        cls.media = import_media(cls.demo["video"], cls.root / "assets")
        cls.overlay = import_media(cls.demo["silent_overlay"], cls.root / "assets")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_import_copy_probe_waveform_and_actual_silences(self):
        self.assertNotEqual(self.media["path"], self.demo["video"])
        self.assertEqual(Path(self.media["path"]).read_bytes(), Path(self.demo["video"]).read_bytes())
        self.assertTrue(Path(self.media["thumbnail"]).is_file())
        self.assertGreater(len(self.media["waveform"]), 10)
        self.assertLessEqual(len(self.media["waveform"]), 240)
        result = analyze_speech(self.media, {"threshold_db": -35, "min_silence": .5, "keep_pause": .2})
        self.assertEqual(len(result["candidates"]), 2, result)
        self.assertAlmostEqual(result["candidates"][0]["start"], 1.1, delta=.05)
        self.assertAlmostEqual(result["candidates"][0]["end"], 1.9, delta=.05)

    def test_real_render_trim_speed_gap_overlay_mix_captions_and_unique_exports(self):
        main_id, overlay_id = self.media["id"], self.overlay["id"]
        project = {"id": "test", "width": 640, "height": 360, "fps": 24,
                   "media": [self.media, self.overlay],
                   "clips": [{"id": "first", "media_id": main_id, "track": "video", "start": 0, "end": 2, "offset": 0, "speed": 1, "volume": .7},
                             {"id": "second", "media_id": main_id, "track": "video", "start": 3, "end": 6, "offset": 2.5, "speed": 1.5, "brightness": .03, "contrast": 1.1, "fade_in": .15, "fade_out": .15},
                             {"id": "overlay", "media_id": overlay_id, "track": "overlay", "start": 0, "end": 1.5, "offset": .25, "scale": .35, "x": 150, "y": -70, "rotation": 5, "opacity": .8},
                             {"id": "audio", "media_id": main_id, "track": "audio", "start": 0, "end": 1, "offset": 2, "volume": .2}],
                   "captions": [{"id": "caption", "media_id": main_id, "start": .25, "end": 1.5, "text": "繁體字幕測試：合成素材"}],
                   "titles": [{"id": "title", "start": 3, "end": 4, "text": "本機輸出測試", "x": 0, "y": -50, "font_size": 28}],
                   "caption_style": {"font_size": 24, "color": "#ffffff", "background": "#000000", "position": "bottom"}}
        reports = []
        first = render_project(project, self.root / "exports", {"preset": "ultrafast"}, reports.append)
        self.assertAlmostEqual(first["duration"], 4.5, delta=.1)
        self.assertEqual((first["width"], first["height"]), (640, 360))
        self.assertTrue(first["has_audio"])
        self.assertGreater(first["size"], 10000)
        self.assertEqual(reports[-1]["progress"], 1)
        # Full decode proves generated packets and filter graph output are valid.
        _run([_tool("ffmpeg"), "-v", "error", "-i", first["path"], "-f", "null", "-"], timeout=60)
        second = render_project(project, self.root / "exports", {"preset": "ultrafast", "burn_captions": False,
                                                                "denoise": True, "normalize_audio": True})
        self.assertNotEqual(first["path"], second["path"])
        self.assertTrue(Path(first["path"]).exists())
        self.assertTrue(second["denoise"])
        self.assertTrue(second["normalize_audio"])
        _run([_tool("ffmpeg"), "-v", "error", "-i", second["path"], "-f", "null", "-"], timeout=60)

    def test_silent_video_exports_with_silent_audio_track(self):
        media_id = self.overlay["id"]
        project = {"media": [self.overlay], "clips": [{"id": "silent", "media_id": media_id,
                    "track": "video", "speed": 1, "start": 0, "end": 1, "offset": .25}], "captions": [], "titles": [],
                    "width": 320, "height": 180, "fps": 24}
        result = render_project(project, self.root / "silent", {"preset": "ultrafast"})
        self.assertAlmostEqual(result["duration"], 1.25, delta=.1)
        self.assertTrue(result["has_audio"])

    def test_still_image_audio_track_and_unicode_export_directory(self):
        still = self.root / "still.png"
        audio = self.root / "tone.wav"
        _run([_tool("ffmpeg"), "-v", "error", "-i", self.demo["silent_overlay"],
              "-frames:v", "1", str(still)], timeout=30)
        _run([_tool("ffmpeg"), "-v", "error", "-i", self.demo["video"],
              "-t", "2", "-vn", str(audio)], timeout=30)
        image_media = import_media(still, self.root / "assets")
        audio_media = import_media(audio, self.root / "assets")
        self.assertEqual(image_media["kind"], "image")
        self.assertEqual(audio_media["kind"], "audio")
        project = {"media": [image_media, audio_media], "clips": [
            {"id": "image", "media_id": image_media["id"], "track": "video", "speed": 1,
             "start": 0, "end": 2, "offset": 0},
            {"id": "audio", "media_id": audio_media["id"], "track": "audio", "speed": 1,
             "start": 0, "end": 2, "offset": 0}], "captions": [],
            "titles": [{"id": "label", "text": "靜態圖片與音軌", "start": 0, "end": 2,
                        "x": 0, "y": 0, "font_size": 20}], "width": 320, "height": 180, "fps": 24}
        result = render_project(project, self.root / "繁中 路徑 'quoted", {"preset": "ultrafast"})
        self.assertAlmostEqual(result["duration"], 2, delta=.1)
        self.assertTrue(result["has_audio"])


if __name__ == "__main__":
    unittest.main()
