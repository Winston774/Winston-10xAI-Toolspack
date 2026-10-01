import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "vh_prepare.py"
SPEC = importlib.util.spec_from_file_location("vh_prepare", SCRIPT)
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class TranscriptTests(unittest.TestCase):
    def test_multiline_srt_retains_text_and_overlap(self):
        text = "\ufeff1\r\n00:00:01,250 --> 00:00:03,500\r\n繁體中文\r\nSecond line\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\n另一位說話者\r\n"
        segments = prepare.parse_srt(text, 5)
        self.assertEqual(segments[0], {"id": "S000001", "start": 1.25, "end": 3.5, "text": "繁體中文\nSecond line"})
        self.assertEqual(segments[1]["id"], "S000002")
        self.assertEqual(prepare.segment_window(segments, 3.4, 4.5), segments)

    def test_bad_srt_timing_is_rejected(self):
        for timing in ("00:60:00,000 --> 01:00:01,000", "00:00:01,000 --> 00:00:01,000", "00:00:00,000 --> 00:00:06,000"):
            with self.subTest(timing=timing), self.assertRaises(prepare.PrepareError):
                prepare.parse_srt("1\n" + timing + "\ntext\n", 5)

    def test_json_numbers_and_order_are_strict(self):
        for value in (True, False, float("nan"), float("inf"), "1"):
            with self.subTest(value=value), self.assertRaises(prepare.PrepareError):
                prepare.validate_segments([{"start": value, "end": 2, "text": "text"}], 5)
        with self.assertRaises(prepare.PrepareError):
            prepare.validate_segments([{"start": 2, "end": 3, "text": "b"}, {"start": 1, "end": 2, "text": "a"}], 5)

    def test_full_chunk_coverage_and_untruncated_boundary_cue(self):
        windows = list(prepare.chunk_windows(650, 300, 20))
        self.assertEqual(windows, [(0, 300), (280, 580), (560, 650)])
        segments = prepare.validate_segments([{"start": 279, "end": 305, "text": "跨越邊界"}], 650)
        self.assertEqual(prepare.segment_window(segments, *windows[0]), segments)
        self.assertEqual(prepare.segment_window(segments, *windows[1]), segments)
        self.assertEqual(segments[0]["end"], 305)
        self.assertEqual(list(prepare.chunk_windows(600, 300, 0)), [(0, 300), (300, 600)])
        for seconds, overlap in ((0, 0), (20, 20), (20, -1)):
            with self.assertRaises(prepare.PrepareError):
                list(prepare.chunk_windows(100, seconds, overlap))

    def test_atomic_publish_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "project.json"
            prepare.atomic_json(path, {"one": 1})
            with self.assertRaises(FileExistsError):
                prepare.atomic_json(path, {"two": 2})
            self.assertEqual(json.loads(path.read_text()), {"one": 1})


FFMPEG = os.environ.get("VH_FFMPEG") or shutil.which("ffmpeg")
FFPROBE = os.environ.get("VH_FFPROBE") or shutil.which("ffprobe")


