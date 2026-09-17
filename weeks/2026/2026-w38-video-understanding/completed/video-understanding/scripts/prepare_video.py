#!/usr/bin/env python3
"""Prepare local, timestamped video evidence. No semantic analysis or network I/O."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import wave


SCHEMA_VERSION = "1.0"
SAMPLE_RATE = 16000


class PreparationError(Exception):
    pass


def finite_number(value, name, *, minimum=None):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PreparationError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise PreparationError(f"{name} must be finite and >= {minimum}")
    return result


def optional_number(value):
    if value is None or value == "N/A":
        return None
    return finite_number(value, "media metadata")


def rational(value):
    try:
        result = Fraction(str(value))
        return result if result > 0 else None
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def find_tool(value, name):
    found = shutil.which(value or name)
    if not found:
        raise PreparationError(f"Missing {name}: install it yourself or supply --{name} PATH")
    return str(Path(found).resolve())


def run(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", check=False)
    except OSError as exc:
        raise PreparationError(f"Could not run {command[0]}: {exc}") from exc
    if result.returncode:
        raise PreparationError(f"{Path(command[0]).name} failed ({result.returncode}):\n"
                               f"{result.stderr[-5000:]}")
    return result


def metadata(probe):
    streams = probe.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")]
    if not videos:
        raise PreparationError("Input has no usable video stream")
    video = videos[0]
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = probe.get("format", {})
    time_base = rational(video.get("time_base"))
    start_pts = video.get("start_pts")
    if start_pts is not None and time_base is not None:
        try:
            origin = float(int(start_pts) * time_base)
        except (TypeError, ValueError, OverflowError) as exc:
            raise PreparationError("Invalid video start_pts") from exc
        origin_basis = "video.start_pts * video.time_base"
    elif optional_number(video.get("start_time")) is not None:
        origin = optional_number(video.get("start_time"))
        origin_basis = "video.start_time"
    else:
        origin = optional_number(fmt.get("start_time")) or 0.0
        origin_basis = "format.start_time fallback" if fmt.get("start_time") else "zero fallback"
    origin = finite_number(origin, "video clock origin")
    duration = optional_number(video.get("duration"))
    duration_basis = "video.duration"
    if duration is None:
        duration_ts = video.get("duration_ts")
        if duration_ts is not None and time_base is not None:
            duration = float(int(duration_ts) * time_base)
            duration_basis = "video.duration_ts * video.time_base"
    if duration is None:
        container_duration = optional_number(fmt.get("duration"))
        if container_duration is not None:
            container_start = optional_number(fmt.get("start_time")) or 0.0
            duration = container_start + container_duration - origin
            duration_basis = "format.start_time + format.duration - video clock origin (estimate)"
    if duration is not None:
        duration = finite_number(duration, "video duration", minimum=0)
    width, height = video.get("width"), video.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise PreparationError("Video has invalid dimensions")
    return video, audio, origin, origin_basis, duration, duration_basis


def decoded_video_timing(ffprobe, source, video, requested_start, requested_end, fps):
    """Stream a numeric-only full decode to establish first/last frame timing.

    Container duration is inconsistent for timestamp-offset files. Keeping only
    a few integers avoids loading an entire frame inventory into memory.
    """
    base = rational(video.get("time_base"))
    if base is None:
        raise PreparationError("Video is missing a usable time_base")
    command = [ffprobe, "-v", "error", "-protocol_whitelist", "file", "-select_streams", str(video["index"]), "-show_frames",
               "-show_entries", "frame=pts,best_effort_timestamp,duration,pkt_duration",
               "-of", "compact=p=0:nk=0", str(source)]
    first = last = previous = last_duration = first_in_range = last_in_range = None
    count = 0
    first_kind = None
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, encoding="utf-8", errors="replace")
        try:
            for line in process.stdout:
                values = dict(pair.split("=", 1) for pair in line.strip().split("|") if "=" in pair)
                raw_pts = values.get("pts", values.get("best_effort_timestamp"))
                if raw_pts is None or raw_pts == "N/A":
                    raw_pts = values.get("best_effort_timestamp")
                if raw_pts is None or raw_pts == "N/A":
                    continue  # Side-data-only lines have no frame timestamp.
                pts = int(raw_pts)
                if last is not None and pts <= last:
                    raise PreparationError("Video has non-increasing decoded timestamps; review manually")
                if first is None:
                    first = pts
                    first_kind = "pts" if values.get("pts") not in (None, "N/A") else "best_effort_timestamp"
                previous, last = last, pts
                raw_duration = values.get("duration", values.get("pkt_duration"))
                last_duration = int(raw_duration) if raw_duration not in (None, "N/A") else None
                relative = float((pts - first) * base)
                if relative >= requested_start and (requested_end is None or relative < requested_end):
                    if first_in_range is None:
                        first_in_range = pts
                    last_in_range = pts
                count += 1
            result = process.wait()
            errors.seek(0)
            error_text = errors.read().decode("utf-8", errors="replace")
            if result or error_text.strip():
                raise PreparationError(f"FFprobe could not cleanly decode the video ({result}):\n{error_text[-5000:]}")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
    if first is None:
        raise PreparationError("Video contains no decodable timestamped frames")
    if last_in_range is None:
        raise PreparationError("No decoded video frames fall in the requested range")
    if last_duration and last_duration > 0:
        final_duration = last_duration * base
        end_basis = "last decoded frame PTS plus reported frame duration"
    elif previous is not None:
        final_duration = (last - previous) * base
        end_basis = "last decoded frame PTS plus previous frame interval (end estimate)"
    elif fps:
        final_duration = 1 / fps
        end_basis = "single decoded frame PTS plus reciprocal FPS (end estimate)"
    else:
        raise PreparationError("Cannot determine the duration of a single-frame video without duration/FPS")
    return {"first_pts": first, "last_pts": last, "time_base": str(base),
            "origin_seconds": float(first * base), "origin_basis": f"first decoded video frame {first_kind}",
            "duration_seconds": float((last - first) * base + final_duration),
            "duration_basis": end_basis, "decoded_frame_count": count,
            "first_frame_in_requested_range_pts": first_in_range,
            "last_frame_in_requested_range_pts": last_in_range,
            "first_frame_in_requested_range_seconds": float((first_in_range - first) * base),
            "last_frame_in_requested_range_seconds": float((last_in_range - first) * base)}


def sampling_plan(start, end, every, max_frames, fps, last_frame_time=None):
    start = finite_number(start, "--start", minimum=0)
    end = finite_number(end, "--end", minimum=0)
    every = finite_number(every, "--every", minimum=0)
    if every <= 0:
        raise PreparationError("--every must be greater than zero")
    if end <= start:
        raise PreparationError("--end must be greater than --start")
    if not isinstance(max_frames, int) or max_frames < 1:
        raise PreparationError("--max-frames must be a positive integer")
    span = end - start
    quotient = span / every
    if not math.isfinite(quotient):
        raise PreparationError("Sampling interval is too small for this range")
    # Round only machine-precision noise at an exact bucket boundary.
    buckets = max(1, math.ceil(quotient - 1e-12 * max(1, abs(quotient))))
    nominal_frame = 1 / float(fps) if fps else min(0.04, span)
    tail = max(start, end - min(every, nominal_frame)) if last_frame_time is None else last_frame_time
    # The near-end target may add one frame to the final interval bucket.
    bound = buckets + (1 if tail > start else 0)
    if bound > max_frames:
        raise PreparationError(f"Sampling requires up to {bound} frames, exceeding --max-frames "
                               f"{max_frames}; increase --every, shorten the range, or raise the cap")
    return {"start_seconds": start, "end_seconds_exclusive": end,
            "every_seconds": every, "last_frame_target_seconds": tail,
            "planned_frame_upper_bound": bound, "max_frames": max_frames}


def selection_filter(plan, origin, decoded_timing):
    start = origin + plan["start_seconds"]
    every = plan["every_seconds"]
    # A decoded frame is taken from every nonempty interval bucket. VFR gaps
    # never produce synthetic frames. An exact last-frame target covers the tail.
    # FFmpeg evaluates decimal seconds as doubles: e.g. 0.3 / 0.1 can fall just
    # below 3. Stabilize bucket boundaries by a billionth of a bucket, without
    # rounding the decoded timestamps written to evidence.
    first_pts = decoded_timing["first_frame_in_requested_range_pts"]
    last_pts = decoded_timing["last_frame_in_requested_range_pts"]
    # Gate the range using decoded integer PTS, avoiding a second floating-point
    # comparison of exact boundaries such as 3.4 seconds inside FFmpeg.
    expr = (f"gte(pts,{first_pts})*lte(pts,{last_pts})*"
            f"(isnan(prev_selected_t)+"
            f"gt(floor((t-({start:.17g}))/{every:.17g}+1e-9),"
            f"floor((prev_selected_t-({start:.17g}))/{every:.17g}+1e-9))+"
            f"eq(pts,{last_pts}))")
    return (f"settb=expr={decoded_timing['time_base']},select='{expr}',"
            "scale=w='max(2,trunc(iw*sar/2)*2)':h=ih,setsar=1,"
            "scale=w='min(1280,iw)':h=-2,showinfo")


def video_timestamps(stderr):
    match = re.search(r"\[Parsed_showinfo_\d+[^\]]*\] config in time_base:\s*(\d+/\d+)", stderr)
    if not match or not rational(match.group(1)):
        raise PreparationError("FFmpeg did not report the decoded video time base")
    base = rational(match.group(1))
    records = []
    for line in stderr.splitlines():
        if "Parsed_showinfo_" not in line:
            continue
        match = re.search(r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:", line)
        if match:
            dimensions = re.search(r"\bs:(\d+)x(\d+)\b", line)
            records.append({"decoded_pts": int(match.group(2)), "time_base": str(base),
                            "absolute_pts_seconds": float(int(match.group(2)) * base),
                            "image_width": int(dimensions.group(1)) if dimensions else None,
                            "image_height": int(dimensions.group(2)) if dimensions else None})
    return records


def audio_mapping(stderr, origin, wav_samples):
    blocks = []
    for line in stderr.splitlines():
        if "Parsed_ashowinfo_" not in line:
            continue
        match = re.search(r"\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:.*?\bnb_samples:\s*(\d+)", line)
        if match:
            blocks.append((int(match.group(1)), int(match.group(2))))
    if sum(count for _, count in blocks) != wav_samples:
        raise PreparationError("Decoded audio sample count does not match WAV; cannot establish timestamp mapping")
    segments = []
    wav_cursor = 0
    previous_end = None
    for pts, count in blocks:
        if count <= 0:
            continue
        if segments and pts == previous_end:
            segments[-1]["sample_count"] += count
            segments[-1]["duration_seconds"] = segments[-1]["sample_count"] / SAMPLE_RATE
        else:
            segments.append({"wav_start_seconds": wav_cursor / SAMPLE_RATE,
                             "source_start_seconds": pts / SAMPLE_RATE - origin,
                             "sample_count": count, "duration_seconds": count / SAMPLE_RATE,
                             "decoded_start_pts": pts, "time_base": f"1/{SAMPLE_RATE}"})
        previous_end = pts + count
        wav_cursor += count
    return segments


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def prepare(args):
    source = Path(args.input).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    if not source.is_file():
        raise PreparationError(f"Input is not a local file: {source}")
    if out.exists():
        raise PreparationError(f"Output already exists; choose a NEW directory: {out}")
    ffmpeg = find_tool(args.ffmpeg, "ffmpeg")
    ffprobe = find_tool(args.ffprobe, "ffprobe")
    initial_stat = source.stat()
    source_hash = sha256(source)
    probe_run = run([ffprobe, "-v", "error", "-protocol_whitelist", "file", "-show_format", "-show_streams", "-of", "json", str(source)])
    try:
        probe = json.loads(probe_run.stdout)
    except json.JSONDecodeError as exc:
        raise PreparationError("FFprobe returned invalid JSON") from exc
    video, audio, metadata_origin, metadata_origin_basis, metadata_duration, metadata_duration_basis = metadata(probe)
    fps = rational(video.get("avg_frame_rate")) or rational(video.get("r_frame_rate"))
    start = finite_number(args.start, "--start", minimum=0)
    requested_end = None if args.end is None else finite_number(args.end, "--end", minimum=0)
    # Validate inputs before the timestamp scan, then enforce the cap against the
    # decoded range before any image/audio extraction is attempted.
    every = finite_number(args.every, "--every", minimum=0)
    if every <= 0 or args.max_frames < 1 or (requested_end is not None and requested_end <= start):
        raise PreparationError("Require --every > 0, --max-frames >= 1, and --end > --start")
    decoded_timing = decoded_video_timing(ffprobe, source, video, start, requested_end, fps)
    probe["decoded_video_timing"] = decoded_timing
    origin, origin_basis = decoded_timing["origin_seconds"], decoded_timing["origin_basis"]
    duration, duration_basis = decoded_timing["duration_seconds"], decoded_timing["duration_basis"]
    end = duration if requested_end is None else requested_end
    if end > duration + 1e-6:
        raise PreparationError(f"--end ({end}) exceeds reported video duration ({duration})")
    end = min(end, duration)
    plan = sampling_plan(start, end, every, args.max_frames, fps, decoded_timing["last_frame_in_requested_range_seconds"])
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{out.name}.prepare-video-", dir=out.parent))
    try:
        (stage / "frames").mkdir()
        write_json(stage / "probe.json", probe)
        video_run = run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "info", "-xerror", "-n", "-copyts",
                         "-protocol_whitelist", "file", "-i", str(source), "-map", f"0:{video['index']}", "-an", "-sn", "-dn",
                         "-vf", selection_filter(plan, origin, decoded_timing), "-fps_mode", "vfr",
                         "-frames:v", str(args.max_frames + 1), "-q:v", "2",
                         str(stage / "frames" / "frame-%06d.jpg")])
        timestamps = video_timestamps(video_run.stderr)
        frame_files = sorted((stage / "frames").glob("frame-*.jpg"))
        if not frame_files:
            raise PreparationError("No decoded video frames fall in the requested range")
        if len(frame_files) != len(timestamps):
            raise PreparationError("Image count does not match decoded PTS count; timestamps cannot be trusted")
        if len(frame_files) > args.max_frames or len(frame_files) > plan["planned_frame_upper_bound"]:
            raise PreparationError("Actual extracted frame count exceeded the planned bound")
        frames = []
        for index, (path, timing) in enumerate(zip(frame_files, timestamps), 1):
            source_time = timing["absolute_pts_seconds"] - origin
            if not (plan["start_seconds"] - 1e-6 <= source_time < end + 1e-6):
                raise PreparationError("Decoded frame PTS fell outside the requested range")
            frames.append({"id": f"frame-{index:06d}", "file": path.relative_to(stage).as_posix(),
                           "source_time_seconds": source_time, "timestamp_kind": "decoded_pts",
                           **timing})
        if any(b["source_time_seconds"] <= a["source_time_seconds"] for a, b in zip(frames, frames[1:])):
            raise PreparationError("Video has non-increasing presentation timestamps; review manually")
        if (abs(frames[0]["source_time_seconds"] - decoded_timing["first_frame_in_requested_range_seconds"]) > 1e-6
                or abs(frames[-1]["source_time_seconds"] - decoded_timing["last_frame_in_requested_range_seconds"]) > 1e-6):
            raise PreparationError("Extracted images did not cover the first and last decoded frames in range")
        audio_info = {"present": audio is not None, "stream_index": audio.get("index") if audio else None,
                      "status": "no_audio_stream" if audio is None else "pending", "listened": False}
        if audio is not None:
            audio_path = stage / "audio.wav"
            audio_filter = (f"aresample={SAMPLE_RATE},asettb=1/{SAMPLE_RATE},"
                            f"atrim=start={origin + plan['start_seconds']:.17g}:end={origin + end:.17g},"
                            "ashowinfo,asetpts=PTS-STARTPTS")
            audio_run = run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "info", "-xerror", "-n", "-copyts",
                             "-protocol_whitelist", "file", "-i", str(source), "-map", f"0:{audio['index']}", "-vn", "-sn", "-dn",
                             "-af", audio_filter, "-ar", str(SAMPLE_RATE), "-ac", "1",
                             "-c:a", "pcm_s16le", str(audio_path)])
            with wave.open(str(audio_path), "rb") as wav:
                wav_samples = wav.getnframes()
            segments = audio_mapping(audio_run.stderr, origin, wav_samples)
            if not wav_samples:
                audio_path.unlink()
                audio_info["status"] = "no_decoded_samples_in_requested_range"
            else:
                audio_info.update({"status": "extracted", "file": "audio.wav", "sample_rate": SAMPLE_RATE,
                                   "channels": 1, "sample_count": wav_samples,
                                   "duration_seconds": wav_samples / SAMPLE_RATE,
                                   "wav_zero_source_seconds": segments[0]["source_start_seconds"],
                                   "continuous_source_timeline": len(segments) == 1,
                                   "segments": segments})
        latest_stat = source.stat()
        if (initial_stat.st_size, initial_stat.st_mtime_ns) != (latest_stat.st_size, latest_stat.st_mtime_ns):
            raise PreparationError("Source file changed during extraction; rerun with a stable file")
        sample_times = [frame["source_time_seconds"] for frame in frames]
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "source": {"path": str(source), "sha256": source_hash, "bytes": initial_stat.st_size,
                       "duration_seconds": duration, "duration_basis": duration_basis,
                       "metadata_duration_seconds": metadata_duration, "metadata_duration_basis": metadata_duration_basis,
                       "decoded_frame_count": decoded_timing["decoded_frame_count"],
                       "video_stream_index": video["index"], "width": video["width"], "height": video["height"],
                       "avg_frame_rate": video.get("avg_frame_rate"), "r_frame_rate": video.get("r_frame_rate"),
                       "fps_for_sampling_hint": float(fps) if fps else None,
                       "sample_aspect_ratio": video.get("sample_aspect_ratio"),
                       "display_aspect_ratio": video.get("display_aspect_ratio"),
                       "rotation_metadata": {"tags_rotate": video.get("tags", {}).get("rotate"),
                                             "side_data_list": video.get("side_data_list", [])}},
            "clock": {"name": "source_video_seconds", "origin_absolute_pts_seconds": origin,
                      "origin_basis": origin_basis, "definition": "source_time_seconds = decoded PTS * time_base - origin_absolute_pts_seconds",
                      "metadata_origin_absolute_pts_seconds": metadata_origin, "metadata_origin_basis": metadata_origin_basis,
                      "format_start_time_seconds": optional_number(probe.get("format", {}).get("start_time")),
                      "video_start_time_seconds": optional_number(video.get("start_time")),
                      "video_start_pts": video.get("start_pts"), "video_time_base": video.get("time_base"),
                      "audio_start_time_seconds": optional_number(audio.get("start_time")) if audio else None},
            "sampling": {**plan, "method": "first decoded frame in each nonempty interval bucket plus last decoded frame in range",
                         "actual_frame_count": len(frames), "first_frame_seconds": sample_times[0],
                         "last_frame_seconds": sample_times[-1],
                         "start_gap_seconds": max(0, sample_times[0] - plan["start_seconds"]),
                         "end_gap_seconds": max(0, end - sample_times[-1]),
                         "actual_intervals_seconds": [b - a for a, b in zip(sample_times, sample_times[1:])],
                         "requested_full_duration": plan["start_seconds"] == 0 and end == duration,
                         "first_and_last_decoded_frames_in_range_extracted": True,
                         "all_source_frames_extracted": (plan["start_seconds"] == 0 and end == duration
                                                         and len(frames) == decoded_timing["decoded_frame_count"])},
            "frames": frames, "audio": audio_info,
            "review": {"semantic_analysis_performed": False, "frames_visually_reviewed": False,
                       "audio_listened": False, "scope": "sampled_frames_and_extracted_audio",
                       "limitations": ["Frame sampling can miss cuts, brief text, actions, flashes, and transitions.",
                                       "Video end duration can be estimated when the final decoded frame has no reported duration; check duration_basis.",
                                       "A full-duration requested range is not proof that the complete video was viewed.",
                                       "Images apply FFmpeg autorotation, normalize pixel aspect ratio, and cap width at 1280px.",
                                       "WAV is mono 16kHz analysis audio; use the original for music, spatial, and quality judgments.",
                                       "No audio stream, no samples in a range, and perceived silence are different states.",
                                       "Use audio segments for timestamp mapping if continuous_source_timeline is false."]},
            "tools": {"ffmpeg": ffmpeg, "ffprobe": ffprobe},
        }
        write_json(stage / "manifest.json", manifest)
        # Exclusive creation prevents an existing directory from being replaced,
        # including a directory created by another process while extraction ran.
        out.mkdir()
        for child in stage.iterdir():
            if child.name != "manifest.json":
                child.rename(out / child.name)
        (stage / "manifest.json").rename(out / "manifest.json")  # Success marker is published last.
        return manifest
    finally:
        shutil.rmtree(stage)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("input", help="Local video file; URLs are not accepted")
    result.add_argument("--out", required=True, help="New output directory; existing paths are refused")
    result.add_argument("--every", type=float, default=1.0, help="Sampling interval in seconds (default: 1)")
    result.add_argument("--start", type=float, default=0.0, help="Start in source-video seconds (inclusive)")
    result.add_argument("--end", type=float, help="End in source-video seconds (exclusive; default: decoded video duration)")
    result.add_argument("--max-frames", type=int, default=240)
    result.add_argument("--ffmpeg", help="FFmpeg executable path, otherwise PATH")
    result.add_argument("--ffprobe", help="FFprobe executable path, otherwise PATH")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        manifest = prepare(args)
    except (PreparationError, OSError, ValueError, wave.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "prepared", "output": str(Path(args.out).expanduser().resolve()),
                      "frame_count": len(manifest["frames"]), "audio_status": manifest["audio"]["status"],
                      "semantic_analysis_performed": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
