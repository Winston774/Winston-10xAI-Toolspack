from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from agent_video_editor.config import list_format_presets, load_format_preset
from agent_video_editor.media import tool_path
from agent_video_editor.pipeline import PipelineContext, run_pipeline
from agent_video_editor.project import create_project
from agent_video_editor.smart_cut import Interval, build_cut_intervals, complement_intervals, parse_silencedetect
from agent_video_editor.subtitles import _dedupe_rolling_segments, _parse_vtt, video_id_from_url, TranscriptSegment


class AgentVideoEditorTests(unittest.TestCase):
    def test_format_presets_are_available(self) -> None:
        formats = list_format_presets()
        self.assertEqual(
            formats,
            ["long-form-youtube", "short-explainer", "short-tiktok-raw"],
        )
        self.assertEqual(load_format_preset("short-explainer")["canvas"]["aspect_ratio"], "9:16")

    def test_create_project_scaffolds_expected_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(root, "demo", format_name="short-explainer")
            self.assertTrue((project.path / "raw").exists())
            self.assertTrue((project.path / "graphics").exists())
            self.assertTrue((project.path / "captions").exists())
            self.assertTrue(project.state_path.exists())

    def test_run_pipeline_dry_run_records_all_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw.mp4"
            raw.write_bytes(b"not really video")
            state = run_pipeline(
                PipelineContext(
                    root=root,
                    job="demo",
                    format_name="short-explainer",
                    raw=raw,
                    dry_run=True,
                )
            )
            self.assertEqual(state["steps"]["export"]["status"], "done")
            self.assertTrue((root / "projects" / "demo" / "graphics" / "graphics-plan.json").exists())
            manifest = root / "projects" / "demo" / "exports" / "export-manifest.json"
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["dry_run"], True)

    def test_youtube_video_id_parsing(self) -> None:
        self.assertEqual(video_id_from_url("https://www.youtube.com/watch?v=XeTAlZiIWHE"), "XeTAlZiIWHE")
        self.assertEqual(video_id_from_url("https://youtu.be/XeTAlZiIWHE"), "XeTAlZiIWHE")

    def test_tool_path_uses_explicit_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "yt-dlp.exe"
            fake.write_text("", encoding="utf-8")
            old = os.environ.get("YT_DLP_PATH")
            os.environ["YT_DLP_PATH"] = str(fake)
            try:
                self.assertEqual(tool_path("yt-dlp"), str(fake))
            finally:
                if old is None:
                    os.environ.pop("YT_DLP_PATH", None)
                else:
                    os.environ["YT_DLP_PATH"] = old

    def test_vtt_parser_extracts_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vtt = Path(tmp) / "sample.vtt"
            vtt.write_text(
                "WEBVTT\n\n"
                "00:00:01.000 --> 00:00:02.500\n"
                "<c>Hello</c> world\n\n",
                encoding="utf-8",
            )
            segments = _parse_vtt(vtt)
            self.assertEqual(len(segments), 1)
            self.assertEqual(segments[0].text, "Hello world")
            self.assertEqual(segments[0].start, 1.0)

    def test_rolling_vtt_segments_are_deduped(self) -> None:
        segments = _dedupe_rolling_segments(
            [
                TranscriptSegment(0, 1, "This video"),
                TranscriptSegment(1, 1, "This video was edited"),
                TranscriptSegment(2, 1, "was edited by Claude"),
            ]
        )
        self.assertEqual([segment.text for segment in segments], ["This video", "was edited", "by Claude"])

    def test_smart_cut_builds_pause_cuts(self) -> None:
        cuts = build_cut_intervals(
            duration=10,
            silences=[Interval(1.0, 2.0), Interval(5.0, 5.2)],
            transcript_segments=[{"start": 0.8, "end": 8.0, "text": "hello"}],
            keep_pause=0.2,
            lead_room=0.3,
            tail_room=0.4,
        )
        self.assertEqual(cuts[0].as_dict(), {"start": 0.0, "end": 0.5, "duration": 0.5})
        self.assertEqual(cuts[1].as_dict(), {"start": 1.1, "end": 1.9, "duration": 0.8})
        self.assertEqual(cuts[-1].as_dict(), {"start": 8.4, "end": 10, "duration": 1.6})
        keeps = complement_intervals(cuts, 10)
        self.assertEqual(keeps[0].start, 0.5)

    def test_parse_silencedetect(self) -> None:
        log = "[silencedetect @ x] silence_start: 1.23\n[silencedetect @ x] silence_end: 2.50 | silence_duration: 1.27\n"
        intervals = parse_silencedetect(log)
        self.assertEqual(intervals[0].as_dict(), {"start": 1.23, "end": 2.5, "duration": 1.27})


if __name__ == "__main__":
    unittest.main()
