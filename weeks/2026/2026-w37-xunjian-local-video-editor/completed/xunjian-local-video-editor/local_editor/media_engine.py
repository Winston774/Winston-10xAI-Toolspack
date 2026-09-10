"""Local media operations. Sources are copied, edits remain declarative, exports are unique.

Only FFmpeg/FFprobe and optional locally installed Whisper are executed. No shell,
cloud endpoint or model download is used by this module.
"""
from __future__ import annotations

import array
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable

from agent_video_editor.media import tool_path


class MediaError(RuntimeError):
    """An actionable local media failure, safe to expose in the workbench."""


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
FILLERS = {"嗯", "嗯嗯", "呃", "呃呃", "啊", "那個", "就是", "然後"}


def _local_model(work_dir: str | Path | None = None) -> Path | None:
    """Discover complete local assets only; never contact a model registry."""
    candidates = []
    configured = os.environ.get("LOCAL_EDITOR_MODEL_PATH")
    if configured:
        candidates.append(Path(configured).expanduser())
    roots = [Path(__file__).resolve().parent.parent / ".local-editor", Path.cwd() / ".local-editor"]
    if work_dir:
        roots.extend(Path(work_dir).resolve().parents[:3])
    for root in roots:
        candidates.extend(root / "models" / f"faster-whisper-{name}" for name in ("small", "base", "tiny"))
    for candidate in candidates:
        if all((candidate / filename).is_file() for filename in ("model.bin", "config.json", "tokenizer.json")):
            if (candidate / "model.bin").stat().st_size >= 10_000_000:
                return candidate.resolve()
    return None


def _number(value: Any, default: float, low: float, high: float, name: str) -> float:
    try:
        number = float(default if value is None else value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}必須是數字。") from exc
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"{name}必須介於 {low:g} 與 {high:g}。")
    return number


def _run(args: list[str], *, timeout: float = 120, cwd: Path | None = None,
         binary: bool = False, env: dict | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(args, shell=False, capture_output=True,
                                text=not binary, encoding=None if binary else "utf-8",
                                errors=None if binary else "replace", timeout=timeout,
                                cwd=cwd, env=env)
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"本機處理超過 {timeout:g} 秒，已停止；請縮短片段或提高逾時設定。") from exc
    except OSError as exc:
        raise MediaError(f"無法啟動本機處理工具：{exc}") from exc
    if result.returncode:
        error = result.stderr.decode("utf-8", "replace") if binary else result.stderr
        raise MediaError(f"本機媒體處理失敗：{error[-3500:].strip()}")
    return result


def _tool(name: str) -> str:
    executable = tool_path(name)
    if not executable:
        raise MediaError(f"找不到 {name}；請安裝 FFmpeg，或設定 AGENT_VIDEO_{name.upper()}。")
    return executable


def doctor() -> dict:
    result: dict[str, Any] = {}
    for name in ("ffmpeg", "ffprobe"):
        executable = tool_path(name)
        info = {"available": False, "path": executable, "version": None}
        if executable:
            try:
                version = _run([executable, "-version"], timeout=10)
                info.update(available=True, version=version.stdout.splitlines()[0])
            except MediaError as exc:
                info["error"] = str(exc)
        result[name] = info
    installed = bool(importlib.util.find_spec("faster_whisper"))
    local_model = _local_model()
    result["transcription"] = {
        "available": installed,
        "backend": "faster-whisper" if installed else None,
        "whisperx_installed": bool(importlib.util.find_spec("whisperx")),
        "local_files_only": True,
        "model_ready": bool(local_model),
        "model_path": str(local_model) if local_model else None,
        "traditional_chinese": bool(importlib.util.find_spec("opencc")),
        "note": ("已找到本機模型，預設 CPU int8，支援離線字幕辨識。" if local_model else
                 "尚未找到工作台模型；請執行 scripts/setup-local-asr.ps1 或指定 model_path。") if installed else
                "目前 Python 未安裝 faster-whisper；請使用已安裝的 .venv，或安裝選用辨識套件。",
    }
    result["ready"] = result["ffmpeg"]["available"] and result["ffprobe"]["available"]
    return result


