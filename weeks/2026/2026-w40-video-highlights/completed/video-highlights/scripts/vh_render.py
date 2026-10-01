#!/usr/bin/env python3
"""Render validated highlight plans with local FFmpeg; Python standard library only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
FORMATS = ("portrait", "landscape", "square", "source")


class RenderError(ValueError):
    """A plan or media check prevented a trustworthy render."""


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RenderError(f"{name} 必須為有限數值")
    return float(value)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command, *, cwd=None, timeout=120):
    """Keep process output on disk and cap reads; never invoke a command shell."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(
                [str(arg) for arg in command], cwd=cwd, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise RenderError(f"工具逾時：{Path(command[0]).name}") from None
        except OSError as exc:
            raise RenderError(f"無法執行 {command[0]}：{exc}") from exc
        stderr.seek(0, 2)
        length = stderr.tell()
        stderr.seek(max(0, length - 8192))
        error = stderr.read(8192).decode("utf-8", errors="replace")
        if code:
            raise RenderError(f"{Path(command[0]).name} 結束碼 {code}：{error.strip()}")
        stdout.seek(0, 2)
        if stdout.tell() > 2 * 1024 * 1024:
            raise RenderError("工具輸出超過 2 MiB 上限")
        stdout.seek(0)
        return stdout.read().decode("utf-8", errors="replace")


def probe(path, ffprobe):
    try:
        return json.loads(run([
            ffprobe, "-v", "error", "-show_entries",
            "format=duration,start_time:stream=index,codec_type,codec_name,width,height,"
            "sample_aspect_ratio,pix_fmt,duration,start_time,avg_frame_rate:"
            "stream_disposition=attached_pic:stream_tags=rotate:stream_side_data=rotation",
            "-of", "json", str(path),
        ]))
    except json.JSONDecodeError as exc:
        raise RenderError("ffprobe 未回傳有效 JSON") from exc


def positive_rational(value, default=1.0):
    if value in (None, "N/A", "0:1", "0/0"):
        return default
    try:
        parts = str(value).replace(":", "/").split("/")
        result = float(parts[0]) / float(parts[1]) if len(parts) == 2 else float(parts[0])
    except (ValueError, ZeroDivisionError):
        raise RenderError(f"無效媒體比例：{value}") from None
    if not math.isfinite(result) or result <= 0:
        raise RenderError(f"無效媒體比例：{value}")
    return result


def media_duration(info):
    value = info.get("format", {}).get("duration")
    if value is None:
        value = next((stream.get("duration") for stream in info.get("streams", [])
                      if stream.get("codec_type") == "video"), None)
    try:
        duration = float(value)
    except (ValueError, TypeError):
        raise RenderError("無法取得媒體時長") from None
    if not math.isfinite(duration) or duration <= 0:
        raise RenderError("媒體時長無效")
    return duration


def display_size(video):
    width = int(video["width"])
    height = int(video["height"])
    sar = positive_rational(video.get("sample_aspect_ratio"))
    rotation = next((item["rotation"] for item in video.get("side_data_list", [])
                     if "rotation" in item), video.get("tags", {}).get("rotate", 0))
    rotation = float(rotation)
    if not math.isfinite(rotation) or abs(rotation / 90 - round(rotation / 90)) > .001:
        raise RenderError("目前僅支援 90 度倍數旋轉；請先製作正規化副本")
    width = max(2, round(width * sar))
    if round(rotation / 90) % 2:
        width, height = height, width
    return width, height


def chosen_stream(info, kind, index=None):
    streams = [stream for stream in info.get("streams", [])
               if stream.get("codec_type") == kind
               and not stream.get("disposition", {}).get("attached_pic", 0)]
    if index is not None:
        streams = [stream for stream in streams if stream.get("index") == index]
    return streams[0] if streams else None


