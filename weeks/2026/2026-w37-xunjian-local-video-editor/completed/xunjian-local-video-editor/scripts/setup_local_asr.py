"""Explicit, bounded download of public SYSTRAN Whisper assets. Runtime stays offline."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import threading
import time
from pathlib import Path

os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ETAG_TIMEOUT"] = "15"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "20"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("small", "base"), default="small")
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    if not 30 <= args.timeout <= 600:
        parser.error("timeout must be 30..600 seconds")
    directory = (args.directory or Path(__file__).resolve().parent.parent / ".local-editor" / "models" / f"faster-whisper-{args.model}").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    repo = f"Systran/faster-whisper-{args.model}"
    print(f"Public model: https://huggingface.co/{repo}; local destination: {directory}", flush=True)
    state = {"done": False, "error": None}

    def download():
        try:
            from huggingface_hub import HfApi, snapshot_download
            info = HfApi(token=False).model_info(repo, files_metadata=True)
            wanted = {"config.json", "model.bin", "tokenizer.json", "vocabulary.txt", "preprocessor_config.json"}
            assets = [f for f in info.siblings if f.rfilename in wanted]
            total = sum(f.size or 0 for f in assets)
            if total > 600_000_000:
                raise RuntimeError("Model exceeds 600 MB; retry with --model base.")
            print(f"Revision: {info.sha}; download size: {total / 1_000_000:.1f} MB", flush=True)
            snapshot_download(repo_id=repo, revision=info.sha, local_dir=directory,
                              allow_patterns=sorted(wanted), token=False, max_workers=2)
            model_file = directory / "model.bin"
            if not model_file.is_file() or model_file.stat().st_size < 10_000_000:
                raise RuntimeError("Model file is incomplete.")
            with model_file.open("rb") as model_stream:
                digest = hashlib.file_digest(model_stream, "sha256").hexdigest()
            model_info = next(f for f in assets if f.rfilename == "model.bin")
            expected = getattr(model_info.lfs, "sha256", None) if model_info.lfs else None
            if expected and expected != digest:
                raise RuntimeError("Model checksum mismatch.")
            manifest = {"repository": repo, "source": f"https://huggingface.co/{repo}",
                        "revision": info.sha, "model_sha256": digest, "bytes": total,
                        "local_files_only_runtime": True, "license": "MIT"}
            (directory / "local-model-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(json.dumps({"status": "ready", "model_path": str(directory), **manifest}), flush=True)
        except Exception as error:
            state["error"] = str(error)
        finally:
            state["done"] = True

    worker = threading.Thread(target=download, daemon=True)
    worker.start()
    started = time.monotonic()
    while not state["done"]:
        elapsed = time.monotonic() - started
        if elapsed > args.timeout:
            print("Download timeout; partial local files are preserved for retry.", flush=True)
            os._exit(124)
        if worker.is_alive():
            size = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
            print(f"Setup elapsed {elapsed:.0f}s; local bytes {size / 1_000_000:.1f} MB", flush=True)
        worker.join(timeout=15)
    if state["error"]:
        print(f"ASR setup failed: {state['error']}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
