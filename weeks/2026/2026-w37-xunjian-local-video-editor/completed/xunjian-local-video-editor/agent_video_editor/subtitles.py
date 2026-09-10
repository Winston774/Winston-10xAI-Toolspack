from __future__ import annotations

import html
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .files import write_json, write_text
from .media import tool_path


class SubtitleError(RuntimeError):
    """Raised when subtitles cannot be fetched or written."""


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    duration: float
    text: str


def video_id_from_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.netloc.endswith("youtu.be"):
        candidate = parsed.path.strip("/")
    else:
        candidate = parse_qs(parsed.query).get("v", [""])[0]
    if not re.match(r"^[A-Za-z0-9_-]{11}$", candidate):
        raise SubtitleError(f"Could not determine YouTube video id from: {value}")
    return candidate


def fetch_youtube_html(video_url: str) -> str:
    request = Request(video_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_caption_tracks(video_url: str) -> list[dict[str, Any]]:
    page = fetch_youtube_html(video_url)
    match = re.search(r'"captionTracks":\[(.*?)\]', page)
    if not match:
        return []
    raw = '{"captionTracks":[' + match.group(1) + "]}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SubtitleError("Could not parse caption track metadata from YouTube page.") from exc
    return list(parsed.get("captionTracks", []))


def fetch_transcript_segments(video_id: str, languages: list[str]) -> list[TranscriptSegment]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        return _fetch_transcript_segments_with_ytdlp(video_id, languages, import_error=exc)

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages)
        rows = list(fetched)
    except Exception:
        try:
            rows = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        except Exception as exc:
            return _fetch_transcript_segments_with_ytdlp(video_id, languages, import_error=exc)

    segments: list[TranscriptSegment] = []
    for row in rows:
        if isinstance(row, dict):
            text = str(row.get("text", ""))
            start = float(row.get("start", 0))
            duration = float(row.get("duration", 0))
        else:
            text = str(getattr(row, "text", ""))
            start = float(getattr(row, "start", 0))
            duration = float(getattr(row, "duration", 0))
        cleaned = html.unescape(text).replace("\n", " ").strip()
        if cleaned:
            segments.append(TranscriptSegment(start=start, duration=duration, text=cleaned))
    return segments


def _fetch_transcript_segments_with_ytdlp(
    video_id: str,
    languages: list[str],
    *,
    import_error: BaseException,
) -> list[TranscriptSegment]:
    ytdlp = tool_path("yt-dlp")
    if not ytdlp:
        raise SubtitleError(
            "Could not fetch transcript with youtube-transcript-api, and yt-dlp was not found. "
            "Set YT_DLP_PATH or AGENT_VIDEO_YT_DLP in .env if yt-dlp is installed outside PATH."
        ) from import_error

    with tempfile.TemporaryDirectory(prefix="agent-video-subtitles-", dir=Path.cwd()) as temp_dir:
        temp_path = Path(temp_dir)
        output_template = str(temp_path / "%(id)s.%(ext)s")
        command = [
            ytdlp,
            "--skip-download",
            "--no-playlist",
            "--quiet",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            ",".join(languages),
            "--sub-format",
            "vtt",
            "-o",
            output_template,
            f"https://www.youtube.com/watch?v={video_id}",
        ]
        try:
            completed = subprocess.run(command, text=True, capture_output=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SubtitleError(f"Could not execute yt-dlp at {ytdlp}: {exc}") from import_error
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise SubtitleError(f"yt-dlp could not fetch subtitles for {video_id}: {detail}") from import_error

        vtt_files = sorted(temp_path.glob(f"{video_id}*.vtt"))
        if not vtt_files:
            raise SubtitleError(f"yt-dlp did not produce a VTT subtitle file for {video_id}.") from import_error
        return _parse_vtt(vtt_files[0])


def _parse_vtt(path: Path) -> list[TranscriptSegment]:
    raw_segments: list[TranscriptSegment] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if "-->" not in line:
            index += 1
            continue

        start_text, end_text = line.split("-->", 1)
        start = _seconds_from_vtt_timestamp(start_text.strip())
        end = _seconds_from_vtt_timestamp(end_text.split()[0].strip())
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index].strip())
            index += 1

        text = _clean_vtt_text(" ".join(text_lines))
        if text:
            raw_segments.append(TranscriptSegment(start=start, duration=max(0, end - start), text=text))
        index += 1
    return _dedupe_rolling_segments(raw_segments)


