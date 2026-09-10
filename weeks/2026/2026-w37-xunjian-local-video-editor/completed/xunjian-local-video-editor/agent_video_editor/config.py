from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
PRESETS_ROOT = PACKAGE_ROOT / "presets"


class ConfigError(RuntimeError):
    """Raised when a preset or pipeline config is invalid."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Missing config file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Expected JSON object in {path}")
    return data


def load_pipeline() -> dict[str, Any]:
    return read_json(PACKAGE_ROOT / "pipeline.json")


def load_format_preset(name: str) -> dict[str, Any]:
    path = PRESETS_ROOT / "formats" / f"{name}.json"
    preset = read_json(path)
    if preset.get("name") != name:
        raise ConfigError(f"Preset {path} must declare name={name!r}")
    return preset


def list_format_presets() -> list[str]:
    root = PRESETS_ROOT / "formats"
    return sorted(path.stem for path in root.glob("*.json"))


def load_style_preset(name: str) -> dict[str, Any]:
    return read_json(PRESETS_ROOT / "styles" / f"{name}.json")
