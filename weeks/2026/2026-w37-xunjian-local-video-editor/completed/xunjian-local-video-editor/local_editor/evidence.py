"""Bounded, real audiovisual evidence using the export renderer and local ASR.

Manifests deliberately carry paths only at this internal service boundary. The
HTTP/MCP service registers opaque resources before returning them to an Agent.
No visual semantics are inferred from pixel change or low-volume detection.
"""
from __future__ import annotations

import array
import copy
import difflib
import hashlib
import math
import sys
import uuid
import wave
from pathlib import Path
from typing import Callable

from .captions import mapped_captions
from .media_engine import MediaError, _number, _run, _tool, probe, render_project, transcription


UNKNOWN = {
    "ocr": {"status": "unknown", "reason": "未執行畫面文字辨識；可直接查看對應影格。"},
    "people": {"status": "unknown", "reason": "未執行人物或人物區域辨識。"},
    "cursor_actions": {"status": "unknown", "reason": "像素變化無法證明游標、捲動或教學操作。"},
    "semantic_edit_value": {"status": "unknown", "reason": "音量與像素變化不代表可以刪除；需檢視聲畫與敘事意圖。"},
    "auditory_naturalness": {"status": "unknown", "reason": "音訊已提供，尚未經聽覺判斷。"},
}


def _request(project: dict, request: dict) -> dict:
    time_space = request.get("time_space", "timeline")
    if time_space not in {"timeline", "source"}:
        raise ValueError("time_space 必須是 timeline 或 source。")
    media = None
    if time_space == "source":
        media = next((m for m in project.get("media", []) if m["id"] == request.get("media_id")), None)
        if media is None:
            raise ValueError("來源觀察需要有效的 media_id。")
        duration = float(media["duration"])
    else:
        duration = max([float(c.get("offset", 0)) + (float(c["end"]) - float(c["start"])) /
                        float(c.get("speed", 1)) for c in project.get("clips", [])] +
                       [float(t["end"]) for t in project.get("titles", [])] + [0])
    span = request.get("range")
    if not isinstance(span, dict) or "start" not in span or "end" not in span:
        raise ValueError("觀察必須指定 range.start 與 range.end，最多 30 秒。")
    start = _number(span["start"], 0, 0, duration, "觀察起點")
    end = _number(span["end"], duration, 0, duration, "觀察終點")
    if not 0 < end - start <= 30:
        raise ValueError("觀察區間必須大於零且不超過 30 秒。")
    detail = request.get("detail", "summary")
    if detail not in {"summary", "review"}:
        raise ValueError("detail 必須是 summary 或 review。")
    max_frames = _number(request.get("max_frames"), 4 if detail == "summary" else 8, 1, 8, "影格上限")
    if max_frames != int(max_frames):
        raise ValueError("影格上限必須是整數。")
    includes = request.get("include", ["frames", "audio"])
    if not isinstance(includes, list) or not all(isinstance(item, str) for item in includes):
        raise ValueError("include 必須是字串陣列。")
    allowed = {"frames", "composite_frames", "audio", "video", "transcript", "layers", "cut_boundaries"}
    if set(includes) - allowed:
        raise ValueError("include 包含未支援的證據種類。")
    includes = set(includes)
    if "composite_frames" in includes:
        includes.add("frames")
    from .contracts import SAMPLING, validate
    sampling = request.get("sampling", {"strategy": "uniform"})
    validate(sampling, SAMPLING, "sampling")
    if time_space != "timeline" and (sampling["strategy"] == "cut_boundaries" or request.get("scan_black_frames")):
        raise ValueError("切點取樣與黑畫面掃描僅支援 timeline")
    return {"time_space": time_space, "range": {"start": start, "end": end}, "media": media,
            "include": includes, "detail": detail, "max_frames": int(max_frames), "duration": end - start,
            "sampling": sampling, "scan_black_frames": request.get("scan_black_frames", False)}


def _directory(output_dir: str | Path) -> Path:
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    directory = root / ("evidence-" + uuid.uuid4().hex)
    directory.mkdir()
    return directory


def _file(path: Path, kind: str, mime: str, **extra) -> dict:
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"id": uuid.uuid4().hex, "kind": kind, "path": str(path.resolve()), "mime_type": mime,
            "size": path.stat().st_size, "sha256": digest, **extra}


