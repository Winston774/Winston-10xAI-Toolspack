"""Local HTTP bridge for the standalone IndexTTS HTML workbench.

The browser UI stays in one dependency-free ``webui.html`` file. This module
owns model lifecycle, input validation, upload isolation, and serialized GPU
inference so the frontend never needs direct access to Python or CUDA.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import threading
import time
import uuid
import wave
import webbrowser
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from opencc import OpenCC
from starlette.concurrency import run_in_threadpool


ROOT = Path(__file__).resolve().parent
HTML_PATH = ROOT / "webui.html"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "htmlui"
ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"}
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_TEXT_LENGTH = 5_000
MODEL_LANGUAGE_BY_UI_LANGUAGE = {
    "ZH-TW": "ZH",
    "ZH": "ZH",
    "EN": "EN",
    "JA": "JA",
    "AR": "AR",
    "ES": "ES",
}
SUPPORTED_LANGUAGES = frozenset(MODEL_LANGUAGE_BY_UI_LANGUAGE)
SUPPORTED_EMOTION_MODES = {"voice", "reference", "vector", "text"}
REQUIRED_MODEL_FILES = {
    "gpt.pth",
    "s2mel.pth",
    "codec.pth",
    "multilingual_zh_ja_yue_char_del.tiktoken",
    "wav2vec2bert_stats.pt",
}


@dataclass(frozen=True)
class RuntimeConfig:
    model_dir: Path = ROOT / "checkpoints"
    output_dir: Path = DEFAULT_OUTPUT_DIR
    use_bf16: bool = True
    use_cuda_kernel: bool = False
    use_accel: bool = False
    use_torch_compile: bool = False
    device: str | None = None
    auto_load: bool = True


@dataclass(frozen=True)
class GenerationOptions:
    text: str
    language: str = "ZH-TW"
    emotion_mode: str = "voice"
    emotion_weight: float = 0.65
    emotion_text: str | None = None
    emotion_vector: tuple[float, ...] = (0.0,) * 8
    use_random: bool = False
    duration_factor: float = 1.0
    interval_silence: int = 200
    max_text_tokens_per_segment: int = 120
    text_normalization: bool = True
    do_sample: bool = True
    top_p: float = 0.8
    top_k: int = 30
    temperature: float = 0.8
    length_penalty: float = 0.0
    num_beams: int = 3
    repetition_penalty: float = 10.0
    max_mel_tokens: int = 1500
    seed: int = 42

    @classmethod
    def from_form(
        cls,
        *,
        text: str,
        language: str,
        emotion_mode: str,
        emotion_weight: float,
        emotion_text: str,
        emotion_vector: str,
        use_random: bool,
        duration_factor: float,
        interval_silence: int,
        max_text_tokens_per_segment: int,
        text_normalization: bool,
        do_sample: bool,
        top_p: float,
        top_k: int,
        temperature: float,
        length_penalty: float,
        num_beams: int,
        repetition_penalty: float,
        max_mel_tokens: int,
        seed: int,
    ) -> "GenerationOptions":
        clean_text = text.strip()
        clean_language = language.upper().strip()
        clean_mode = emotion_mode.lower().strip()

        if not clean_text:
            raise ValueError("請輸入要合成的文字。")
        if len(clean_text) > MAX_TEXT_LENGTH:
            raise ValueError(f"文字長度不可超過 {MAX_TEXT_LENGTH} 個字元。")
        if clean_language not in SUPPORTED_LANGUAGES:
            raise ValueError("不支援這個語言選項。")
        if clean_mode not in SUPPORTED_EMOTION_MODES:
            raise ValueError("不支援這個情緒控制模式。")

        try:
            vector_data = json.loads(emotion_vector)
        except json.JSONDecodeError as exc:
            raise ValueError("情緒向量格式錯誤。") from exc
        if not isinstance(vector_data, list) or len(vector_data) != 8:
            raise ValueError("情緒向量必須包含 8 個數值。")
        try:
            vector = tuple(float(value) for value in vector_data)
        except (TypeError, ValueError) as exc:
            raise ValueError("情緒向量只能包含數值。") from exc
        if any(value < 0.0 or value > 1.0 for value in vector):
            raise ValueError("每個情緒向量值必須介於 0.0 到 1.0。")

        cls._require_range("情緒權重", emotion_weight, 0.0, 1.0)
        cls._require_range("時長係數", duration_factor, 0.5, 2.0)
        cls._require_range("段落間隔", interval_silence, 0, 2_000)
        cls._require_range("分句 Token", max_text_tokens_per_segment, 20, 600)
        cls._require_range("top_p", top_p, 0.0, 1.0)
        cls._require_range("top_k", top_k, 0, 100)
        cls._require_range("temperature", temperature, 0.1, 2.0)
        cls._require_range("length_penalty", length_penalty, -2.0, 2.0)
        cls._require_range("num_beams", num_beams, 1, 10)
        cls._require_range("repetition_penalty", repetition_penalty, 0.1, 20.0)
        cls._require_range("max_mel_tokens", max_mel_tokens, 50, 5_000)
        cls._require_range("seed", seed, 0, 2_147_483_647)

        return cls(
            text=clean_text,
            language=clean_language,
            emotion_mode=clean_mode,
            emotion_weight=float(emotion_weight),
            emotion_text=emotion_text.strip() or None,
            emotion_vector=vector,
            use_random=bool(use_random),
            duration_factor=float(duration_factor),
            interval_silence=int(interval_silence),
            max_text_tokens_per_segment=int(max_text_tokens_per_segment),
            text_normalization=bool(text_normalization),
            do_sample=bool(do_sample),
            top_p=float(top_p),
            top_k=int(top_k),
            temperature=float(temperature),
            length_penalty=float(length_penalty),
            num_beams=int(num_beams),
            repetition_penalty=float(repetition_penalty),
            max_mel_tokens=int(max_mel_tokens),
            seed=int(seed),
        )

    @staticmethod
    def _require_range(name: str, value: float, minimum: float, maximum: float) -> None:
        if value < minimum or value > maximum:
            raise ValueError(f"{name} 必須介於 {minimum:g} 到 {maximum:g}。")

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["emotion_vector"] = list(self.emotion_vector)
        return data


@dataclass(frozen=True)
class ModelTextInput:
    """Internal text payload prepared for the upstream IndexTTS model."""

    text: str
    language: str
    emotion_text: str | None


@lru_cache(maxsize=1)
def _taiwan_traditional_converter() -> OpenCC:
    return OpenCC("tw2s")


def _prepare_model_text(options: GenerationOptions) -> ModelTextInput:
    model_language = MODEL_LANGUAGE_BY_UI_LANGUAGE[options.language]
    if model_language != "ZH":
        return ModelTextInput(options.text, model_language, options.emotion_text)

    converter = _taiwan_traditional_converter()
    return ModelTextInput(
        text=converter.convert(options.text),
        language=model_language,
        emotion_text=(
            converter.convert(options.emotion_text)
            if options.emotion_text is not None
            else None
        ),
    )


class ModelRuntime:
    """Owns one model instance and permits one GPU job at a time."""

    model_version = "2.5"

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self._state = "idle"
        self._message = "等待載入模型"
        self._model: Any | None = None
        self._state_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._load_thread: threading.Thread | None = None
        self._loaded_at: float | None = None

    def start_loading(self) -> None:
        with self._state_lock:
            if self._state in {"loading", "ready"}:
                return
            self._state = "loading"
            self._message = "正在檢查模型檔案"
            self._load_thread = threading.Thread(
                target=self._load_model,
                name="indextts-model-loader",
                daemon=True,
            )
            self._load_thread.start()

    def _load_model(self) -> None:
        try:
            self._ensure_model_files()
            self._set_state("loading", "正在載入 IndexTTS 2.5")
            from indextts.infer_v2_5 import IndexTTS2

            self._model = IndexTTS2(
                cfg_path=str(self.config.model_dir / "config.yaml"),
                model_dir=str(self.config.model_dir),
                use_bf16=self.config.use_bf16,
                use_cuda_kernel=self.config.use_cuda_kernel,
                use_accel=self.config.use_accel,
                use_torch_compile=self.config.use_torch_compile,
                use_qwen_emo=True,
                device=self.config.device,
            )
            self._loaded_at = time.time()
            self._set_state("ready", "模型已就緒")
        except Exception as exc:  # surfaced through the local health endpoint
            self._model = None
            self._set_state("error", f"模型載入失敗：{exc}")

    def _ensure_model_files(self) -> None:
        self.config.model_dir.mkdir(parents=True, exist_ok=True)
        missing = [
            name for name in sorted(REQUIRED_MODEL_FILES)
            if not (self.config.model_dir / name).exists()
        ]
        if missing:
            self._set_state("loading", "正在下載 IndexTTS 2.5 模型")
            from indextts.utils.model_download import snapshot_download

            snapshot_download("IndexTeam/IndexTTS-2.5", local_dir=str(self.config.model_dir))

        from indextts.utils.model_download import ensure_config_available

        ensure_config_available(str(self.config.model_dir), version="2.5")
        still_missing = [
            name for name in sorted(REQUIRED_MODEL_FILES)
            if not (self.config.model_dir / name).exists()
        ]
        if still_missing:
            raise RuntimeError("缺少模型檔案：" + ", ".join(still_missing))

    def _set_state(self, state: str, message: str) -> None:
        with self._state_lock:
            self._state = state
            self._message = message

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "state": self._state,
                "message": self._message,
                "busy": self._inference_lock.locked(),
                "model_version": self.model_version,
                "bf16": self.config.use_bf16,
                "loaded_at": self._loaded_at,
            }

    def generate(
        self,
        options: GenerationOptions,
        voice_path: Path,
        emotion_path: Path | None,
        output_path: Path,
    ) -> float:
        if self._state != "ready" or self._model is None:
            raise RuntimeError("模型尚未就緒。")
        if options.emotion_mode == "reference" and emotion_path is None:
            raise ValueError("情緒參考模式需要上傳情緒參考音檔。")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._inference_lock:
            max_text_tokens = int(getattr(self._model.cfg.gpt, "max_text_tokens", 600))
            max_mel_tokens = int(getattr(self._model.cfg.gpt, "max_mel_tokens", 5_000))
            if options.max_text_tokens_per_segment > max_text_tokens:
                raise ValueError(f"目前模型的分句 Token 上限為 {max_text_tokens}。")
            if options.max_mel_tokens > max_mel_tokens:
                raise ValueError(f"目前模型的 Max Mel Tokens 上限為 {max_mel_tokens}。")

            self._seed_everything(options.seed)
            model_text = _prepare_model_text(options)
            emotion_vector = None
            use_emotion_text = options.emotion_mode == "text"
            emotion_audio = emotion_path if options.emotion_mode == "reference" else None
            if options.emotion_mode == "vector":
                emotion_vector = self._model.normalize_emo_vec(
                    list(options.emotion_vector), apply_bias=True
                )

            started = time.perf_counter()
            result = self._model.infer(
                spk_audio_prompt=str(voice_path),
                text=model_text.text,
                output_path=str(output_path),
                lang=model_text.language,
                emo_audio_prompt=str(emotion_audio) if emotion_audio else None,
                emo_alpha=options.emotion_weight,
                emo_vector=emotion_vector,
                use_emo_text=use_emotion_text,
                emo_text=model_text.emotion_text,
                use_random=options.use_random,
                interval_silence=options.interval_silence,
                max_text_tokens_per_segment=options.max_text_tokens_per_segment,
                duration_factor=options.duration_factor,
                text_normalization=options.text_normalization,
                do_sample=options.do_sample,
                top_p=options.top_p,
                top_k=options.top_k or None,
                temperature=options.temperature,
                length_penalty=options.length_penalty,
                num_beams=options.num_beams,
                repetition_penalty=options.repetition_penalty,
                max_mel_tokens=options.max_mel_tokens,
            )
            elapsed = time.perf_counter() - started

        resolved = Path(result) if isinstance(result, str) else output_path
        if resolved != output_path and resolved.exists():
            shutil.copy2(resolved, output_path)
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("模型沒有產生可用的 WAV 檔案。")
        return elapsed

    @staticmethod
    def _seed_everything(seed: int) -> None:
        random.seed(seed)
        try:
            import numpy as np

            np.random.seed(seed)
        except ImportError:
            pass
        try:
            import torch

            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
        except ImportError:
            pass


async def _save_upload(
    upload: UploadFile,
    directory: Path,
    stem: str,
    label: str = "音檔",
) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_AUDIO_SUFFIXES))
        raise HTTPException(status_code=400, detail=f"{label}格式需為：{allowed}")

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{stem}{suffix}"
    total = 0
    try:
        with target.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="單一音檔不可超過 64 MB。")
                handle.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if total == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="上傳的音檔是空的。")
    return target


def _wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wav_file:
            frame_rate = wav_file.getframerate()
            if frame_rate <= 0:
                return None
            return round(wav_file.getnframes() / frame_rate, 3)
    except (wave.Error, OSError):
        return None


def _task_path(output_dir: Path, task_id: str, suffix: str) -> Path:
    try:
        normalized = str(uuid.UUID(task_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="找不到這筆生成結果。") from exc
    return output_dir / f"{normalized}{suffix}"


def create_app(runtime: ModelRuntime | None = None) -> FastAPI:
    runtime = runtime or ModelRuntime(RuntimeConfig())

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if runtime.config.auto_load:
            runtime.start_loading()
        yield

    app = FastAPI(
        title="IndexTTS HTML UI API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["null"],
        allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/", include_in_schema=False)
    @app.get("/webui.html", include_in_schema=False)
    async def index() -> FileResponse:
        if not HTML_PATH.exists():
            raise HTTPException(status_code=500, detail="找不到 webui.html。")
        return FileResponse(
            HTML_PATH,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return runtime.status()

    @app.get("/api/capabilities")
    async def capabilities() -> dict[str, Any]:
        return {
            "model": "IndexTTS 2.5",
            "languages": sorted(SUPPORTED_LANGUAGES),
            "emotion_modes": ["voice", "reference", "vector", "text"],
            "emotion_vector_order": [
                "happy", "angry", "sad", "afraid",
                "disgusted", "melancholic", "surprised", "calm",
            ],
            "duration_factor": {"minimum": 0.5, "maximum": 2.0, "default": 1.0},
            "pronunciation_annotations": ["pinyin", "cmu_phoneme", "japanese_kana"],
            "single_gpu_job": True,
        }

    @app.post("/api/generate")
    async def generate(
        voice: UploadFile = File(...),
        # Browsers may serialize an unselected file input as an empty string or
        # a zero-byte UploadFile named "blob". Accept both forms and normalize
        # them below instead of rejecting the whole multipart request.
        emotion_audio: UploadFile | str | None = File(None),
        text: str = Form(...),
        language: str = Form("ZH-TW"),
        emotion_mode: str = Form("voice"),
        emotion_weight: float = Form(0.65),
        emotion_text: str = Form(""),
        emotion_vector: str = Form("[0,0,0,0,0,0,0,0]"),
        use_random: bool = Form(False),
        duration_factor: float = Form(1.0),
        interval_silence: int = Form(200),
        max_text_tokens_per_segment: int = Form(120),
        text_normalization: bool = Form(True),
        do_sample: bool = Form(True),
        top_p: float = Form(0.8),
        top_k: int = Form(30),
        temperature: float = Form(0.8),
        length_penalty: float = Form(0.0),
        num_beams: int = Form(3),
        repetition_penalty: float = Form(10.0),
        max_mel_tokens: int = Form(1500),
        seed: int = Form(42),
    ) -> JSONResponse:
        status = runtime.status()
        if status["state"] != "ready":
            raise HTTPException(status_code=503, detail=status["message"])
        if status["busy"]:
            raise HTTPException(status_code=409, detail="GPU 正在處理另一筆生成，請稍後再試。")

        try:
            options = GenerationOptions.from_form(
                text=text,
                language=language,
                emotion_mode=emotion_mode,
                emotion_weight=emotion_weight,
                emotion_text=emotion_text,
                emotion_vector=emotion_vector,
                use_random=use_random,
                duration_factor=duration_factor,
                interval_silence=interval_silence,
                max_text_tokens_per_segment=max_text_tokens_per_segment,
                text_normalization=text_normalization,
                do_sample=do_sample,
                top_p=top_p,
                top_k=top_k,
                temperature=temperature,
                length_penalty=length_penalty,
                num_beams=num_beams,
                repetition_penalty=repetition_penalty,
                max_mel_tokens=max_mel_tokens,
                seed=seed,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        emotion_upload = emotion_audio if not isinstance(emotion_audio, str) else None
        emotion_upload_is_empty = (
            emotion_upload is None
            or not (emotion_upload.filename or "").strip()
            or getattr(emotion_upload, "size", None) == 0
        )
        if options.emotion_mode == "reference" and emotion_upload_is_empty:
            raise HTTPException(status_code=422, detail="請上傳情緒參考音檔。")

        task_id = str(uuid.uuid4())
        upload_dir = runtime.config.output_dir / "uploads" / task_id
        output_path = runtime.config.output_dir / f"{task_id}.wav"
        metadata_path = runtime.config.output_dir / f"{task_id}.json"
        voice_path: Path | None = None
        emotion_path: Path | None = None
        try:
            voice_path = await _save_upload(
                voice, upload_dir, "voice", label="聲紋參考音檔"
            )
            if options.emotion_mode == "reference" and emotion_upload is not None:
                emotion_path = await _save_upload(
                    emotion_upload,
                    upload_dir,
                    "emotion",
                    label="情緒參考音檔",
                )
            elif emotion_upload is not None:
                await emotion_upload.close()
            elapsed = await run_in_threadpool(
                runtime.generate,
                options,
                voice_path,
                emotion_path,
                output_path,
            )
        except HTTPException:
            output_path.unlink(missing_ok=True)
            raise
        except ValueError as exc:
            output_path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"生成失敗：{exc}") from exc
        finally:
            shutil.rmtree(upload_dir, ignore_errors=True)

        audio_duration = _wav_duration(output_path)
        metadata = {
            "task_id": task_id,
            "created_at": time.time(),
            "model": "IndexTTS 2.5",
            "generation_seconds": round(elapsed, 3),
            "audio_duration_seconds": audio_duration,
            "options": options.public_dict(),
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return JSONResponse(
            {
                **metadata,
                "audio_url": f"/api/audio/{task_id}",
                "metadata_url": f"/api/runs/{task_id}",
            }
        )

    @app.get("/api/audio/{task_id}")
    async def audio(task_id: str) -> FileResponse:
        path = _task_path(runtime.config.output_dir, task_id, ".wav")
        if not path.exists():
            raise HTTPException(status_code=404, detail="找不到這筆生成結果。")
        return FileResponse(
            path,
            media_type="audio/wav",
            filename=f"indextts-{task_id[:8]}.wav",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @app.get("/api/runs/{task_id}")
    async def run_metadata(task_id: str) -> JSONResponse:
        path = _task_path(runtime.config.output_dir, task_id, ".json")
        if not path.exists():
            raise HTTPException(status_code=404, detail="找不到這筆生成紀錄。")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    return app


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IndexTTS 2.5 standalone HTML UI")
    parser.add_argument("--host", default="127.0.0.1", help="Local server host")
    parser.add_argument("--port", type=int, default=7861, help="Local server port")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "checkpoints")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--bf16",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use BF16 inference when the selected device supports it",
    )
    parser.add_argument("--cuda-kernel", action="store_true")
    parser.add_argument("--accel", action="store_true")
    parser.add_argument("--torch-compile", action="store_true")
    parser.add_argument("--device", default=None, help="Example: cuda:0 or cpu")
    parser.add_argument(
        "--open-browser",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Open the HTML workbench after the server starts",
    )
    return parser


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")

    args = _build_parser().parse_args()
    config = RuntimeConfig(
        model_dir=args.model_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        use_bf16=args.bf16,
        use_cuda_kernel=args.cuda_kernel,
        use_accel=args.accel,
        use_torch_compile=args.torch_compile,
        device=args.device,
    )
    runtime = ModelRuntime(config)
    app = create_app(runtime)
    url = f"http://127.0.0.1:{args.port}"
    if args.open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print("WARNING: the API is listening beyond this computer. Only use this on a trusted network.")

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
