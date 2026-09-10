from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import load_format_preset
from .files import ensure_dir, read_json, require_job_name, write_json, write_text
from .media import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, copy_media, find_media_file


PROJECT_DIRS = (
    "raw",
    "work",
    "scripts",
    "graphics",
    "captions",
    "music",
    "review",
    "premiere",
    "exports",
    "logs",
    "tmp",
)


@dataclass(frozen=True)
class EditorProject:
    root: Path
    job: str

    @property
    def path(self) -> Path:
        return self.root / "projects" / self.job

    @property
    def state_path(self) -> Path:
        return self.path / "state.json"

    @property
    def config_path(self) -> Path:
        return self.path / "project.json"

    def dir(self, name: str) -> Path:
        return self.path / name

    def read_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            return read_json(self.state_path)
        return {"job": self.job, "steps": {}, "current_media": None}

    def write_state(self, state: dict[str, Any]) -> Path:
        return write_json(self.state_path, state)


def open_project(root: Path, job: str) -> EditorProject:
    return EditorProject(root=root.resolve(), job=require_job_name(job))


def create_project(
    root: Path,
    job: str,
    *,
    format_name: str,
    raw: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> EditorProject:
    project = open_project(root, job)
    if project.path.exists() and not force:
        raise FileExistsError(f"Project already exists: {project.path}")

    for dirname in PROJECT_DIRS:
        ensure_dir(project.dir(dirname))
    ensure_dir(root / "outputs")

    preset = load_format_preset(format_name)
    config = {
        "job": job,
        "format": format_name,
        "format_preset": preset,
        "created_by": "agent-video",
    }
    write_json(project.config_path, config)

    raw_target: str | None = None
    if raw:
        target = project.dir("raw") / raw.name
        copy_media(raw, target, dry_run=dry_run, label="intake")
        raw_target = str(target)
    else:
        write_text(project.dir("raw") / "DROP_RAW_CLIP_HERE.txt", "Place the raw video clip for this job in this folder.\n")

    project.write_state(
        {
            "job": job,
            "format": format_name,
            "steps": {},
            "current_media": raw_target,
            "final_output": None,
        }
    )
    return project


def primary_raw(project: EditorProject) -> Path | None:
    return find_media_file(project.dir("raw"), VIDEO_EXTENSIONS)


def primary_music(project: EditorProject) -> Path | None:
    return find_media_file(project.dir("music"), AUDIO_EXTENSIONS)
