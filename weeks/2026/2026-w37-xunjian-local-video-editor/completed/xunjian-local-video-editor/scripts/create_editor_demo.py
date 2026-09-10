"""Generate explicitly synthetic local test media; this is not speech recognition evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from local_editor.media_engine import _run, _tool, probe


def create_demo(directory: Path) -> dict:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "synthetic-speech-timing.mp4"
    _run([_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
          "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=6",
          "-f", "lavfi", "-i",
          "aevalsrc=if(between(t\\,1\\,2)+between(t\\,3.5\\,4.5)\\,0\\,0.18*sin(2*PI*440*t)):s=48000:d=6",
          "-vf", "drawtext=text='SYNTHETIC DEMO - NOT REAL SPEECH':fontcolor=white:fontsize=23:x=(w-tw)/2:y=24:box=1:boxcolor=black@0.8",
          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-t", "6", str(path)], timeout=90)
    silent = directory / "synthetic-silent-overlay.mp4"
    _run([_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
          "-f", "lavfi", "-i", "color=c=blue:size=320x180:rate=24:duration=2",
          "-vf", "drawtext=text='SILENT OVERLAY':fontcolor=white:fontsize=24:x=(w-tw)/2:y=(h-th)/2",
          "-an", "-c:v", "libx264", "-preset", "ultrafast", str(silent)], timeout=90)
    info = {"synthetic": True, "purpose": "FFmpeg 匯入、停頓偵測、時間軸合成測試，非真人口播或辨識結果。",
            "video": str(path), "silent_overlay": str(silent),
            "known_silences": [[1, 2], [3.5, 4.5]], "probe": probe(path)}
    (directory / "synthetic-demo.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/local-editor-demo"))
    args = parser.parse_args()
    print(json.dumps(create_demo(args.output_dir), ensure_ascii=False, indent=2))
