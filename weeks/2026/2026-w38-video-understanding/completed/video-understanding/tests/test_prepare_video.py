"""Stdlib tests; optional generated-media integration with VIDEO_TEST_FFMPEG/FFPROBE."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_video.py"
spec = importlib.util.spec_from_file_location("prepare_video", SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class UnitTests(unittest.TestCase):
    def test_rejects_invalid_ranges_before_extracting(self):
        for start, end, interval in [(0, 5, 0), (0, 5, -1), (-1, 5, 1), (2, 2, 1),
                                     (0, float("nan"), 1), (0, 5, float("inf")),
                                     (0, 5, 1e-320)]:
            with self.subTest(start=start, end=end, interval=interval):
                with self.assertRaises(helper.PreparationError):
                    helper.sampling_plan(start, end, interval, 240, None)

    def test_cap_and_fractional_boundary(self):
        plan = helper.sampling_plan(0.2, 0.5, 0.1, 4, helper.rational("30/1"))
        self.assertEqual(plan["planned_frame_upper_bound"], 4)
        with self.assertRaises(helper.PreparationError):
            helper.sampling_plan(0, 240, 1, 240, helper.rational("30/1"))

    def test_video_timestamp_uses_integer_pts(self):
        parsed = helper.video_timestamps("[Parsed_showinfo_4 @ abc] config in time_base: 1/30000, frame_rate: 30/1\n"
                                         "[Parsed_showinfo_4 @ abc] n:   0 pts:  301001 pts_time:10.0334 fmt:yuvj420p s:320x240\n")
        self.assertAlmostEqual(parsed[0]["absolute_pts_seconds"], 301001 / 30000)
        self.assertEqual(parsed[0]["image_width"], 320)
        with self.assertRaises(helper.PreparationError):
            helper.video_timestamps("no timestamps")

    def test_audio_segments_preserve_source_gaps(self):
        log = "\n".join(f"[Parsed_ashowinfo_3 @ x] n:{i} pts:{pts} pts_time:0 fmt:s16 nb_samples:{count} checksum:abc"
                        for i, (pts, count) in enumerate([(16000, 800), (16800, 800), (20000, 400)]))
        segments = helper.audio_mapping(log, 0.5, 2000)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["source_start_seconds"], 0.5)
        self.assertEqual(segments[0]["duration_seconds"], 0.1)
        self.assertEqual(segments[1]["wav_start_seconds"], 0.1)
        self.assertEqual(segments[1]["source_start_seconds"], 0.75)
        with self.assertRaises(helper.PreparationError):
            helper.audio_mapping(log, 0, 1999)

    def test_metadata_clock_prefers_exact_pts(self):
        probe = {"streams": [{"index": 0, "codec_type": "video", "width": 320, "height": 240,
                              "start_pts": 90000, "time_base": "1/90000", "duration": "2"}],
                 "format": {"start_time": "0.5", "duration": "2.5"}}
        result = helper.metadata(probe)
        self.assertEqual(result[2], 1)
        del probe["streams"][0]["duration"]
        self.assertEqual(helper.metadata(probe)[4], 2)

    def test_existing_output_refused_without_running_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.mp4"
            source.write_bytes(b"fixture")
            out = Path(directory) / "existing"
            out.mkdir()
            args = helper.parser().parse_args([str(source), "--out", str(out)])
            with mock.patch.object(helper, "run") as run:
                with self.assertRaisesRegex(helper.PreparationError, "already exists"):
                    helper.prepare(args)
                run.assert_not_called()

    def test_corrupt_input_does_not_publish_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bad.mp4"
            source.write_bytes(b"bad")
            out = Path(directory) / "evidence"
            args = helper.parser().parse_args([str(source), "--out", str(out)])
            with mock.patch.object(helper, "find_tool", return_value="mock-tool"):
                with mock.patch.object(helper, "run", side_effect=helper.PreparationError("corrupt media")):
                    with self.assertRaisesRegex(helper.PreparationError, "corrupt media"):
                        helper.prepare(args)
            self.assertFalse(out.exists())


@unittest.skipUnless(os.environ.get("VIDEO_TEST_FFMPEG") and os.environ.get("VIDEO_TEST_FFPROBE"),
                     "Set VIDEO_TEST_FFMPEG and VIDEO_TEST_FFPROBE to run generated-media tests")
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ffmpeg = os.environ["VIDEO_TEST_FFMPEG"]
        self.ffprobe = os.environ["VIDEO_TEST_FFPROBE"]

    def tearDown(self):
        self.temp.cleanup()

    def command(self, command):
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def extract(self, source, name, *options):
        out = self.root / name
        args = helper.parser().parse_args([str(source), "--out", str(out), "--ffmpeg", self.ffmpeg,
                                          "--ffprobe", self.ffprobe, *options])
        result = helper.prepare(args)
        self.assertEqual(json.loads((out / "manifest.json").read_text(encoding="utf-8")), result)
        return result, out

    def test_generated_av_range_and_audio_clock(self):
        source = self.root / "av.mkv"
        self.command([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                      "-filter_complex", "testsrc2=size=160x90:rate=10:duration=2[v];sine=frequency=440:sample_rate=16000:duration=2[a]",
                      "-map", "[v]", "-map", "[a]",
                      "-c:v", "ffv1", "-c:a", "pcm_s16le", str(source)])
        manifest, out = self.extract(source, "range", "--start", "0.5", "--end", "1.8", "--every", "0.5")
        times = [frame["source_time_seconds"] for frame in manifest["frames"]]
        self.assertAlmostEqual(times[0], 0.5)
        self.assertAlmostEqual(times[-1], 1.7)
        self.assertFalse(manifest["sampling"]["requested_full_duration"])
        self.assertTrue(manifest["audio"]["present"])
        self.assertAlmostEqual(manifest["audio"]["wav_zero_source_seconds"], 0.5)
        self.assertAlmostEqual(manifest["audio"]["duration_seconds"], 1.3)
        self.assertTrue((out / "audio.wav").is_file())
        self.assertFalse(manifest["review"]["semantic_analysis_performed"])

    def test_frame_rate_interval_does_not_skip_decimal_boundaries(self):
        for offset in (0, 2):
            with self.subTest(offset=offset):
                source = self.root / f"decimal-{offset}.mkv"
                self.command([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                              "-filter_complex", f"testsrc2=size=160x90:rate=10:duration=4,setpts=PTS+{offset}/TB[v]",
                              "-map", "[v]", "-c:v", "ffv1", str(source)])
                manifest, _ = self.extract(source, f"decimal-frames-{offset}", "--every", "0.1")
                times = [round(frame["source_time_seconds"], 6) for frame in manifest["frames"]]
                self.assertEqual(times, [n / 10 for n in range(40)])
                self.assertTrue(manifest["sampling"]["all_source_frames_extracted"])
                self.assertFalse(manifest["review"]["frames_visually_reviewed"])

    def test_frame_exact_subrange_uses_integer_pts_at_decimal_start(self):
        source = self.root / "thirty-fps.mkv"
        self.command([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                      "-filter_complex", "testsrc2=size=160x90:rate=30:duration=4[v]",
                      "-map", "[v]", "-c:v", "ffv1", str(source)])
        for start, end in ((0.4, 0.7), (3.4, 3.7)):
            manifest, _ = self.extract(source, f"exact-{start}", "--start", str(start), "--end", str(end), "--every", str(1/30))
            self.assertAlmostEqual(manifest["frames"][0]["source_time_seconds"], start)
            self.assertAlmostEqual(manifest["frames"][-1]["source_time_seconds"], end - 1/30, delta=0.001)

    def test_generated_no_audio_and_nonzero_video_origin(self):
        source = self.root / "offset.mkv"
        self.command([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                      "-filter_complex", "testsrc2=size=160x90:rate=10:duration=1,setpts=PTS+2/TB[v]",
                      "-map", "[v]", "-c:v", "ffv1", str(source)])
        manifest, out = self.extract(source, "offset-evidence", "--every", "0.3")
        self.assertAlmostEqual(manifest["clock"]["origin_absolute_pts_seconds"], 2)
        self.assertAlmostEqual(manifest["source"]["duration_seconds"], 1)
        self.assertAlmostEqual(manifest["frames"][0]["source_time_seconds"], 0)
        self.assertAlmostEqual(manifest["frames"][-1]["source_time_seconds"], 0.9)
        self.assertFalse(manifest["audio"]["present"])
        self.assertEqual(manifest["audio"]["status"], "no_audio_stream")
        self.assertFalse((out / "audio.wav").exists())

    def test_generated_vfr_keeps_real_timestamps_and_last_frame(self):
        source = self.root / "vfr.mkv"
        self.command([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                      "-filter_complex", "testsrc2=size=160x90:rate=10:duration=2,select='eq(n,0)+eq(n,3)+eq(n,4)+eq(n,11)+eq(n,19)'[v]",
                      "-map", "[v]", "-fps_mode", "vfr", "-c:v", "ffv1", str(source)])
        manifest, _ = self.extract(source, "vfr-evidence", "--every", "0.5")
        times = [frame["source_time_seconds"] for frame in manifest["frames"]]
        self.assertEqual(times, [0, 1.1, 1.9])
        self.assertEqual(manifest["source"]["decoded_frame_count"], 5)
        close, _ = self.extract(source, "vfr-close", "--start", "0.25", "--end", "1.5", "--every", "0.5")
        self.assertEqual([frame["source_time_seconds"] for frame in close["frames"]], [0.3, 1.1])

    def test_generated_delayed_audio_and_empty_audio_range(self):
        source = self.root / "delayed-audio.mkv"
        self.command([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                      "-filter_complex", "testsrc2=size=160x90:rate=10:duration=2[v];sine=frequency=440:sample_rate=16000:duration=1,asetpts=PTS+0.4/TB[a]",
                      "-map", "[v]", "-map", "[a]", "-c:v", "ffv1", "-c:a", "pcm_s16le", str(source)])
        manifest, _ = self.extract(source, "delayed-evidence", "--every", "0.5")
        self.assertAlmostEqual(manifest["audio"]["wav_zero_source_seconds"], 0.4)
        self.assertAlmostEqual(manifest["audio"]["duration_seconds"], 1)
        empty, out = self.extract(source, "empty-range", "--start", "0", "--end", "0.3")
        self.assertTrue(empty["audio"]["present"])
        self.assertEqual(empty["audio"]["status"], "no_decoded_samples_in_requested_range")
        self.assertFalse((out / "audio.wav").exists())

    def test_generated_pixel_aspect_and_rotation_display_geometry(self):
        source = self.root / "wide-pixels.mkv"
        self.command([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                      "-filter_complex", "testsrc2=size=160x90:rate=10:duration=0.3,setsar=2/1[v]",
                      "-map", "[v]", "-c:v", "ffv1", str(source)])
        manifest, _ = self.extract(source, "sar-evidence")
        self.assertEqual(manifest["frames"][0]["image_width"], 320)
        self.assertEqual(manifest["frames"][0]["image_height"], 90)
        base, rotated = self.root / "base.mp4", self.root / "rotated.mp4"
        self.command([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                      "-filter_complex", "testsrc2=size=160x90:rate=10:duration=0.3[v]",
                      "-map", "[v]", "-c:v", "mpeg4", str(base)])
        self.command([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                      "-display_rotation:v:0", "90", "-i", str(base), "-c", "copy", str(rotated)])
        rotated_manifest, _ = self.extract(rotated, "rotation-evidence")
        self.assertEqual(rotated_manifest["frames"][0]["image_width"], 90)
        self.assertEqual(rotated_manifest["frames"][0]["image_height"], 160)


if __name__ == "__main__":
    unittest.main()
