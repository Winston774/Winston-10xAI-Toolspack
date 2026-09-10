from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .files import ensure_dir, write_json
from .media import MediaError, tool_path


SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)")
FILLER_ONLY_RE = re.compile(r"^(嗯+|呃+|啊+|就是|那個|然後|好|OK|ok|okay|對)$")


@dataclass(frozen=True)
class Interval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def as_dict(self) -> dict[str, float]:
        return {"start": round(self.start, 3), "end": round(self.end, 3), "duration": round(self.duration, 3)}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = smart_cut(
            input_path=args.input,
            output_path=args.output,
            plan_path=args.plan,
            transcript_path=args.transcript,
            silence_threshold=args.silence_threshold,
            min_silence=args.min_silence,
            keep_pause=args.keep_pause,
            lead_room=args.lead_room,
            tail_room=args.tail_room,
            preset=args.preset,
            crf=args.crf,
        )
    except (MediaError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="smart-cut", description="Cut long pauses and filler-only segments.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--transcript", type=Path)
    parser.add_argument("--silence-threshold", default="-35dB")
    parser.add_argument("--min-silence", type=float, default=0.45)
    parser.add_argument("--keep-pause", type=float, default=0.24)
    parser.add_argument("--lead-room", type=float, default=0.3)
    parser.add_argument("--tail-room", type=float, default=0.45)
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--crf", default="20")
    return parser


def smart_cut(
    *,
    input_path: Path,
    output_path: Path,
    plan_path: Path,
    transcript_path: Path | None,
    silence_threshold: str,
    min_silence: float,
    keep_pause: float,
    lead_room: float,
    tail_room: float,
    preset: str,
    crf: str,
) -> dict[str, Any]:
    if not input_path.exists():
        raise ValueError(f"Input video not found: {input_path}")

    ensure_dir(output_path.parent)
    ensure_dir(plan_path.parent)
    work_dir = plan_path.parent

    duration = probe_duration(input_path)
    transcript_segments = load_transcript_segments(transcript_path) if transcript_path else []
    silence_log = work_dir / "silencedetect.log"
    silences = detect_silences(input_path, silence_log, threshold=silence_threshold, min_silence=min_silence)
    cut_intervals = build_cut_intervals(
        duration=duration,
        silences=silences,
        transcript_segments=transcript_segments,
        keep_pause=keep_pause,
        lead_room=lead_room,
        tail_room=tail_room,
    )
    keep_intervals = complement_intervals(cut_intervals, duration)
    if not keep_intervals:
        raise MediaError("Smart cut produced no keep intervals; refusing to render.")

    filter_script = work_dir / "smart-cut.filter_complex"
    write_filter_script(filter_script, keep_intervals)
    render_concat(input_path, output_path, filter_script, segment_count=len(keep_intervals), preset=preset, crf=crf)

    plan = {
        "input": str(input_path),
        "output": str(output_path),
        "duration_seconds": round(duration, 3),
        "estimated_output_seconds": round(sum(interval.duration for interval in keep_intervals), 3),
        "removed_seconds": round(sum(interval.duration for interval in cut_intervals), 3),
        "rules": {
            "silence_threshold": silence_threshold,
            "min_silence": min_silence,
            "keep_pause": keep_pause,
            "lead_room": lead_room,
            "tail_room": tail_room,
            "filler_only_cutting": True,
        },
        "silence_count": len(silences),
        "cut_count": len(cut_intervals),
        "keep_count": len(keep_intervals),
        "cut_intervals": [interval.as_dict() for interval in cut_intervals],
        "keep_intervals": [interval.as_dict() for interval in keep_intervals],
        "transcript_segments": len(transcript_segments),
    }
    write_json(plan_path, plan)
    write_intervals_csv(work_dir / "smart-cut-keep-intervals.csv", keep_intervals)
    write_intervals_csv(work_dir / "smart-cut-cut-intervals.csv", cut_intervals)
    return {
        "output": str(output_path),
        "plan": str(plan_path),
        "duration_seconds": plan["duration_seconds"],
        "estimated_output_seconds": plan["estimated_output_seconds"],
        "removed_seconds": plan["removed_seconds"],
        "cut_count": plan["cut_count"],
        "keep_count": plan["keep_count"],
    }


def probe_duration(input_path: Path) -> float:
    ffprobe = tool_path("ffprobe")
    if not ffprobe:
        raise MediaError("ffprobe was not found.")
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(input_path)],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise MediaError(completed.stderr.strip() or "ffprobe failed.")
    data = json.loads(completed.stdout)
    return float(data["format"]["duration"])