def probe(path: str | Path) -> dict:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError("找不到媒體檔案。")
    output = _run([_tool("ffprobe"), "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams",
                   "-of", "json", str(source)], timeout=30)
    try:
        info = json.loads(output.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError("FFprobe 回傳的媒體資訊無法解析。") from exc
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video and not audio:
        raise MediaError("檔案未包含可使用的影像或聲音。")
    image = source.suffix.lower() in IMAGE_EXTENSIONS and video is not None
    duration = info.get("format", {}).get("duration")
    if not duration:
        duration = max((float(s.get("duration", 0) or 0) for s in streams), default=0)
    fps = 0.0
    if video:
        numerator, _, denominator = str(video.get("avg_frame_rate", "0/1")).partition("/")
        try:
            fps = float(numerator) / float(denominator or 1) if float(denominator or 1) else 0.0
        except ValueError:
            pass
    return {"kind": "image" if image else "video" if video else "audio",
            "duration": 5.0 if image else round(float(duration or 0), 6),
            "width": int(video.get("width", 0)) if video else 0,
            "height": int(video.get("height", 0)) if video else 0,
            "has_audio": bool(audio), "fps": round(fps, 4),
            "video_codec": video.get("codec_name") if video else None,
            "audio_codec": audio.get("codec_name") if audio else None,
            "size": source.stat().st_size}


def import_media(path: str | Path, asset_dir: str | Path) -> dict:
    source = Path(path).expanduser().resolve()
    metadata = probe(source)
    directory = Path(asset_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    asset_id = uuid.uuid4().hex
    target = directory / f"{asset_id}{source.suffix.lower()}"
    shutil.copy2(source, target)
    media = {"id": asset_id, "name": source.name, "path": str(target), **metadata}
    if metadata["kind"] in {"video", "image"}:
        thumbnail = directory / f"{asset_id}.thumb.jpg"
        try:
            _run([_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
                  "-n", "-protocol_whitelist", "file,pipe", "-i", str(target), "-frames:v", "1", "-vf", "scale=320:-2",
                  "-q:v", "4", str(thumbnail)], timeout=60)
            media["thumbnail"] = str(thumbnail)
        except MediaError as exc:
            media["thumbnail_error"] = str(exc)
    if metadata["has_audio"]:
        try:
            # Downsample to 1 kHz mono; bounded decoding prevents large allocations.
            raw = _run([_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-protocol_whitelist", "file,pipe", "-i", str(target), "-t", "1800", "-vn", "-ac", "1", "-ar", "1000",
                        "-f", "s16le", "pipe:1"], binary=True, timeout=90).stdout
            samples = array.array("h")
            samples.frombytes(raw)
            if sys.byteorder != "little":
                samples.byteswap()
            bucket = max(1, math.ceil(len(samples) / 240))
            media["waveform"] = [round(max(abs(v) for v in samples[i:i + bucket]) / 32768, 4)
                                 for i in range(0, len(samples), bucket)]
            media["waveform_duration"] = min(metadata["duration"], 1800)
        except MediaError as exc:
            media["waveform_error"] = str(exc)
    return media


def _clean_text(text: Any) -> str:
    return re.sub(r"[\W_]+", "", str(text), flags=re.UNICODE).casefold()


def analyze_speech(media: dict, options: dict | None = None, captions: list | None = None) -> dict:
    options = options or {}
    threshold = _number(options.get("threshold_db"), -35, -80, -5, "靜音門檻")
    min_silence = _number(options.get("min_silence"), .5, .1, 10, "最短停頓")
    keep_pause = _number(options.get("keep_pause"), .2, 0, 5, "保留停頓")
    duration = _number(media.get("duration"), 0, 0, 86400, "媒體長度")
    candidates: list[dict] = []
    silences: list[tuple[float, float]] = []
    warnings = []
    if media.get("has_audio") and options.get("detect_silence", True):
        completed = _run([_tool("ffmpeg"), "-hide_banner", "-nostdin", "-protocol_whitelist", "file,pipe", "-i", str(media["path"]),
                          "-vn", "-af", f"silencedetect=noise={threshold}dB:d={min_silence}",
                          "-f", "null", "-"], timeout=max(120, min(1800, duration * 2)))
        current_start = None
        for line in completed.stderr.splitlines():
            match = re.search(r"silence_start:\s*([-+\d.eE]+)", line)
            if match:
                current_start = max(0, float(match.group(1)))
            match = re.search(r"silence_end:\s*([-+\d.eE]+)", line)
            if match and current_start is not None:
                silences.append((current_start, min(duration, float(match.group(1)))))
                current_start = None
        if current_start is not None:
            silences.append((current_start, duration))
        for start, end in silences:
            trimmed_start = start + keep_pause / 2
            trimmed_end = end - keep_pause / 2
            if trimmed_end - trimmed_start >= .04:
                candidates.append({"kind": "silence", "start": round(trimmed_start, 4),
                                   "end": round(trimmed_end, 4), "text": "",
                                   "detection": {"method": "ffmpeg_silencedetect", "threshold_db": threshold,
                                                 "observed_range": {"start": start, "end": end},
                                                 "duration": round(end - start, 4), "status": "measured"},
                                   "edit_assessment": {"status": "requires_review", "confidence": None,
                                                       "unknowns": ["畫面操作意義", "停頓的敘事用途", "刪除後聲音自然度"]},
                                   "reason": f"音量低於 {threshold:g} dB，停頓 {end - start:.2f} 秒；保留 {keep_pause:g} 秒銜接。"})
    elif not media.get("has_audio"):
        warnings.append("素材沒有音軌，未執行停頓偵測。")
    source_captions = sorted([c for c in (captions or []) if c.get("media_id") in (None, media.get("id"))],
                             key=lambda c: float(c.get("start", 0)))
    previous = None
    for caption in source_captions:
        start = max(0, float(caption.get("start", 0)))
        end = min(duration, float(caption.get("end", 0)))
        text = str(caption.get("text", ""))
        cleaned = _clean_text(text)
        kind = None
        if options.get("detect_fillers", True) and cleaned in FILLERS and end - start <= 2:
            kind = "filler"
            reason = "整段字幕只有語助詞；請試聽確認語意後套用。"
        elif options.get("detect_repeats", True) and previous and cleaned and cleaned == previous[0] and 0 <= start - previous[1] <= 1.2:
            kind = "repeat"
            reason = "相鄰字幕文字完全相同；請確認是否為刻意強調。"
        if kind and end > start:
            candidates.append({"kind": kind, "start": round(start, 4), "end": round(end, 4),
                               "text": text, "reason": reason,
                               "detection": {"method": "exact_caption_rule", "status": "matched", "rule": kind},
                               "edit_assessment": {"status": "requires_review", "confidence": None,
                                                   "unknowns": ["字幕辨識是否正確", "刻意強調或語意用途", "刪除後聲音自然度"]}})
        previous = (cleaned, end)
    candidates.sort(key=lambda c: (c["start"], c["end"], c["kind"]))
    for index, candidate in enumerate(candidates):
        candidate["id"] = f"cut_{index + 1}_{uuid.uuid4().hex[:8]}"
    merged: list[list[float]] = []
    for candidate in candidates:
        if merged and candidate["start"] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], candidate["end"])
        else:
            merged.append([candidate["start"], candidate["end"]])
    removed = sum(end - start for start, end in merged)
    return {"media_id": media.get("id"), "duration": duration, "candidates": candidates,
            "candidate_count": len(candidates), "estimated_removed_seconds": round(removed, 4),
            "estimated_duration": round(max(0, duration - removed), 4), "warnings": warnings,
            "method": "FFmpeg 靜音偵測 + 字幕精確規則", "requires_review": True,
            "options": {"threshold_db": threshold, "min_silence": min_silence, "keep_pause": keep_pause}}


