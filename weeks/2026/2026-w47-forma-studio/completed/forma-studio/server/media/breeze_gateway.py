"""Authenticated relay for an already-running Breeze TTS 2 streaming server."""

import hmac
from pathlib import Path

import requests
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse


def create_app(token, upstream="http://127.0.0.1:7860", profiles=None):
    """Map each optional profile name to (reference WAV, UTF-8 transcript file) on the VM."""
    if not isinstance(token, str) or not token.strip() or not token.isascii():
        raise ValueError("請設定 ASCII 存取權杖。")
    profiles = dict(profiles or {})
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    bearer = ("Bearer " + token.strip()).encode("ascii")

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        actual = request.headers.get("authorization", "").encode("utf-8")
        if not hmac.compare_digest(actual, bearer):
            return JSONResponse({"detail": "需要有效的存取權杖。"}, 401)
        if request.method == "POST":
            length = request.headers.get("content-length", "")
            if not length.isdecimal() or int(length) > 65536:
                return JSONResponse({"detail": "單筆請求容量上限為 64 KiB。"}, 413)
        return await call_next(request)

    @app.get("/studio/capabilities")
    def capabilities():
        return {"profiles": sorted(profiles)}

    @app.post("/v1/audio/speech")
    def speech(text: str = Form(...), instruction: str = Form("自然清晰的台灣華語。"),
               voice_id: str = Form(""), cfg_scale: float = Form(4), seed: int = Form(42)):
        if not text.strip() or len(text) > 5000 or len(instruction) > 2000:
            raise HTTPException(422, "台詞或聲音描述長度不符。")
        if voice_id and voice_id not in profiles:
            raise HTTPException(404, "沒有這個音色。")
        fields = {"text": text, "instruction": instruction, "cfg_scale": str(cfg_scale), "seed": str(seed)}
        endpoint = upstream.rstrip("/") + "/v1/audio/speech"
        try:
            if voice_id:
                wav, transcript = map(Path, profiles[voice_id])
                fields["ref_text"] = transcript.read_text(encoding="utf-8-sig").strip()
                with wav.open("rb") as reference:
                    response = requests.post(endpoint, data=fields, stream=True, timeout=(15, 600),
                                             files={"ref_audio": ("reference.wav", reference, "audio/wav")},
                                             allow_redirects=False)
            else:
                response = requests.post(endpoint, data=fields, stream=True, timeout=(15, 600), allow_redirects=False)
        except (OSError, requests.RequestException) as exc:
            raise HTTPException(502, "無法連線到此執行階段上的 Breeze API 或讀取指定音色。") from exc

        if response.status_code != 200:
            response.close()
            raise HTTPException(response.status_code if response.status_code >= 400 else 502,
                                "Breeze 語音服務未完成此次請求。")

        def audio():
            try:
                yield from response.iter_content(65536)
            finally:
                response.close()

        return StreamingResponse(audio(), media_type=response.headers.get("Content-Type", "audio/pcm"),
                                 headers={"X-Sample-Rate": response.headers.get("X-Sample-Rate", "24000"),
                                          "X-Sample-Format": response.headers.get("X-Sample-Format", "s16le"),
                                          "Cache-Control": "no-store"})

    return app
