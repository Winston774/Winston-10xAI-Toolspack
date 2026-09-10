"""Bounded source-peak chunks, cached independently of project edit history."""
from __future__ import annotations

import array
import hashlib
import json
import sys
import threading
import uuid
from pathlib import Path

from .media_engine import _run, _tool

CHUNK_SECONDS = 30
SAMPLE_RATE = 48000
BUCKET_SECONDS = .01
_cache_lock = threading.Lock()


def source_peaks(path: Path, cache_dir: Path, chunk: int, duration: float) -> dict:
    start = chunk * CHUNK_SECONDS
    length = min(CHUNK_SECONDS, duration - start)
    if chunk < 0 or length <= 0:
        raise ValueError("波形區間超出素材範圍")
    stat = path.stat()
    identity = f"peaks-v1:{path}:{stat.st_size}:{stat.st_mtime_ns}:{chunk}"
    key = hashlib.sha256(identity.encode()).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{key}.json"
    # Serialize bounded decoding; concurrent viewers share the same cache.
    with _cache_lock:
        if cached.is_file():
            try:
                return json.loads(cached.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                pass
        raw = _run([_tool("ffmpeg"), "-v", "error", "-nostdin",
                    "-protocol_whitelist", "file,pipe", "-ss", str(start), "-i", str(path),
                    "-t", str(length), "-map", "0:a:0", "-vn", "-ac", "2", "-ar", str(SAMPLE_RATE),
                    "-f", "s16le", "pipe:1"], binary=True, timeout=60).stdout
        samples = array.array("h")
        samples.frombytes(raw)
        if sys.byteorder != "little":
            samples.byteswap()
        bucket = int(SAMPLE_RATE * BUCKET_SECONDS) * 2
        peaks = []
        for i in range(0, len(samples), bucket):
            section = samples[i:i + bucket]
            # Preserve peaks of both channels, including opposite-phase stereo.
            peaks.append(round(max(max(section), -min(section)) / 32768, 5))
        result = {"start": start, "end": start + len(samples) / (SAMPLE_RATE * 2),
                  "bucket_seconds": BUCKET_SECONDS, "peaks": peaks}
        temporary = cached.with_suffix(f".{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
            temporary.replace(cached)
        finally:
            temporary.unlink(missing_ok=True)
        return result
