"""Frame-addressed observations; pixel candidates never imply editorial mistakes."""
from __future__ import annotations

import hashlib
import json
import math

from .media_engine import _run, _tool
from .understanding import cut_boundaries


def frame_map(project, time):
    placements = []
    for clip in project["clips"]:
        speed = clip.get("speed", 1)
        if clip["offset"] <= time < clip["offset"] + (clip["end"] - clip["start"]) / speed:
            placements.append({"clip_id": clip["id"], "media_id": clip["media_id"],
                "track": clip.get("track", "video"),
                "source_time": round(clip["start"] + (time - clip["offset"]) * speed, 8)})
    return placements


def sample_cuts(project, selection):
    fps = float(project["fps"])
    start, end = selection["range"]["start"], selection["range"]["end"]
    offsets = selection["sampling"].get("offset_frames", [-2, -1, 0, 1, 2])
    cuts = [cut for cut in cut_boundaries(project, selection["range"])
            if any(edge["track"] != "audio" for edge in cut["left"] + cut["right"])]
    candidates = {}
    # The partial render's frame grid begins at range.start, not project zero.
    for cut in cuts:
        base = math.ceil((cut["at"] - start) * fps - 1e-7)
        for offset in offsets:
            index = base + offset
            time = start + index / fps
            if index >= 0 and time < end - 1e-7:
                candidates.setdefault(index, []).append({"cut_id": cut["id"], "cut_time": cut["at"], "offset_frames": offset})
    # Prioritize the seam, then its closest neighbours. Always report omitted frames.
    ranked = sorted(candidates, key=lambda i: (min(abs(c["offset_frames"]) for c in candidates[i]), i))
    chosen = sorted(ranked[:selection["max_frames"]])
    return [{"index": i, "relative_time": i / fps, "cut_refs": candidates[i]} for i in chosen], {
        "strategy": "cut_boundaries", "cut_count": len(cuts), "requested_frame_count": len(candidates),
        "omitted_frame_count": max(0, len(candidates) - len(chosen)), "selected_frame_count": len(chosen),
        "note": "僅取樣所選區間內的切點；未選影格與區間外仍未確認。"}


def scan_black_frames(path, project, selection):
    """Decode every preview frame, measuring dark pixel fraction at 160x90.

    Timestamps come from the same decoded stream. No temporal downsampling.
    Spatial reduction and threshold are explicit limitations of this detector.
    """
    raw = _run([_tool("ffmpeg"), "-v", "error", "-i", str(path), "-map", "0:v:0",
        "-vf", "scale=160:90,format=gray", "-vsync", "0", "-f", "rawvideo", "pipe:1"],
        binary=True, timeout=120).stdout
    timing = _run([_tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)], timeout=120)
    timestamps = [float(f["best_effort_timestamp_time"]) for f in json.loads(timing.stdout)["frames"]]
    size = 160 * 90
    if not timestamps or len(raw) != size * len(timestamps):
        raise ValueError("解碼影格與時間戳數量不符，無法完成逐影格掃描")
    frame_duration = 1 / float(project["fps"])
    if (abs(timestamps[0]) > frame_duration or any(b <= a for a, b in zip(timestamps, timestamps[1:]))
            or timestamps[-1] + 2 * frame_duration < selection["duration"] - 1e-6):
        raise ValueError("解碼時間戳未完整覆蓋要求區間，無法通過逐影格掃描")
    # FFmpeg may round a fractional range down to whole output frames. Expose
    # the measured interval so an assertion cannot certify an unrendered tail.
    measured_end = min(selection["range"]["end"], selection["range"]["start"] + timestamps[-1] + frame_duration)
    findings, dark = [], []
    start = selection["range"]["start"]
    for index, pts in enumerate(timestamps):
        pixels = raw[index * size:(index + 1) * size]
        fraction = sum(value <= 24 for value in pixels) / size
        if fraction >= .98:
            dark.append((index, pts, fraction))
    groups = []
    for item in dark:
        if not groups or item[0] != groups[-1][-1][0] + 1:
            groups.append([])
        groups[-1].append(item)
    for group in groups:
        first, last = group[0], group[-1]
        time = start + first[1]
        end = min(selection["range"]["end"], start + (timestamps[last[0]+1]
            if last[0]+1 < len(timestamps) else last[1]+1/float(project["fps"])))
        mapping = []
        for _, pts, _ in group:
            for placement in frame_map(project, start + pts):
                if placement["clip_id"] not in {m["clip_id"] for m in mapping}:
                    mapping.append(placement)
        findings.append({"id": "finding-" + hashlib.sha256(f"{project['id']}:{project['version']}:{time}".encode()).hexdigest()[:20],
            "code": "black_frame_candidate", "severity": "warning", "time_space": "timeline",
            "time": round(time, 8), "range": {"start": round(time, 8), "end": round(end, 8)},
            "project_version": project["version"], "target_ids": [m["clip_id"] for m in mapping],
            "source_mapping": mapping, "bbox": [0, 0, project["width"], project["height"]],
            "frame_index_start": first[0], "frame_count": len(group), "dark_fraction_min": min(x[2] for x in group),
            "measurement": "decoded_pixels", "review_status": "unreviewed",
            "message": "偵測到近黑影格；請確認是否為刻意淡出或剪點異常。"})
    return {"status": "completed", "range": {"start": selection["range"]["start"] + timestamps[0], "end": measured_end},
        "requested_range": selection["range"], "uncovered_tail_seconds": max(0, selection["range"]["end"] - measured_end),
        "decoded_frame_count": len(timestamps),
        "temporal_sampling": "every_decoded_frame", "spatial_resolution": [160, 90],
        "pixel_threshold": 24, "dark_fraction_threshold": .98,
        "candidate_count": len(findings), "findings": findings[:100], "truncated": len(findings) > 100,
        "naturalness": "unchecked", "surface": "export_compositor_preview",
        "limitations": "僅檢查合成區間的近黑像素；不判定敘事、音訊、局部遮擋或即時 UI 播放。"}
