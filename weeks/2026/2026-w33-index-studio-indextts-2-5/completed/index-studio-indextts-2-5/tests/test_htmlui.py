"""Contract tests for the standalone HTML workbench.

These tests use a tiny fake runtime, so they validate the HTTP bridge without
downloading checkpoints or reserving GPU memory.
"""

import json
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from htmlui_server import GenerationOptions, ModelRuntime, RuntimeConfig, create_app


class FakeRuntime:
    model_version = "2.5"

    def __init__(self, output_dir: Path, state: str = "ready") -> None:
        self.config = RuntimeConfig(output_dir=output_dir, auto_load=False)
        self.state = state
        self.generate_calls = []

    def start_loading(self) -> None:
        raise AssertionError("auto_load=False should not start the model")

    def status(self):
        return {
            "state": self.state,
            "message": "模型已就緒" if self.state == "ready" else "模型載入中",
            "busy": False,
            "model_version": self.model_version,
            "bf16": True,
            "loaded_at": None,
        }

    def generate(self, options, voice_path, emotion_path, output_path):
        self.generate_calls.append((options, voice_path, emotion_path, output_path))
        assert voice_path.exists()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(22_050)
            audio.writeframes(b"\x00\x00" * 2_205)
        return 0.125


def valid_options(**overrides):
    values = {
        "text": "這是一段測試語音。",
        "language": "ZH",
        "emotion_mode": "voice",
        "emotion_weight": 0.65,
        "emotion_text": "",
        "emotion_vector": "[0,0,0,0,0,0,0,0]",
        "use_random": False,
        "duration_factor": 1.0,
        "interval_silence": 200,
        "max_text_tokens_per_segment": 120,
        "text_normalization": True,
        "do_sample": True,
        "top_p": 0.8,
        "top_k": 30,
        "temperature": 0.8,
        "length_penalty": 0.0,
        "num_beams": 3,
        "repetition_penalty": 10.0,
        "max_mel_tokens": 1500,
        "seed": 42,
    }
    values.update(overrides)
    return GenerationOptions.from_form(**values)


def test_generation_options_normalize_and_validate():
    options = valid_options(text="  Hello  ", language="en", emotion_mode="TEXT")
    assert options.text == "Hello"
    assert options.language == "EN"
    assert options.emotion_mode == "text"

    with pytest.raises(ValueError, match="8 個數值"):
        valid_options(emotion_vector="[0, 1]")
    with pytest.raises(ValueError, match="時長係數"):
        valid_options(duration_factor=2.1)
    with pytest.raises(ValueError, match="不支援這個語言"):
        valid_options(language="FR")