def transcription(media: dict, options: dict | None, work_dir: str | Path) -> list[dict]:
    options = dict(options or {})
    if not media.get("has_audio"):
        raise ValueError("素材沒有音軌，無法產生語音字幕。")
    if not importlib.util.find_spec("faster_whisper"):
        raise MediaError("目前 Python 未安裝 faster-whisper；請使用專案 .venv 或安裝選用辨識套件。")
    model_path = options.get("model_path")
    if not model_path:
        discovered = _local_model(work_dir)
        if discovered:
            model_path = options["model_path"] = str(discovered)
    if model_path and not Path(model_path).expanduser().is_dir():
        raise ValueError("model_path 必須是已存在的本機 Whisper 模型資料夾。")
    directory = Path(work_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    request_path = directory / f"transcription-{token}.request.json"
    output_path = directory / f"transcription-{token}.json"
    request_path.write_text(json.dumps({"path": str(Path(media["path"]).resolve()),
                                       "options": options}, ensure_ascii=False), encoding="utf-8")
    environment = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent) + os.pathsep + environment.get("PYTHONPATH", "")
    timeout = _number(options.get("timeout"), 1800, 30, 14400, "辨識逾時")
    try:
        _run([sys.executable, "-m", "local_editor.media_engine", "_transcribe",
              str(request_path), str(output_path)], timeout=timeout, env=environment)
        captions = json.loads(output_path.read_text(encoding="utf-8"))
    except MediaError as exc:
        raise MediaError("本機語音辨識未完成。請確認模型已存於本機快取，或指定 model_path；不會自動下載模型。" + str(exc)) from exc
    finally:
        request_path.unlink(missing_ok=True)
    for item in captions:
        item["id"] = uuid.uuid4().hex
        item["media_id"] = media["id"]
    return captions