def _clean_vtt_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", value)
    without_entities = html.unescape(without_tags)
    return re.sub(r"\s+", " ", without_entities).strip()


def _dedupe_rolling_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    deduped: list[TranscriptSegment] = []
    emitted_words: list[str] = []
    for segment in segments:
        words = segment.text.split()
        if not words:
            continue
        overlap = _tail_prefix_overlap(emitted_words, words)
        new_words = words[overlap:]
        if not new_words:
            continue
        deduped.append(
            TranscriptSegment(
                start=segment.start,
                duration=segment.duration,
                text=" ".join(new_words),
            )
        )
        emitted_words.extend(new_words)
        if len(emitted_words) > 200:
            emitted_words = emitted_words[-200:]
    return deduped


def _tail_prefix_overlap(previous_words: list[str], current_words: list[str]) -> int:
    limit = min(len(previous_words), len(current_words))
    for size in range(limit, 0, -1):
        if previous_words[-size:] == current_words[:size]:
            return size
    return 0


def _seconds_from_vtt_timestamp(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    elif len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])
    else:
        raise SubtitleError(f"Invalid VTT timestamp: {value}")
    return hours * 3600 + minutes * 60 + seconds


def transcript_summary(video_url: str, *, languages: list[str]) -> dict[str, Any]:
    video_id = video_id_from_url(video_url)
    tracks = extract_caption_tracks(video_url)
    segments = fetch_transcript_segments(video_id, languages)
    text = " ".join(segment.text for segment in segments)
    keywords = {
        "rough_cut": ["rough cut", "whisper", "filler"],
        "graphics": ["graphics", "hyperframes", "motion"],
        "captions": ["caption", "captions"],
        "music": ["background music", "duck", "music"],
        "presets": ["preset", "format", "workflow"],
        "export": ["export", "final", "ship"],
    }
    hits = {
        key: sum(len(re.findall(re.escape(term), text, flags=re.IGNORECASE)) for term in terms)
        for key, terms in keywords.items()
    }
    return {
        "video_id": video_id,
        "source": "youtube_auto_captions",
        "languages_requested": languages,
        "caption_tracks": [
            {
                "languageCode": track.get("languageCode"),
                "name": track.get("name", {}).get("simpleText"),
                "kind": track.get("kind"),
                "isTranslatable": track.get("isTranslatable"),
            }
            for track in tracks
        ],
        "segments": len(segments),
        "characters": len(text),
        "keyword_hits": hits,
        "implementation_notes": [
            "Treat the editor as a project folder that Claude Code can operate through repeatable skills.",
            "Every job follows the same seven-step path from raw intake to final export.",
            "Only the graphics and captions presets change materially between short and long formats.",
            "WhisperX, FFmpeg, HyperFrames, and optional yt-dlp/youtube-transcript-api are external tools.",
            "Store full transcripts only when the user owns the rights or explicitly needs a local working copy.",
        ],
        "copyright_note": "Full verbatim transcript intentionally not stored by this command.",
    }


def write_summary(video_url: str, output_dir: Path, *, languages: list[str]) -> Path:
    summary = transcript_summary(video_url, languages=languages)
    target = output_dir / f"{summary['video_id']}.caption-summary.json"
    return write_json(target, summary)


def write_vtt_from_segments(video_url: str, output_dir: Path, *, languages: list[str], rights_confirmed: bool) -> Path:
    if not rights_confirmed:
        raise SubtitleError("Refusing to write a full transcript file without --i-own-rights.")
    video_id = video_id_from_url(video_url)
    segments = fetch_transcript_segments(video_id, languages)
    lines = ["WEBVTT", ""]
    for index, segment in enumerate(segments, start=1):
        start = _vtt_timestamp(segment.start)
        end = _vtt_timestamp(segment.start + segment.duration)
        lines.extend([str(index), f"{start} --> {end}", segment.text, ""])
    return write_text(output_dir / f"{video_id}.captions.vtt", "\n".join(lines))


def _vtt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"