def _source_preview(media: dict, span: dict, directory: Path, audio_only: bool = False) -> tuple[Path, bool]:
    """Normalize a bounded source interval; no project overlays are applied."""
    output = directory / "source.mp4"
    duration = span["end"] - span["start"]
    args = [_tool("ffmpeg"), "-v", "error", "-nostdin", "-n"]
    if media.get("kind") == "image":
        args += ["-loop", "1", "-framerate", "24"]
    args += ["-ss", f"{span['start']:.8f}", "-t", f"{duration:.8f}", "-protocol_whitelist", "file,pipe",
             "-i", str(Path(media["path"]).resolve())]
    if media.get("kind") == "audio" or audio_only:
        output = directory / "source.wav"
        args += ["-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"]
    else:
        args += ["-map", "0:v:0", "-map", "0:a:0?", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-movflags", "+faststart"]
    args += ["-t", f"{duration:.8f}", str(output)]
    _run(args, timeout=240)
    return output, bool(media.get("has_audio"))


def _compose(project: dict, selection: dict, directory: Path, report: Callable | None) -> tuple[Path, bool, dict]:
    if selection["time_space"] == "timeline":
        result = render_project(project, directory, {"range": selection["range"], "preset": "ultrafast", "crf": 18}, report)
        return Path(result["path"]), True, {
            "renderer": "render_project", "same_composition_rules_as_export": True,
            "composition_resolution": {"width": result["width"], "height": result["height"]},
            "caption_layout": "project_pixels_via_same_libass", "burn_captions": True,
            "differences_from_default_export": ["H.264 使用 ultrafast／CRF 18；編碼像素可能有些微差異。",
                                                 "觀察區間以外不渲染；輸出的音訊編碼邊界可能有些微差異。"],
            "audio_processing": {"denoise": False, "normalize_audio": False},
        }
    audio_only = selection["media"].get("has_audio") and not selection["include"].intersection({"frames", "video"})
    path, has_audio = _source_preview(selection["media"], selection["range"], directory, bool(audio_only))
    return path, has_audio, {"renderer": "source_extract", "same_composition_rules_as_export": False,
                             "caption_layout": "source_only", "burn_captions": False,
                             "differences_from_default_export": ["來源證據保留素材畫面；未套用時間軸圖層、字幕或效果。"]}


def _evidence(project: dict, selection: dict, directory: Path, report: Callable | None) -> tuple[dict, Path]:
    path, has_audio, parity = _compose(project, selection, directory, report)
    start, end = selection["range"]["start"], selection["range"]["end"]
    manifest = {"schema_version": "editor.evidence.v1", "project_id": project.get("id"),
                "project_version": project.get("version"), "time_space": selection["time_space"],
                "range": selection["range"], "media_id": (selection["media"] or {}).get("id"),
                "detail": selection["detail"], "files": [], "render_parity": parity,
                "unknowns": copy.deepcopy(UNKNOWN), "coverage": {"audio": "not_requested", "video": "not_requested",
                                                               "frames": "not_requested", "max_duration_seconds": 30}}
    visual = selection["time_space"] == "timeline" or selection["media"].get("kind") != "audio"
    if selection["scan_black_frames"]:
        from .cut_review import scan_black_frames
        manifest["black_scan"] = scan_black_frames(path, project, selection)
        manifest["findings"] = manifest["black_scan"]["findings"]
    if "video" in selection["include"]:
        if visual:
            manifest["files"].append(_file(path, "video", "video/mp4", range=selection["range"], has_audio=has_audio))
            manifest["coverage"]["video"] = "complete_requested_range"
        else:
            manifest["coverage"]["video"] = "unavailable_audio_only_source"
    if "frames" in selection["include"]:
        if visual:
            # Midpoints of equal-duration bins avoid a repeated final frame and preserve provenance.
            count = selection["max_frames"]
            fps = float(project.get("fps", 30)) if selection["time_space"] == "timeline" else float(selection["media"].get("fps") or 24)
            samples = sorted(set(min(selection["duration"] - .0001, math.floor((index + .5) *
                                  selection["duration"] / count * fps) / fps) for index in range(count)))
            frame_samples = [{"relative_time": relative} for relative in samples]
            if selection["sampling"]["strategy"] == "cut_boundaries":
                from .cut_review import sample_cuts
                frame_samples, manifest["sampling"] = sample_cuts(project, selection)
            if manifest.get("findings"):
                # Keep anomaly frames visible even when equal-distance sampling misses them.
                anomalies = [{"relative_time": f["time"] - start, "index": f["frame_index_start"],
                              "finding_id": f["id"]} for f in manifest["findings"]]
                combined, seen = [], set()
                for sample in anomalies + frame_samples:
                    key = round(sample["relative_time"], 7)
                    if key not in seen:
                        combined.append(sample)
                        seen.add(key)
                    elif sample.get("cut_refs"):
                        next(s for s in combined if round(s["relative_time"], 7) == key)["cut_refs"] = sample["cut_refs"]
                frame_samples = sorted(combined[:selection["max_frames"]], key=lambda s: s["relative_time"])
                manifest.setdefault("sampling", {"strategy": selection["sampling"]["strategy"]})
                manifest["sampling"].update(anomaly_priority=True, candidate_frame_count=len(combined),
                    omitted_candidate_frames=max(0, len(combined)-len(frame_samples)),
                    retained_cut_frame_count=sum(bool(s.get("cut_refs")) for s in frame_samples))
            for sample in frame_samples:
                if "index" in sample and manifest.get("black_scan") and sample["index"] >= manifest["black_scan"]["decoded_frame_count"]:
                    manifest.setdefault("sampling", {})["unrendered_frame_omitted"] = True
                    continue
                relative = sample["relative_time"]
                frame = directory / f"frame-{len(manifest['files']):02d}.jpg"
                args = [_tool("ffmpeg"), "-v", "error", "-nostdin", "-n"]
                if "index" not in sample:
                    args += ["-ss", f"{relative:.8f}"]
                frame_filter = (f"select=eq(n\\,{sample['index']})," if "index" in sample else "") + "scale=min(960\\,iw):-2"
                _run(args + ["-i", str(path), "-frames:v", "1", "-vf", frame_filter, "-q:v", "2", str(frame)], timeout=60)
                from .cut_review import frame_map
                manifest["files"].append(_file(frame, "image", "image/jpeg", time=round(start + relative, 8),
                                                relative_time=round(relative, 8), max_width=960,
                                                cut_refs=sample.get("cut_refs", []), finding_id=sample.get("finding_id"),
                                                source_mapping=frame_map(project, start + relative) if selection["time_space"] == "timeline" else [],
                                                timing_precision_seconds=round(1 / fps, 8)))
            manifest["coverage"]["frames"] = "sampled_only"
            manifest["coverage"]["frame_times"] = [f["time"] for f in manifest["files"] if f["kind"] == "image"]
            for finding in manifest.get("findings", []):
                finding["file_ids"] = [f["id"] for f in manifest["files"] if f.get("finding_id") == finding["id"]]
        else:
            manifest["coverage"]["frames"] = "unavailable_audio_only_source"
    if "audio" in selection["include"]:
        if has_audio:
            audio = directory / "listen.wav"
            _run([_tool("ffmpeg"), "-v", "error", "-nostdin", "-n", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                  "-t", f"{selection['duration']:.8f}", "-c:a", "pcm_s16le", str(audio)], timeout=60)
            manifest["files"].append(_file(audio, "audio", "audio/wav", range=selection["range"],
                                            channels=1, sample_rate=16000, processing="mono_16khz_review_copy"))
            manifest["coverage"]["audio"] = "complete_requested_range"
        else:
            manifest["coverage"]["audio"] = "unavailable_no_source_audio"
    return manifest, path


def inspect_media(project: dict, request: dict, output_dir: Path,
                  progress_callback: Callable | None = None) -> dict:
    selection = _request(project, request)
    manifest, _ = _evidence(project, selection, _directory(output_dir), progress_callback)
    return manifest


def _sound_signal(path: Path, selection: dict, options: dict) -> dict:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        samples = array.array("h", handle.readframes(handle.getnframes()))
        if sys.byteorder != "little":
            samples.byteswap()
    threshold = _number(options.get("threshold_db"), -35, -80, -5, "靜音門檻")
    min_pause = _number(options.get("min_silence"), .5, .1, 10, "最短停頓")
    bucket = max(1, int(rate * .02))
    rms = [math.sqrt(sum(float(v) ** 2 for v in samples[i:i + bucket]) / len(samples[i:i + bucket])) / 32768
           for i in range(0, len(samples), bucket)]
    start, end = selection["range"]["start"], selection["range"]["end"]
    quiet = [20 * math.log10(max(value, 1e-8)) < threshold for value in rms]
    pauses = []
    beginning = None
    for index, low in enumerate(quiet + [False]):
        if low and beginning is None:
            beginning = index
        if not low and beginning is not None:
            left, right = start + beginning * .02, min(end, start + index * .02)
            if right - left >= min_pause - 1e-8:
                pauses.append({"id": f"pause-{beginning}", "range": {"start": round(left, 4), "end": round(right, 4)},
                               "duration": round(right - left, 4), "detection_status": "measured_low_volume",
                               "edit_safety": "unknown", "requires_audiovisual_review": True})
            beginning = None
    chart_stride = max(1, math.ceil(len(rms) / 120))
    return {"method": "20ms_RMS_on_rendered_mono_audio", "threshold_db": threshold, "min_pause_seconds": min_pause,
            "range": selection["range"], "measurement_window_seconds": .02, "pauses": pauses,
            "low_volume_seconds": round(sum(quiet) * .02, 4),
            "non_silent_audio_seconds": round(sum(not value for value in quiet) * .02, 4),
            "speech_activity": {"status": "unknown", "reason": "未執行聲音分類；非靜音可能是語音、音樂或噪音。"},
            "waveform": {"range": selection["range"], "bucket_seconds": .02 * chart_stride,
                         "rms": [round(max(rms[i:i + chart_stride]), 5) for i in range(0, len(rms), chart_stride)]}}


def _visual_signal(path: Path, selection: dict, options: dict) -> dict:
    threshold = _number(options.get("visual_change_threshold"), .1, .001, 1, "畫面變化門檻")
    raw = _run([_tool("ffmpeg"), "-v", "error", "-i", str(path), "-an", "-vf", "fps=2,scale=160:90,format=gray",
                "-t", f"{selection['duration']:.8f}", "-f", "rawvideo", "pipe:1"], timeout=120, binary=True).stdout
    frame_size = 160 * 90
    frames = [raw[i:i + frame_size] for i in range(0, len(raw) - frame_size + 1, frame_size)]
    changes = []
    for index in range(1, len(frames)):
        score = sum(abs(a - b) for a, b in zip(frames[index - 1], frames[index])) / (255 * frame_size)
        if score >= threshold:
            changes.append({"time": round(selection["range"]["start"] + index * .5, 4),
                            "mean_absolute_pixel_difference": round(score, 5), "semantic_meaning": "unknown"})
    return {"method": "mean_absolute_difference_160x90_gray", "sample_fps": 2, "threshold": threshold,
            "sample_count": len(frames), "events": changes, "coverage": "sampled_only",
            "limitations": ["可能漏掉短於 0.5 秒的動作。", "鏡頭、字幕、游標或壓縮雜訊都可能造成變化。",
                            "低變化分數無法證明畫面沒有重要教學內容。"]}


def analyze_media(project: dict, request: dict, output_dir: Path,
                  progress_callback: Callable | None = None) -> dict:
    selection = _request(project, request)
    selection["include"].update({"frames", "audio"})
    manifest, path = _evidence(project, selection, _directory(output_dir), progress_callback)
    options = request.get("options") or {}
    audio = next((item for item in manifest["files"] if item["kind"] == "audio"), None)
    analysis = {"range": selection["range"], "audio": _sound_signal(Path(audio["path"]), selection, options)
                if audio else {"status": "unavailable", "reason": "來源沒有音軌。"},
                "visual_changes": _visual_signal(path, selection, options) if
                selection["time_space"] == "timeline" or selection["media"].get("kind") != "audio"
                else {"status": "unavailable", "reason": "來源只有音訊。"},
                "semantic_repeat_detection": {"status": "unknown", "reason": "未執行跨段語意重錄判斷。"}}
    cues = mapped_captions(project) if selection["time_space"] == "timeline" else [
        item for item in project.get("captions", []) if item.get("media_id") == selection["media"]["id"]]
    intersecting = [item for item in cues if item["start"] < selection["range"]["end"] and item["end"] > selection["range"]["start"]]
    analysis["caption_metrics"] = {"cue_count": len(intersecting), "character_count": sum(len(item["text"]) for item in intersecting),
                                   "source": "authored_or_asr_transcript", "speech_rate_status": "approximate_transcript_only"}
    manifest["analysis"] = analysis
    return manifest


def review_caption(project: dict, request: dict, output_dir: Path,
                   progress_callback: Callable | None = None) -> dict:
    caption_id = request.get("caption_id")
    caption = next((item for item in project.get("captions", []) if item["id"] == caption_id), None)
    if caption is None:
        raise ValueError("字幕複核需要有效的 caption_id。")
    media = next((item for item in project.get("media", []) if item["id"] == caption.get("media_id")), None)
    if media is None:
        raise ValueError("字幕來源素材不存在。")
    if not media.get("has_audio"):
        raise ValueError("字幕來源沒有音軌，無法進行語音複核。")
    options = dict(request.get("options") or {})
    padding = _number(options.pop("padding", request.get("padding")), .35, 0, 2, "複核前後文")
    span = {"start": max(0, float(caption["start"]) - padding), "end": min(float(media["duration"]), float(caption["end"]) + padding)}
    selection = _request(project, {"time_space": "source", "media_id": media["id"], "range": span,
                                  "include": ["audio"], "detail": "review"})
    directory = _directory(output_dir)
    manifest, _ = _evidence(project, selection, directory, progress_callback)
    audio = next(item for item in manifest["files"] if item["kind"] == "audio")
    if progress_callback:
        progress_callback({"progress": .25, "message": "正在複核指定句子的本機語音；原字幕保留不變。"})
    fresh = transcription({"id": media["id"], "path": audio["path"], "has_audio": True,
                           "duration": selection["duration"]}, options, directory)
    proposal = []
    timing_adjustments = []
    for cue in fresh:
        item = copy.deepcopy(cue)
        raw_start, raw_end = cue["start"] + span["start"], cue["end"] + span["start"]
        item["start"] = round(max(span["start"], raw_start), 4)
        item["end"] = round(min(span["end"], raw_end), 4)
        if item["end"] <= item["start"]:
            timing_adjustments.append({"caption_id": cue["id"], "reason": "辨識句子完全位於擷取區間外，已排除。"})
            continue
        if raw_start < span["start"] or raw_end > span["end"]:
            timing_adjustments.append({"caption_id": cue["id"], "reason": "辨識估計超出擷取區間，已截至證據邊界。"})
        words = []
        for index, word in enumerate(item.get("words", [])):
            word["start"] = round(max(item["start"], word["start"] + span["start"]), 4)
            word["end"] = round(min(item["end"], word["end"] + span["start"]), 4)
            if word["end"] > word["start"]:
                word.setdefault("id", "word-" + hashlib.sha256(f"{item['id']}:{index}".encode()).hexdigest()[:24])
                words.append(word)
        item["words"] = words
        item["alignment_status"] = "asr_estimated"
        if item["start"] < caption["end"] and item["end"] > caption["start"]:
            proposal.append(item)
    proposed_text = "".join(item["text"] for item in proposal)
    manifest["caption_id"] = caption_id
    manifest["authored"] = copy.deepcopy(caption)
    manifest["proposal"] = {"captions": proposal, "text": proposed_text, "time_space": "source", "media_id": media["id"],
                            "applied": False, "requires_review": True, "includes_padding_context": bool(padding)}
    manifest["comparison"] = {"authored_text": caption["text"], "proposed_text": proposed_text,
                               "changed": proposed_text != caption["text"],
                               "character_similarity": round(difflib.SequenceMatcher(None, caption["text"], proposed_text).ratio(), 4),
                               "similarity_is_accuracy": False}
    manifest["alignment"] = {"status": "proposal_only", "method": "local_whisper_word_timestamps",
                              "forced_alignment": "unsupported", "authored_text_realigned": False,
                              "timing_adjustments": timing_adjustments,
                              "note": "重新辨識附帶估計詞級時間；未對原稿做強制對齊，也未自動套用任何修改。"}
    if progress_callback:
        progress_callback({"progress": 1, "message": "局部語音複核完成；請檢閱候選文字與音訊。"})
    return manifest