def _transcribe_worker(request_path: Path, output_path: Path) -> None:
    from faster_whisper import WhisperModel
    request = json.loads(request_path.read_text(encoding="utf-8"))
    options = request["options"]
    model = WhisperModel(options.get("model_path") or options.get("model", "small"),
                         device=options.get("device", "cpu"),
                         compute_type=options.get("compute_type", "int8"),
                         local_files_only=True, cpu_threads=int(options.get("cpu_threads", 4)))
    language = options.get("language", "zh")
    segments, _ = model.transcribe(request["path"], language=None if language == "auto" else language,
                                   beam_size=int(options.get("beam_size", 5)),
                                   vad_filter=True, word_timestamps=True,
                                   initial_prompt=options.get("initial_prompt", "以下內容使用繁體中文。"))
    result = [{"start": round(s.start, 4), "end": round(s.end, 4), "text": s.text.strip(),
               "words": [{"start": round(w.start, 4), "end": round(w.end, 4), "text": w.word,
                          **({"probability": round(float(w.probability), 4)} if getattr(w, "probability", None) is not None else {})}
                         for w in (s.words or [])]} for s in segments if s.text.strip()]
    if options.get("traditional_chinese", True) and importlib.util.find_spec("opencc"):
        from opencc import OpenCC
        converter = OpenCC("s2t")
        for caption in result:
            caption["text"] = converter.convert(caption["text"])
            for word in caption["words"]:
                word["text"] = converter.convert(word["text"])
    output_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


def _atempo(speed: float) -> str:
    parts = []
    while speed > 2:
        parts.append("atempo=2")
        speed /= 2
    while speed < .5:
        parts.append("atempo=0.5")
        speed *= 2
    parts.append(f"atempo={speed:.8f}")
    return ",".join(parts)


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{cs:02}"


def _ass_color(value: str, default: str = "#ffffff") -> str:
    value = value if re.fullmatch(r"#[0-9a-fA-F]{6}", str(value)) else default
    return "&H00" + value[5:7] + value[3:5] + value[1:3]


def _ass_text(text: str) -> str:
    # Do not allow subtitle text to inject ASS override tags or drawing commands.
    return str(text).replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\r", "").replace("\n", "\\N")


def _write_ass(project: dict, path: Path, width: int, height: int, burn_captions: bool = True,
               time_origin: float = 0, range_end: float | None = None) -> bool:
    from .captions import mapped_captions
    # ASS coordinates stay in project pixels; libass scales them with export resolution.
    width = int(project.get("width", width))
    height = int(project.get("height", height))
    style = project.get("caption_style") or {}
    font_size = _number(style.get("font_size"), 48, 8, 250, "字幕字級")
    alignment = {"bottom": 2, "center": 5, "top": 8}.get(style.get("position"), 2)
    color = _ass_color(style.get("color", "#ffffff"))
    background = _ass_color(style.get("background", "#000000"), "#000000")
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
             "WrapStyle: 0", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             f"Style: Caption,Microsoft JhengHei,{font_size},{color},{color},&H00000000,{background},-1,0,0,0,100,100,0,0,3,2,0,{alignment},30,30,{max(20, int(height * .055))},1",
             f"Style: Title,Microsoft JhengHei,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,5,30,30,30,1",
             "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    count = 0
    if burn_captions:
        for caption in mapped_captions(project):
            start, end = float(caption["start"]), float(caption["end"])
            start, end = max(0, start - time_origin), end - time_origin
            if range_end is not None:
                end = min(end, range_end - time_origin)
            if end > start:
                lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{_ass_text(caption['text'])}")
                count += 1
    for title in project.get("titles", []):
        start = float(title.get("start", 0))
        end = float(title.get("end", start + float(title.get("duration", 3))))
        start, end = max(0, start - time_origin), end - time_origin
        if range_end is not None:
            end = min(end, range_end - time_origin)
        if end <= start or not title.get("text"):
            continue
        size = _number(title.get("font_size"), 64, 8, 300, "標題字級")
        x = width / 2 + _number(title.get("x"), 0, -width * 4, width * 4, "標題 X")
        y = height / 2 + _number(title.get("y"), 0, -height * 4, height * 4, "標題 Y")
        tag = "{\\pos(" + f"{x:g},{y:g}" + ")\\fs" + f"{size:g}\\c{_ass_color(title.get('color', '#ffffff'))}" + "}"
        lines.append(f"Dialogue: 1,{_ass_time(start)},{_ass_time(end)},Title,,0,0,0,,{tag}{_ass_text(title['text'])}")
        count += 1
    if count:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return bool(count)