def source_checks(project, plan, ffprobe):
    source = project["source"]
    path = Path(source["path"])
    if not path.is_absolute() or not path.is_file():
        raise RenderError("source.path 須為存在的絕對檔案路徑")
    expected_hash = source.get("sha256")
    if expected_hash != plan.get("source_sha256") or sha256(path) != expected_hash:
        raise RenderError("來源影片 SHA256 與計畫不一致；請重新 prepare")
    info = probe(path, ffprobe)
    video = chosen_stream(info, "video", source.get("video_stream_index"))
    audio = chosen_stream(info, "audio", source.get("audio_stream_index"))
    if video is None:
        raise RenderError("找不到計畫指定的視訊軌")
    if not isinstance(source.get("has_audio"), bool) or bool(audio) != source["has_audio"]:
        raise RenderError("來源音軌狀態與 project.json 不一致")
    for label, item in (("容器", info.get("format", {})), ("視訊", video), ("音訊", audio)):
        if item and item.get("start_time") not in (None, "N/A"):
            value = float(item["start_time"])
            if not math.isfinite(value) or abs(value) > .1:
                raise RenderError(f"{label} 起點超出 0.1 秒；請先製作同步確認過的正規化副本")
    duration = media_duration(info)
    if abs(duration - number(source["duration"], "source.duration")) > .15:
        raise RenderError("來源影片時長與 project.json 不一致")
    width, height = display_size(video)
    if abs(width - int(source["width"])) > 2 or abs(height - int(source["height"])) > 2:
        raise RenderError("來源顯示尺寸與 project.json 不一致")
    # Explicit display dimensions avoid relying on SAR inversion during autorotation.
    return path, info, video, audio, duration, width, height


def canvas(format_name, height, display_width, display_height):
    ratios = {"portrait": 9 / 16, "landscape": 16 / 9, "square": 1,
              "source": display_width / display_height}
    return max(2, round(height * ratios[format_name] / 2) * 2), height


