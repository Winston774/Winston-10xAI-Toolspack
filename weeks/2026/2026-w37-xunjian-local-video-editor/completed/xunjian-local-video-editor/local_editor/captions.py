"""SRT/WebVTT import and timeline-aware subtitle export, without dependencies."""
from __future__ import annotations

import html
import re
import uuid

from .core import EditorError, mapped_captions


def _seconds(value: str) -> float:
    match = re.fullmatch(r"(?:(\d{1,4}):)?(\d{2}):(\d{2})[,.](\d{3})", value.strip())
    if not match:
        raise EditorError(f"無效的字幕時間碼：{value}")
    hours, minutes, seconds, milliseconds = match.groups()
    if int(minutes) > 59 or int(seconds) > 59:
        raise EditorError(f"無效的字幕時間碼：{value}")
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000


def parse_captions(text: str, format: str = "srt", media_id: str | None = None) -> list[dict]:
    if not isinstance(text, str) or len(text) > 20_000_000:
        raise EditorError("字幕文字格式錯誤或檔案過大。")
    format = format.lower().lstrip(".")
    if format not in ("srt", "vtt", "webvtt"):
        raise EditorError("字幕匯入支援 SRT 與 VTT。")
    content = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    if content.startswith("WEBVTT"):
        lines = content.split("\n")
        lines.pop(0)
        content = "\n".join(lines).strip()
    if not content:
        return []
    captions = []
    for block in re.split(r"\n\s*\n", content):
        lines = block.strip().splitlines()
        if not lines:
            continue
        if format in ("vtt", "webvtt") and re.match(r"^(NOTE(?:\s|$)|STYLE$|REGION$)", lines[0]):
            continue
        timing_index = next((i for i, line in enumerate(lines[:2]) if "-->" in line), None)
        if timing_index is None:
            if format in ("vtt", "webvtt") and all(":" in line for line in lines):
                continue  # Optional WebVTT header metadata.
            raise EditorError("字幕區塊缺少有效的時間碼。")
        timing = re.fullmatch(r"\s*(\S+)\s+-->\s+(\S+)(?:\s+.*)?", lines[timing_index])
        if not timing:
            raise EditorError("字幕時間碼格式錯誤。")
        start, end = _seconds(timing.group(1)), _seconds(timing.group(2))
        if end <= start:
            raise EditorError("字幕終點必須晚於起點。")
        caption_text = "\n".join(lines[timing_index + 1:]).strip()
        # Imported subtitle markup is text content, never an HTML execution surface.
        caption_text = html.unescape(re.sub(r"<[^>]*>", "", caption_text))
        item = {"id": uuid.uuid4().hex, "start": start, "end": end, "text": caption_text}
        if media_id is not None:
            item["media_id"] = media_id
        captions.append(item)
    return sorted(captions, key=lambda c: (c["start"], c["end"]))


def _timestamp(seconds: float, separator: str) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}{separator}{millis:03}"


def export_captions(project: dict | list[dict], format: str = "srt") -> str:
    """Accept a project (maps source timings) or an already mapped caption list."""
    format = format.lower().lstrip(".")
    if format not in ("srt", "vtt", "webvtt", "txt"):
        raise EditorError("字幕匯出支援 SRT、VTT 與 TXT。")
    captions = mapped_captions(project) if isinstance(project, dict) else project
    if format == "txt":
        return "\n".join(c["text"] for c in captions) + ("\n" if captions else "")
    blocks = []
    separator = "," if format == "srt" else "."
    for index, caption in enumerate(captions, 1):
        start_ms, end_ms = round(caption["start"] * 1000), round(caption["end"] * 1000)
        if end_ms <= start_ms:
            continue
        # Escape cue markup so user-entered angle brackets remain visible text.
        text = html.escape(caption["text"], quote=False)
        blocks.append(f"{index}\n{_timestamp(caption['start'], separator)} --> {_timestamp(caption['end'], separator)}\n{text}")
    prefix = "WEBVTT\n\n" if format in ("vtt", "webvtt") else ""
    return prefix + "\n\n".join(blocks) + ("\n" if blocks else "")


def parse_srt(text: str, media_id: str | None = None) -> list[dict]:
    return parse_captions(text, "srt", media_id)


def parse_vtt(text: str, media_id: str | None = None) -> list[dict]:
    return parse_captions(text, "vtt", media_id)


def export_srt(project: dict | list[dict]) -> str:
    return export_captions(project, "srt")


def export_vtt(project: dict | list[dict]) -> str:
    return export_captions(project, "vtt")