def render_project(project: dict, output_dir: str | Path, options: dict | None = None,
                   progress_callback: Callable[[dict], None] | None = None) -> dict:
    """Render declarative source trims onto a real MP4 timeline with FFmpeg.

    Video clips and overlays compose in list order; overlays always stack above video.
    Gain and time stretching apply before mix; silent inputs and gaps get silent audio.
    """
    options = options or {}
    def report(progress: float, message: str) -> None:
        if progress_callback:
            progress_callback({"progress": progress, "message": message})
    width = int(_number(options.get("width", project.get("width")), 1920, 128, 7680, "輸出寬度"))
    height = int(_number(options.get("height", project.get("height")), 1080, 128, 4320, "輸出高度"))
    width, height = width // 2 * 2, height // 2 * 2
    fps = _number(options.get("fps", project.get("fps")), 30, 1, 120, "影格率")
    crf = int(_number(options.get("crf"), 20, 0, 51, "CRF"))
    preset = options.get("preset", "veryfast")
    if preset not in {"ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"}:
        raise ValueError("不支援的編碼 preset。")
    media_by_id = {item["id"]: item for item in project.get("media", [])}
    clips = []
    duration = 0.0
    for raw in project.get("clips", []):
        if raw.get("media_id") not in media_by_id:
            raise ValueError("時間軸引用了不存在的素材。")
        media = media_by_id[raw["media_id"]]
        if not Path(media["path"]).is_file():
            raise ValueError(f"素材檔案不存在：{media.get('name', media['id'])}")
        clip = dict(raw)
        clip["start"] = _number(raw.get("start"), 0, 0, 86400, "來源起點")
        clip["end"] = _number(raw.get("end"), media["duration"], 0, 86400, "來源終點")
        if clip["end"] <= clip["start"]:
            raise ValueError("片段終點必須晚於起點。")
        if media.get("kind") != "image" and clip["end"] > float(media["duration"]) + .1:
            raise ValueError("片段終點超過素材長度。")
        clip["speed"] = _number(raw.get("speed"), 1, .1, 16, "播放速度")
        clip["offset"] = _number(raw.get("offset"), 0, 0, 86400, "時間軸位置")
        clip["duration"] = (clip["end"] - clip["start"]) / clip["speed"]
        clip["media"] = media
        duration = max(duration, clip["offset"] + clip["duration"])
        clips.append(clip)
    if not clips:
        raise ValueError("時間軸沒有片段，無法輸出。")
    for title in project.get("titles", []):
        duration = max(duration, _number(title.get("end"), 0, 0, 86400, "標題終點"))
    if duration > 14400:
        raise ValueError("單次輸出最長 4 小時，請將專案拆分。")
    full_duration = duration
    render_range = options.get("range")
    origin = 0.0
    if render_range is not None:
        if not isinstance(render_range, dict):
            raise ValueError("預覽區間必須包含 start 與 end。")
        origin = _number(render_range.get("start"), 0, 0, full_duration, "預覽起點")
        range_end = _number(render_range.get("end"), full_duration, 0, full_duration, "預覽終點")
        if range_end <= origin or range_end - origin > 30:
            raise ValueError("預覽區間必須大於零且不得超過 30 秒。")
        duration = range_end - origin
        bounded_clips = []
        for clip in clips:
            left, right = max(origin, clip["offset"]), min(range_end, clip["offset"] + clip["duration"])
            if right <= left:
                continue
            elapsed = left - clip["offset"]
            clip["original_duration"] = clip["duration"]
            clip["elapsed"] = elapsed
            clip["start"] += elapsed * clip["speed"]
            clip["end"] = clip["start"] + (right - left) * clip["speed"]
            clip["offset"] = left - origin
            clip["duration"] = right - left
            bounded_clips.append(clip)
        clips = bounded_clips
    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    export_id = uuid.uuid4().hex
    output_path = directory / f"export-{export_id}.mp4"
    timeout = _number(options.get("timeout"), max(180, min(14400, duration * 30)), 10, 28800, "輸出逾時")
    report(.02, "正在準備影像、聲音與字幕軌。")
    with tempfile.TemporaryDirectory(prefix="render-", dir=directory) as temporary:
        work = Path(temporary)
        args = [_tool("ffmpeg"), "-hide_banner", "-loglevel", "warning", "-nostdin", "-n",
                "-filter_complex_threads", "2", "-f", "lavfi", "-i",
                f"color=c=black:s={width}x{height}:r={fps}:d={duration:.6f}",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        filters = [f"[0:v]format=yuv420p[base0]", f"[1:a]atrim=duration={duration:.6f},asetpts=PTS-STARTPTS[abase]"]
        audio_labels = ["abase"]
        visual_clips = []
        for index, clip in enumerate(clips, 2):
            media = clip["media"]
            if media.get("kind") == "image":
                args += ["-loop", "1", "-framerate", str(fps)]
            args += ["-ss", f"{clip['start']:.6f}", "-t", f"{clip['end'] - clip['start']:.6f}",
                     "-protocol_whitelist", "file,pipe", "-i", str(Path(media["path"]).resolve())]
            speed, offset, length = clip["speed"], clip["offset"], clip["duration"]
            elapsed, original_length = clip.get("elapsed", 0), clip.get("original_duration", length)
            volume = _number(clip.get("volume"), 1, 0, 8, "音量")
            fade_in = _number(clip.get("fade_in"), 0, 0, 600, "淡入")
            fade_out = _number(clip.get("fade_out"), 0, 0, 600, "淡出")
            if media.get("has_audio") and not clip.get("muted") and volume:
                audio = [f"[{index}:a]asetpts=PTS-STARTPTS", _atempo(speed),
                         "aresample=48000", "aformat=channel_layouts=stereo"]
                if options.get("denoise", False):
                    audio.append("afftdn=nf=-25")
                audio += [f"volume={volume:.6f}",
                         f"apad=whole_dur={length:.6f}", f"atrim=duration={length:.6f}"]
                if fade_in:
                    # Preserve original clip envelopes when a bounded preview starts mid-fade.
                    duration_in = min(fade_in, original_length)
                    if elapsed:
                        expression = f"min(1,max(0,(t+{elapsed:.8f})/{duration_in:.8f}))"
                        audio.append(f"aeval=exprs='val(0)*{expression}|val(1)*{expression}'")
                    else:
                        audio.append(f"afade=t=in:st=0:d={duration_in:.6f}")
                if fade_out:
                    duration_out = min(fade_out, original_length)
                    fade_start = max(0, original_length - fade_out) - elapsed
                    if fade_start < 0:
                        expression = f"min(1,max(0,({original_length:.8f}-t-{elapsed:.8f})/{duration_out:.8f}))"
                        audio.append(f"aeval=exprs='val(0)*{expression}|val(1)*{expression}'")
                    else:
                        audio.append(f"afade=t=out:st={fade_start:.6f}:d={duration_out:.6f}")
                audio.append(f"adelay={int(round(offset * 1000))}:all=1[a{index}]")
                filters.append(",".join(audio))
                audio_labels.append(f"a{index}")
            if media.get("kind") in {"video", "image"} and clip.get("track", "video") != "audio":
                scale = _number(clip.get("scale"), 1, .05, 4, "縮放")
                brightness = _number(clip.get("brightness"), 0, -1, 1, "亮度")
                contrast = _number(clip.get("contrast"), 1, 0, 3, "對比")
                saturation = _number(clip.get("saturation"), 1, 0, 3, "飽和度")
                rotation = _number(clip.get("rotation"), 0, -360, 360, "旋轉")
                opacity = _number(clip.get("opacity"), 1, 0, 1, "透明度")
                target_width = max(2, int(width * scale) // 2 * 2)
                target_height = max(2, int(height * scale) // 2 * 2)
                video = [f"[{index}:v]setpts=(PTS-STARTPTS)/{speed:.8f}", f"fps={fps}",
                         f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease",
                         "setsar=1", f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}", "format=rgba"]
                if rotation:
                    video.append(f"rotate={rotation}*PI/180:ow=rotw({rotation}*PI/180):oh=roth({rotation}*PI/180):c=none")
                if opacity < 1:
                    video.append(f"colorchannelmixer=aa={opacity}")
                if elapsed and (fade_in or fade_out):
                    video.append(f"setpts=PTS+{elapsed:.8f}/TB")
                if fade_in:
                    video.append(f"fade=t=in:st=0:d={min(fade_in, original_length):.6f}:alpha=1")
                if fade_out:
                    video.append(f"fade=t=out:st={max(0, original_length - fade_out):.6f}:d={min(fade_out, original_length):.6f}:alpha=1")
                if elapsed and (fade_in or fade_out):
                    video.append(f"setpts=PTS-{elapsed:.8f}/TB")
                video.append(f"setpts=PTS+{offset:.6f}/TB[v{index}]")
                filters.append(",".join(video))
                visual_clips.append((index, clip))
        visual_clips.sort(key=lambda item: item[1].get("track") == "overlay")
        last_video = "base0"
        for order, (index, clip) in enumerate(visual_clips, 1):
            canvas_width, canvas_height = project.get("width", width), project.get("height", height)
            x = _number(clip.get("x"), 0, -canvas_width * 4, canvas_width * 4, "影像 X") * width / canvas_width
            y = _number(clip.get("y"), 0, -canvas_height * 4, canvas_height * 4, "影像 Y") * height / canvas_height
            next_video = f"base{order}"
            filters.append(f"[{last_video}][v{index}]overlay=x=(W-w)/2+{x}:y=(H-h)/2+{y}:"
                           f"eof_action=pass:repeatlast=0:enable='gte(t,{clip['offset']:.6f})*lt(t,{clip['offset'] + clip['duration']:.6f})'[{next_video}]")
            last_video = next_video
        caption_file = work / "captions.ass"
        if _write_ass(project, caption_file, width, height, bool(options.get("burn_captions", True)),
                      time_origin=origin, range_end=origin + duration):
            filters.append(f"[{last_video}]ass=filename=captions.ass[vout]")
        else:
            filters.append(f"[{last_video}]null[vout]")
        normalization = ",loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000" if options.get("normalize_audio", False) else ""
        filters.append("".join(f"[{label}]" for label in audio_labels) +
                       f"amix=inputs={len(audio_labels)}:duration=longest:normalize=0:dropout_transition=0{normalization},alimiter=limit=0.95:latency=1,atrim=duration={duration:.6f}[aout]")
        script = work / "timeline.ffgraph"
        script.write_text(";\n".join(filters), encoding="utf-8")
        args += ["-filter_complex_script", str(script), "-map", "[vout]", "-map", "[aout]",
                 "-t", f"{duration:.6f}", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_path)]
        report(.1, "FFmpeg 正在合成時間軸。")
        try:
            _run(args, timeout=timeout, cwd=work)
            result = probe(output_path)
        except Exception:
            output_path.unlink(missing_ok=True)
            raise
    report(1, "MP4 已輸出並通過 FFprobe 驗證。")
    return {"id": export_id, "path": str(output_path), "filename": output_path.name,
            "duration": result["duration"], "width": result["width"], "height": result["height"],
            "has_audio": result["has_audio"], "size": result["size"], "format": "mp4",
            "denoise": bool(options.get("denoise", False)), "normalize_audio": bool(options.get("normalize_audio", False)),
            "burn_captions": bool(options.get("burn_captions", True))}


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "_transcribe":
        try:
            _transcribe_worker(Path(sys.argv[2]), Path(sys.argv[3]))
        except Exception as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1)
    else:
        print(json.dumps(doctor(), ensure_ascii=False, indent=2))
