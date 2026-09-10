from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


JOB_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,80}$")


def require_job_name(job: str) -> str:
    if not JOB_RE.match(job):
        raise ValueError(
            "Job names may contain letters, numbers, dots, underscores, and dashes, "
            "and must start with a letter or number."
        )
    return job


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: dict[str, Any]) -> Path:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> Path:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8", newline="\n")
    return path
