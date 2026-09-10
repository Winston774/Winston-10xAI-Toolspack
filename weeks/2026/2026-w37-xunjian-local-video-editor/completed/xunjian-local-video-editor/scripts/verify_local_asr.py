"""Verify local ASR on a local Windows Speech fixture, preserving evidence."""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from local_editor.media_engine import doctor, probe, transcription

fixture = Path(sys.argv[1]).resolve()
metadata = probe(fixture)
media = {"id": "windows-local-speech-fixture", "path": str(fixture), **metadata}
captions = transcription(media, {"language": "zh", "device": "cpu", "compute_type": "int8", "timeout": 180}, fixture.parent / "asr-smoke")
text = "".join(c["text"] for c in captions)
if not text.strip():
    raise SystemExit("ASR returned no captions.")
keywords = [word for word in ("字幕", "繁體中文", "停頓", "電腦") if word in text]
if len(keywords) < 2:
    raise SystemExit(f"ASR returned text but did not identify enough fixture keywords: {text}")
result = {"status": "passed", "fixture": str(fixture), "synthetic": True,
          "fixture_source": "Windows installed SpeechSynthesizer; no uploaded audio",
          "duration": media["duration"], "caption_count": len(captions), "text": text,
          "matched_keywords": keywords, "captions": captions, "asr": doctor()["transcription"]}
evidence = fixture.parent / "asr-smoke-result.json"
evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