def test_model_runtime_maps_vector_and_generation_controls(tmp_path):
    class RecordingModel:
        cfg = SimpleNamespace(gpt=SimpleNamespace(max_text_tokens=240, max_mel_tokens=2_000))

        def __init__(self):
            self.kwargs = None

        @staticmethod
        def normalize_emo_vec(vector, apply_bias):
            assert apply_bias is True
            return [round(value * 0.5, 3) for value in vector]

        def infer(self, **kwargs):
            self.kwargs = kwargs
            with wave.open(kwargs["output_path"], "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(22_050)
                audio.writeframes(b"\x00\x00" * 220)
            return kwargs["output_path"]

    runtime = ModelRuntime(RuntimeConfig(output_dir=tmp_path, auto_load=False))
    model = RecordingModel()
    runtime._model = model
    runtime._state = "ready"
    runtime._seed_everything = lambda _: None
    voice_path = tmp_path / "voice.wav"
    voice_path.write_bytes(b"fake")
    output_path = tmp_path / "result.wav"

    runtime.generate(
        valid_options(
            emotion_mode="vector",
            emotion_vector="[0.8,0,0,0,0,0,0,0.2]",
            duration_factor=1.2,
            seed=774,
        ),
        voice_path,
        None,
        output_path,
    )

    assert output_path.exists()
    assert model.kwargs["lang"] == "ZH"
    assert model.kwargs["emo_vector"] == [0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1]
    assert model.kwargs["duration_factor"] == 1.2
    assert model.kwargs["use_emo_text"] is False


def test_taiwan_traditional_mode_converts_only_internal_model_input(tmp_path):
    class RecordingModel:
        cfg = SimpleNamespace(gpt=SimpleNamespace(max_text_tokens=240, max_mel_tokens=2_000))

        def __init__(self):
            self.kwargs = None

        def infer(self, **kwargs):
            self.kwargs = kwargs
            with wave.open(kwargs["output_path"], "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(22_050)
                audio.writeframes(b"\x00\x00" * 220)
            return kwargs["output_path"]

    runtime = ModelRuntime(RuntimeConfig(output_dir=tmp_path, auto_load=False))
    model = RecordingModel()
    runtime._model = model
    runtime._state = "ready"
    runtime._seed_everything = lambda _: None
    voice_path = tmp_path / "voice.wav"
    voice_path.write_bytes(b"fake")
    output_path = tmp_path / "result.wav"
    options = valid_options(
        text="臺灣正體中文，先別出聲。",
        language="ZH-TW",
        emotion_mode="text",
        emotion_text="壓低聲音，緊張地提醒身邊的人",
    )

    runtime.generate(options, voice_path, None, output_path)

    assert model.kwargs["lang"] == "ZH"
    assert model.kwargs["text"] == "台湾正体中文，先别出声。"
    assert model.kwargs["emo_text"] == "压低声音，紧张地提醒身边的人"
    assert options.public_dict()["language"] == "ZH-TW"
    assert options.public_dict()["text"] == "臺灣正體中文，先別出聲。"
    assert options.public_dict()["emotion_text"] == "壓低聲音，緊張地提醒身邊的人"


def test_legacy_zh_language_value_still_converts_traditional_model_input(tmp_path):
    class RecordingModel:
        cfg = SimpleNamespace(gpt=SimpleNamespace(max_text_tokens=240, max_mel_tokens=2_000))

        def __init__(self):
            self.kwargs = None

        def infer(self, **kwargs):
            self.kwargs = kwargs
            with wave.open(kwargs["output_path"], "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(22_050)
                audio.writeframes(b"\x00\x00" * 220)
            return kwargs["output_path"]

    runtime = ModelRuntime(RuntimeConfig(output_dir=tmp_path, auto_load=False))
    model = RecordingModel()
    runtime._model = model
    runtime._state = "ready"
    runtime._seed_everything = lambda _: None
    voice_path = tmp_path / "voice.wav"
    voice_path.write_bytes(b"fake")

    runtime.generate(
        valid_options(text="先別出聲，他就在門外。", language="ZH"),
        voice_path,
        None,
        tmp_path / "result.wav",
    )

    assert model.kwargs["lang"] == "ZH"
    assert model.kwargs["text"] == "先别出声，他就在门外。"


def test_health_capabilities_and_html_are_available(tmp_path):
    runtime = FakeRuntime(tmp_path)
    with TestClient(create_app(runtime)) as client:
        html_response = client.get("/")
        assert html_response.status_code == 200
        health = client.get("/api/health").json()
        capabilities = client.get("/api/capabilities").json()

    assert health["state"] == "ready"
    assert capabilities["languages"] == ["AR", "EN", "ES", "JA", "ZH", "ZH-TW"]
    assert capabilities["single_gpu_job"] is True
    assert '<option value="ZH-TW" selected>中文</option>' in html_response.text
    assert "--canvas: #f1efe7;" in html_response.text
    assert "--accent: #7432ff;" in html_response.text
    assert "--signal: #dff813;" in html_response.text
    assert "NOISE WINSTON VOICE WORKBENCH" in html_response.text
    assert 'class="intro-facts"' in html_response.text
    assert 'class="select-control"' in html_response.text
    assert ".field-row + .field { margin-top: 18px; }" in html_response.text
    assert ".field + .field { margin-top:" not in html_response.text
    assert html_response.text.count(">中文</option>") == 1
    assert "臺灣正體中文" not in html_response.text
    assert "簡體輸入" not in html_response.text


def test_generate_returns_audio_and_reproducible_metadata(tmp_path):
    runtime = FakeRuntime(tmp_path)
    payload = {
        "text": "同一個聲音可以測試不同情緒。",
        "language": "ZH-TW",
        "emotion_mode": "vector",
        "emotion_weight": "0.7",
        "emotion_vector": "[0.6,0,0,0,0,0,0,0.2]",
        "duration_factor": "1.1",
        "seed": "774",
    }

    with TestClient(create_app(runtime)) as client:
        response = client.post(
            "/api/generate",
            data=payload,
            files={"voice": ("voice.wav", b"fake-wave-data", "audio/wav")},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        audio_response = client.get(result["audio_url"])
        metadata_response = client.get(result["metadata_url"])

    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"].startswith("audio/wav")
    assert result["generation_seconds"] == 0.125
    assert result["audio_duration_seconds"] == 0.1
    assert result["options"]["seed"] == 774
    assert result["options"]["language"] == "ZH-TW"
    assert result["options"]["text"] == payload["text"]
    assert result["options"]["emotion_vector"][0] == 0.6
    assert metadata_response.json()["task_id"] == result["task_id"]
    assert len(runtime.generate_calls) == 1
    assert not (tmp_path / "uploads" / result["task_id"]).exists()

    metadata_path = tmp_path / f"{result['task_id']}.json"
    saved = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert saved["options"]["duration_factor"] == 1.1


def test_generate_rejects_requests_while_model_loads(tmp_path):
    runtime = FakeRuntime(tmp_path, state="loading")
    with TestClient(create_app(runtime)) as client:
        response = client.post(
            "/api/generate",
            data={"text": "test"},
            files={"voice": ("voice.wav", b"fake", "audio/wav")},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "模型載入中"


def test_reference_emotion_requires_second_audio_file(tmp_path):
    runtime = FakeRuntime(tmp_path)
    with TestClient(create_app(runtime)) as client:
        response = client.post(
            "/api/generate",
            data={"text": "test", "emotion_mode": "reference"},
            files={"voice": ("voice.wav", b"fake", "audio/wav")},
        )

    assert response.status_code == 422
    assert "情緒參考音檔" in response.json()["detail"]


def test_browser_empty_optional_emotion_upload_is_ignored(tmp_path):
    """Some browsers serialize an unselected file input as an empty blob."""
    runtime = FakeRuntime(tmp_path)
    with TestClient(create_app(runtime)) as client:
        response = client.post(
            "/api/generate",
            data={
                "text": "先別出聲，他就在門外。",
                "emotion_mode": "text",
                "emotion_text": "壓低聲音，緊張地提醒身邊的人",
            },
            files=[
                ("voice", ("MainOutput_2026-08-12_14-51-51.wav", b"valid-wave-fixture", "audio/wav")),
                ("emotion_audio", ("blob", b"", "application/octet-stream")),
            ],
        )

    assert response.status_code == 200, response.text
    assert len(runtime.generate_calls) == 1
    assert runtime.generate_calls[0][2] is None