def detect_silences(input_path: Path, log_path: Path, *, threshold: str, min_silence: float) -> list[Interval]:
    ffmpeg = tool_path("ffmpeg")
    if not ffmpeg:
        raise MediaError("ffmpeg was not found.")
    command = [
        ffmpeg,
        "-hide_banner",
        "-i",
        str(input_path),
        "-af",
        f"silencedetect=noise={threshold}:d={min_silence}",
        "-f",
        "null",
        "-",
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    log_text = (completed.stdout or "") + "\n" + (completed.stderr or "")
    log_path.write_text(log_text, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise MediaError("ffmpeg silencedetect failed; see " + str(log_path))
    return parse_silencedetect(log_text)


def parse_silencedetect(log_text: str) -> list[Interval]:
    silences: list[Interval] = []
    current_start: float | None = None
    for line in log_text.splitlines():
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            current_start = float(start_match.group(1))
            continue
        end_match = SILENCE_END_RE.search(line)
        if end_match and current_start is not None:
            end = float(end_match.group(1))
            if end > current_start:
                silences.append(Interval(current_start, end))
            current_start = None
    return silences


def load_transcript_segments(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    return [segment for segment in segments if "start" in segment and "end" in segment]


def build_cut_intervals(
    *,
    duration: float,
    silences: list[Interval],
    transcript_segments: list[dict[str, Any]],
    keep_pause: float,
    lead_room: float,
    tail_room: float,
) -> list[Interval]:
    cut_intervals: list[Interval] = []
    half_pause = keep_pause / 2
    for silence in silences:
        if silence.duration <= keep_pause:
            continue
        start = silence.start + half_pause
        end = silence.end - half_pause
        if end - start >= 0.08:
            cut_intervals.append(Interval(start, end))

    if transcript_segments:
        first_start = min(float(segment["start"]) for segment in transcript_segments)
        last_end = max(float(segment["end"]) for segment in transcript_segments)
        if first_start > lead_room + 0.2:
            cut_intervals.append(Interval(0.0, max(0.0, first_start - lead_room)))
        if duration - last_end > tail_room + 0.2:
            cut_intervals.append(Interval(min(duration, last_end + tail_room), duration))
        for segment in transcript_segments:
            text = normalize_text(str(segment.get("text", "")))
            start = float(segment["start"])
            end = float(segment["end"])
            if end > start and end - start <= 1.4 and FILLER_ONLY_RE.match(text):
                cut_intervals.append(Interval(max(0.0, start - 0.03), min(duration, end + 0.03)))

    return merge_intervals(cut_intervals, duration)


def normalize_text(value: str) -> str:
    cleaned = re.sub(r"[\s，。！？、,.!?：:；;「」『』（）()]+", "", value)
    return cleaned.strip()


def merge_intervals(intervals: list[Interval], duration: float) -> list[Interval]:
    normalized = [
        Interval(max(0.0, min(duration, interval.start)), max(0.0, min(duration, interval.end)))
        for interval in intervals
        if interval.end - interval.start > 0.03
    ]
    normalized.sort(key=lambda interval: interval.start)
    merged: list[Interval] = []
    for interval in normalized:
        if not merged or interval.start > merged[-1].end:
            merged.append(interval)
        else:
            merged[-1] = Interval(merged[-1].start, max(merged[-1].end, interval.end))
    return merged


def complement_intervals(cuts: list[Interval], duration: float) -> list[Interval]:
    keeps: list[Interval] = []
    cursor = 0.0
    for cut in cuts:
        if cut.start - cursor > 0.08:
            keeps.append(Interval(cursor, cut.start))
        cursor = max(cursor, cut.end)
    if duration - cursor > 0.08:
        keeps.append(Interval(cursor, duration))
    return keeps


def write_filter_script(path: Path, keep_intervals: list[Interval]) -> None:
    lines: list[str] = []
    concat_inputs: list[str] = []
    for index, interval in enumerate(keep_intervals):
        start = f"{interval.start:.3f}"
        end = f"{interval.end:.3f}"
        lines.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{index}]")
        lines.append(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{index}]")
        concat_inputs.append(f"[v{index}][a{index}]")
    lines.append(f"{''.join(concat_inputs)}concat=n={len(keep_intervals)}:v=1:a=1[v][a]")
    path.write_text(";\n".join(lines) + "\n", encoding="utf-8")


def render_concat(
    input_path: Path,
    output_path: Path,
    filter_script: Path,
    *,
    segment_count: int,
    preset: str,
    crf: str,
) -> None:
    ffmpeg = tool_path("ffmpeg")
    if not ffmpeg:
        raise MediaError("ffmpeg was not found.")
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-i",
        str(input_path),
        "-filter_complex_script",
        str(filter_script),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    log_path = output_path.with_suffix(output_path.suffix + ".ffmpeg.log")
    log_path.write_text((completed.stdout or "") + "\n" + (completed.stderr or ""), encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise MediaError(f"ffmpeg render failed after planning {segment_count} segments; see {log_path}")


def write_intervals_csv(path: Path, intervals: list[Interval]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["start", "end", "duration"])
        writer.writeheader()
        for interval in intervals:
            writer.writerow(interval.as_dict())


if __name__ == "__main__":
    raise SystemExit(main())