def srt_time(milliseconds):
    hours, value = divmod(milliseconds, 3600000)
    minutes, value = divmod(value, 60000)
    seconds, milliseconds = divmod(value, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def clip_subtitles(segments, start, end):
    cues = []
    maximum = math.floor((end - start) * 1000 + .00001)
    for segment in segments:
        left = max(start, number(segment["start"], "字幕 start"))
        right = min(end, number(segment["end"], "字幕 end"))
        if right <= left:
            continue
        a = max(0, round((left - start) * 1000))
        b = min(maximum, round((right - start) * 1000))
        text = str(segment["text"]).replace("\r\n", "\n").replace("\r", "\n").strip()
        if b > a and text:
            cues.append(f"{len(cues) + 1}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n")
    return "\n".join(cues)


def crossing_subtitle_cues(segments, start, end):
    """A cue can overlap a cut without word timestamps; retain an explicit review flag."""
    crossed = []
    for segment in segments:
        left = number(segment["start"], "字幕 start")
        right = number(segment["end"], "字幕 end")
        if min(right, end) <= max(left, start):
            continue
        boundaries = []
        if left < start < right:
            boundaries.append("start")
        if left < end < right:
            boundaries.append("end")
        if boundaries:
            crossed.append({"segment_id": segment.get("id"), "source_start": left,
                            "source_end": right, "crosses": boundaries})
    return crossed


def framing_filter(candidate, width, height, source_width, source_height):
    framing = candidate.get("framing", {"mode": "pad"})
    mode = framing.get("mode", "pad")
    normalized = f"scale={source_width}:{source_height},setsar=1"
    if mode == "pad":
        return (f"{normalized},scale={width}:{height}:force_original_aspect_ratio=decrease:"
                f"force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")
    if mode != "crop":
        raise RenderError("framing.mode 只能為 pad 或 crop")
    review = candidate.get("review", {})
    if review.get("visual") not in ("sampled", "watched") or not review.get("evidence"):
        raise RenderError("crop 需要視覺檢視紀錄與證據")
    if not str(framing.get("reason", "")).strip():
        raise RenderError("crop 需要取景理由")
    x = number(framing.get("x"), "crop.x")
    y = number(framing.get("y"), "crop.y")
    if not 0 <= x <= 1 or not 0 <= y <= 1:
        raise RenderError("crop.x/y 必須介於 0 與 1")
    return (f"{normalized},scale={width}:{height}:force_original_aspect_ratio=increase:"
            f"force_divisible_by=2,crop={width}:{height}:(iw-ow)*{x:.6f}:(ih-oh)*{y:.6f},setsar=1")


def verify_output(path, ffprobe, width, height, expected_duration, has_audio):
    info = probe(path, ffprobe)
    video = chosen_stream(info, "video")
    audio = chosen_stream(info, "audio")
    if not video or (video.get("width"), video.get("height")) != (width, height):
        raise RenderError(f"輸出尺寸驗證失敗：{path.name}")
    if video.get("codec_name") != "h264" or video.get("pix_fmt") != "yuv420p":
        raise RenderError(f"輸出視訊編碼驗證失敗：{path.name}")
    if abs(positive_rational(video.get("sample_aspect_ratio")) - 1) > .001:
        raise RenderError(f"輸出像素比例驗證失敗：{path.name}")
    if bool(audio) != has_audio or (audio and audio.get("codec_name") != "aac"):
        raise RenderError(f"輸出音軌驗證失敗：{path.name}")
    fps = positive_rational(video.get("avg_frame_rate"), default=25)
    tolerance = max(.15, 2 / fps)
    duration = media_duration(info)
    if abs(duration - expected_duration) > tolerance:
        raise RenderError(f"輸出時長驗證失敗：{path.name} ({duration:.3f}s / {expected_duration:.3f}s)")
    starts = {}
    for label, stream in (("video", video), ("audio", audio)):
        if stream and stream.get("start_time") not in (None, "N/A"):
            starts[label] = float(stream["start_time"])
            if abs(starts[label]) > tolerance:
                raise RenderError(f"輸出 {label} 起點異常：{path.name}")
    if len(starts) == 2 and abs(starts["video"] - starts["audio"]) > tolerance:
        raise RenderError(f"輸出音畫起點不同步：{path.name}")
    return {"width": width, "height": height, "duration": duration,
            "video_codec": video["codec_name"], "pixel_format": video["pix_fmt"],
            "has_audio": bool(audio), "audio_codec": audio["codec_name"] if audio else None,
            "stream_start_times": starts, "bytes": path.stat().st_size,
            "duration_tolerance": tolerance}


def load_validated_plan(path):
    from vh_plan import validate_plan
    return validate_plan(path)


def write_json(path, data):
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def render(args):
    plan_path = Path(args.plan).resolve()
    plan, project = load_validated_plan(plan_path)
    if not Path(plan["project"]).is_absolute():
        raise RenderError("plan.project 須為絕對路徑")
    if args.height < 64 or args.height > 4320 or args.height % 2:
        raise RenderError("--height 須為 64 至 4320 之間的偶數")
    if len(set(args.formats)) != len(args.formats):
        raise RenderError("--formats 不可重複")
    source_path, source_info, video, audio, duration, sw, sh = source_checks(project, plan, args.ffprobe)
    selected = plan.get("selected", [])
    if not selected:
        raise RenderError("plan 沒有可輸出的 selected 片段")
    ids = set()
    for candidate in selected:
        identifier = candidate.get("id", "")
        if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier) or identifier in ids:
            raise RenderError("片段 ID 須為唯一且安全的英數字、底線或連字號")
        ids.add(identifier)
        start = number(candidate["start"], "片段 start")
        end = number(candidate["end"], "片段 end")
        if not 0 <= start < end <= duration + .001:
            raise RenderError(f"片段時間超出來源範圍：{identifier}")
        # Check framing before creating any output directory.
        framing_filter(candidate, 640, 360, sw, sh)
    if args.burn_subtitles and not re.search(r"\bsubtitles\s+V", run([args.ffmpeg, "-hide_banner", "-filters"])):
        raise RenderError("此 FFmpeg 缺少 subtitles/libass；請改用含 libass 的版本或省略 --burn-subtitles")
    out = Path(args.out).resolve()
    try:
        out.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise RenderError("--out 必須為尚未存在的新目錄，避免覆蓋既有輸出") from None
    metadata = out / "metadata"
    metadata.mkdir()
    report = {"schema_version": 1, "status": "rendering", "plan": str(plan_path),
              "project": plan["project"], "source_sha256": plan["source_sha256"],
              "review_status": plan.get("status", "partial"),
              "human_audiovisual_signoff": False,
              "subtitle_boundary_notice": "跨切點字幕僅調整時間，保留整句文字；缺少逐字時間，請回聽並修正跨界文字或調整切點。",
              "files": []}
    source_stat = source_path.stat()
    try:
        for candidate in selected:
            start, end = float(candidate["start"]), float(candidate["end"])
            subtitles = clip_subtitles(project["transcript"]["segments"], start, end)
            crossing_cues = crossing_subtitle_cues(project["transcript"]["segments"], start, end)
            for format_name in args.formats:
                basename = f"{candidate['id']}-{format_name}"
                output_file = out / f"{basename}.mp4"
                subtitle_file = out / f"{basename}.srt"
                with subtitle_file.open("x", encoding="utf-8", newline="\n") as handle:
                    handle.write(subtitles)
                width, height = canvas(format_name, args.height, sw, sh)
                filters = framing_filter(candidate, width, height, sw, sh)
                if args.burn_subtitles and subtitles:
                    # Safe relative name + cwd avoids Windows drive-colon filter escaping.
                    filters += f",subtitles={subtitle_file.name}"
                command = [args.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                           "-ss", f"{start:.9f}", "-i", str(source_path), "-t", f"{end-start:.9f}",
                           "-map", f"0:{video['index']}"]
                if audio:
                    command += ["-map", f"0:{audio['index']}"]
                command += ["-map_metadata", "-1", "-map_chapters", "-1", "-vf", filters,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
                if audio:
                    command += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
                else:
                    command += ["-an"]
                command += ["-movflags", "+faststart", str(output_file)]
                run(command, cwd=out, timeout=max(120, (end-start) * 30))
                specs = verify_output(output_file, args.ffprobe, width, height, end-start, bool(audio))
                report["files"].append({"id": candidate["id"], "title": candidate["title"],
                    "format": format_name, "video": output_file.name, "subtitles": subtitle_file.name,
                    "subtitles_burned": bool(args.burn_subtitles and subtitles),
                    "crossing_subtitle_cues": crossing_cues,
                    "subtitle_boundary_review_required": bool(crossing_cues),
                    "source_start": start, "source_end": end, "score": candidate["score"],
                    "scores": candidate["scores"], "review_status": candidate.get("review_status", "partial"),
                    "review": candidate.get("review", {}), "unresolved": candidate.get("unresolved", []),
                    "framing": candidate.get("framing", {"mode": "pad"}),
                    "status": "verified", "specifications": specs})
        current_stat = source_path.stat()
        if (current_stat.st_size, current_stat.st_mtime_ns) != (source_stat.st_size, source_stat.st_mtime_ns) or sha256(source_path) != plan["source_sha256"]:
            raise RenderError("來源檔案於輸出期間變更；本次結果不可視為完成")
        report["status"] = "rendered"
        write_json(metadata / "render.json", report)
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        write_json(metadata / "render.failed.json", report)
        raise
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="將已驗證的 Video Highlights 計畫剪輯為本機 MP4 與字幕")
    parser.add_argument("plan", help="plan.json")
    parser.add_argument("--out", required=True, help="尚未存在的新輸出目錄")
    parser.add_argument("--formats", nargs="+", choices=FORMATS, default=["portrait", "landscape"])
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--burn-subtitles", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = render(args)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "review_status": result["review_status"],
                      "files": len(result["files"]), "report": str(Path(args.out).resolve() / "metadata" / "render.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