@unittest.skipUnless(FFMPEG and FFPROBE, "Set VH_FFMPEG / VH_FFPROBE for real FFmpeg integration")
class MediaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.media = cls.base / "interview.mp4"
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                        "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=25:d=1.6",
                        "-f", "lavfi", "-i", "sine=frequency=500:sample_rate=16000:duration=1.6",
                        "-vf", "setsar=2/1", "-c:v", "mpeg4", "-q:v", "4", "-c:a", "aac", "-shortest", str(cls.media)],
                       check=True, capture_output=True)
        cls.original_hash = prepare.file_hash(cls.media)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def arguments(self, name, extra=None):
        return [str(self.media), "--out", str(self.base / name), "--ffmpeg", FFMPEG, "--ffprobe", FFPROBE,
                "--every", "0.8", "--chunk-seconds", "1", "--overlap", "0.2"] + (extra or [])

    def run_prepare(self, name, extra=None):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = prepare.main(self.arguments(name, extra))
        self.assertEqual(result, 0)
        return json.loads((self.base / name / "project.json").read_text(encoding="utf-8"))

    def test_real_prepare_normalizes_sar_and_keeps_source(self):
        subtitle = self.base / "source.srt"
        raw = "1\r\n00:00:00,200 --> 00:00:01,200\r\n重點第一行\r\n第二行\r\n".encode("utf-8")
        subtitle.write_bytes(raw)
        project = self.run_prepare("complete", ["--srt", str(subtitle)])
        out = self.base / "complete"
        self.assertEqual(project["source"]["width"], 640)
        self.assertEqual(project["source"]["height"], 180)
        self.assertEqual(project["source"]["sha256"], self.original_hash)
        self.assertEqual(prepare.file_hash(self.media), self.original_hash)
        self.assertEqual((out / "transcript-original.srt").read_bytes(), raw)
        self.assertEqual(project["overview"][0]["requested_time"], 0)
        for chunk in project["chunks"][:2]:
            text = (out / chunk["file"]).read_text(encoding="utf-8")
            self.assertIn("S000001", text)
            self.assertIn("第二行", text)
            self.assertIn("1.200", text)
        frame = project["overview"][0]["file"]
        dimensions = json.loads(subprocess.run([FFPROBE, "-v", "error", "-show_streams", "-of", "json", str(out / frame)], capture_output=True, text=True, check=True).stdout)["streams"][0]
        self.assertEqual((dimensions["width"], dimensions["height"]), (640, 180))
        with wave.open(str(out / "audio.wav"), "rb") as audio:
            self.assertEqual((audio.getnchannels(), audio.getframerate()), (1, 16000))
        self.assertFalse((out / ".incomplete").exists())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(prepare.main(self.arguments("complete")), 2)

    def test_missing_transcript_has_explicit_gap(self):
        project = self.run_prepare("missing")
        self.assertEqual(project["transcript"]["segments"], [])
        self.assertEqual(project["transcript"]["method"], "missing")
        self.assertTrue(any("缺少逐字稿" in item for item in project["gaps"]))

    def test_shifted_source_is_rejected_before_output(self):
        shifted = self.base / "shifted.mp4"
        subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-i", str(self.media), "-c", "copy", "-output_ts_offset", "2", str(shifted)], check=True, capture_output=True)
        args = self.arguments("shifted-output")
        args[0] = str(shifted)
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            self.assertEqual(prepare.main(args), 2)
        self.assertIn("zero-based copy", error.getvalue())
        self.assertFalse((self.base / "shifted-output").exists())

    def test_parent_traversal_is_rejected(self):
        args = self.arguments("traversal")
        args[2] = str(self.base / "unused" / ".." / "traversal")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(prepare.main(args), 2)
        self.assertFalse((self.base / "traversal").exists())

    def test_rotated_anamorphic_video_has_correct_overview_dimensions(self):
        rotated = self.base / "rotated.mp4"
        result = subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-display_rotation:v:0", "90",
                                 "-i", str(self.media), "-c", "copy", str(rotated)], capture_output=True)
        if result.returncode:
            subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-i", str(self.media), "-c", "copy",
                            "-metadata:s:v:0", "rotate=90", str(rotated)], check=True, capture_output=True)
        args = self.arguments("rotated-output")
        args[0] = str(rotated)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(prepare.main(args), 0)
        out = self.base / "rotated-output"
        project = json.loads((out / "project.json").read_text(encoding="utf-8"))
        self.assertEqual((project["source"]["width"], project["source"]["height"]), (180, 640))
        frame = out / project["overview"][0]["file"]
        actual = json.loads(subprocess.run([FFPROBE, "-v", "error", "-show_streams", "-of", "json", str(frame)], capture_output=True, text=True, check=True).stdout)["streams"][0]
        self.assertEqual((actual["width"], actual["height"]), (180, 640))

    def test_silent_video_and_failed_extraction_are_explicit(self):
        silent = self.base / "silent.mp4"
        subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-i", str(self.media), "-c:v", "copy",
                        "-an", str(silent)], check=True, capture_output=True)
        args = self.arguments("silent-output")
        args[0] = str(silent)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(prepare.main(args), 0)
        out = self.base / "silent-output"
        project = json.loads((out / "project.json").read_text(encoding="utf-8"))
        self.assertFalse(project["source"]["has_audio"])
        self.assertIsNone(project["audio_file"])
        self.assertFalse((out / "audio.wav").exists())
        broken = self.arguments("failed-output")
        broken[4] = str(self.base / "ffmpeg-does-not-exist")
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            self.assertEqual(prepare.main(broken), 2)
        self.assertIn("new --out", error.getvalue())
        failed = self.base / "failed-output"
        self.assertTrue((failed / ".incomplete").is_file())
        self.assertFalse((failed / "project.json").exists())


if __name__ == "__main__":
    unittest.main()
