from __future__ import annotations

import json
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.kie.ai"
CREATE_TASK_PATH = "/api/v1/jobs/createTask"
TASK_DETAIL_PATH = "/api/v1/jobs/recordInfo"
TERMINAL_STATES = {"success", "fail"}


class KieApiError(RuntimeError):
    """Raised when KIE AI returns an error or cannot be reached."""


@dataclass(frozen=True)
class KieClient:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout: int = 60

    @classmethod
    def from_env(cls) -> "KieClient":
        load_dotenv()
        api_key = os.getenv("KIE_API_KEY", "").strip()
        if not api_key or api_key == "replace_with_your_kie_ai_api_key":
            raise KieApiError(
                "Missing KIE_API_KEY. Copy .env.example to .env and set your KIE AI API key, "
                "or set KIE_API_KEY in the current shell."
            )
        base_url = os.getenv("KIE_API_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
        return cls(api_key=api_key, base_url=base_url.rstrip("/"))

    def create_task(
        self,
        *,
        prompt: str,
        model: str = "bytedance/seedance-2",
        callback_url: str | None = None,
        first_frame_url: str | None = None,
        last_frame_url: str | None = None,
        reference_image_urls: list[str] | None = None,
        reference_video_urls: list[str] | None = None,
        reference_audio_urls: list[str] | None = None,
        return_last_frame: bool | None = None,
        generate_audio: bool | None = None,
        resolution: str | None = None,
        aspect_ratio: str | None = None,
        duration: int | None = None,
        web_search: bool | None = None,
    ) -> dict[str, Any]:
        input_payload: dict[str, Any] = {"prompt": prompt}
        optional_fields: dict[str, Any] = {
            "first_frame_url": first_frame_url,
            "last_frame_url": last_frame_url,
            "reference_image_urls": reference_image_urls,
            "reference_video_urls": reference_video_urls,
            "reference_audio_urls": reference_audio_urls,
            "return_last_frame": return_last_frame,
            "generate_audio": generate_audio,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "web_search": web_search,
        }
        input_payload.update(
            {key: value for key, value in optional_fields.items() if value not in (None, [], "")}
        )

        payload: dict[str, Any] = {"model": model, "input": input_payload}
        if callback_url:
            payload["callBackUrl"] = callback_url
        return self._request_json("POST", CREATE_TASK_PATH, payload)

    def get_task(self, task_id: str) -> dict[str, Any]:
        path = f"{TASK_DETAIL_PATH}?{urlencode({'taskId': task_id})}"
        return self._request_json("GET", path)

    def wait_for_task(
        self,
        task_id: str,
        *,
        poll_interval: int = 5,
        timeout_seconds: int = 900,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last_response: dict[str, Any] | None = None

        while time.monotonic() < deadline:
            response = self.get_task(task_id)
            last_response = response
            state = task_state(response)
            if state in TERMINAL_STATES:
                return response
            time.sleep(poll_interval)

        state = task_state(last_response) if last_response else "unknown"
        raise KieApiError(f"Timed out waiting for task {task_id}; last state: {state}")

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise KieApiError(f"KIE API HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise KieApiError(f"Could not reach KIE API: {exc.reason}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise KieApiError(f"KIE API returned non-JSON response: {raw[:500]}") from exc

        if data.get("code") not in (None, 200):
            raise KieApiError(f"KIE API error {data.get('code')}: {data.get('msg') or data}")
        return data


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def task_data(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def task_state(response: dict[str, Any] | None) -> str:
    if not response:
        return "unknown"
    return str(task_data(response).get("state", "unknown"))


def task_id_from_response(response: dict[str, Any]) -> str:
    task_id = task_data(response).get("taskId")
    if not task_id:
        raise KieApiError(f"Could not find taskId in response: {response}")
    return str(task_id)


def result_urls(response: dict[str, Any]) -> list[str]:
    result_json = task_data(response).get("resultJson")
    if not result_json:
        return []

    parsed: Any
    if isinstance(result_json, str):
        try:
            parsed = json.loads(result_json)
        except json.JSONDecodeError:
            return []
    else:
        parsed = result_json

    urls: list[str] = []
    if isinstance(parsed, dict):
        for key in ("resultUrls", "result_urls", "urls", "videoUrls", "video_urls"):
            value = parsed.get(key)
            if isinstance(value, list):
                urls.extend(str(item) for item in value if item)
            elif isinstance(value, str):
                urls.append(value)
    elif isinstance(parsed, list):
        urls.extend(str(item) for item in parsed if item)
    return urls


def download_urls(urls: list[str], output_dir: str | Path) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    for index, url in enumerate(urls, start=1):
        request = Request(url, headers={"User-Agent": "seedance-kie-client/0.1"})
        with urlopen(request, timeout=120) as response:
            content_type = response.headers.get("Content-Type", "")
            suffix = _suffix_from_url_or_type(url, content_type)
            target = output_path / f"seedance_result_{index}{suffix}"
            target.write_bytes(response.read())
            downloaded.append(target)
    return downloaded


def _suffix_from_url_or_type(url: str, content_type: str) -> str:
    url_path = url.split("?", 1)[0].rstrip("/")
    suffix = Path(url_path).suffix
    if suffix:
        return suffix
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
    return guessed or ".mp4"
