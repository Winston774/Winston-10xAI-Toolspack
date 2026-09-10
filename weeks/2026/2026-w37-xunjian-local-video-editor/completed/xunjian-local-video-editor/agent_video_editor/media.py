from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .files import ensure_dir, write_json


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac"}


class MediaError(RuntimeError):
    """Raised when a media operation cannot be completed."""


def tool_path(name: str) -> str | None:
    load_dotenv()
    for candidate in _explicit_tool_candidates(name):
        if _path_is_probable_file(candidate):
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found

    for candidate in _tool_candidates(name):
        if _path_is_probable_file(candidate):
            return str(candidate)
    return None


def dependency_report() -> dict[str, dict[str, str | bool | None]]:
    tools = ("ffmpeg", "ffprobe", "whisperx", "yt-dlp")
    report: dict[str, dict[str, str | bool | None]] = {}
    for name in tools:
        path = tool_path(name)
        report[name] = {"available": bool(path), "path": path, "version": tool_version(path) if path else None}
    return report


def tool_version(path: str | None) -> str | None:
    if not path:
        return None
    try:
        executable = Path(path).name.lower()
        flag = "--version" if ("yt-dlp" in executable or "whisperx" in executable) else "-version"
        completed = subprocess.run([path, flag], text=True, capture_output=True, timeout=10)
        output = completed.stdout or completed.stderr
        return output.splitlines()[0] if output else None
    except (OSError, subprocess.TimeoutExpired):
        return None


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


def _explicit_tool_candidates(name: str) -> list[Path]:
    exe_names = _executable_names(name)
    candidates: list[Path] = []
    explicit_env = {
        "ffmpeg": ("AGENT_VIDEO_FFMPEG", "FFMPEG_PATH"),
        "ffprobe": ("AGENT_VIDEO_FFPROBE", "FFPROBE_PATH"),
        "whisperx": ("AGENT_VIDEO_WHISPERX", "WHISPERX_PATH"),
        "yt-dlp": ("AGENT_VIDEO_YT_DLP", "YT_DLP_PATH", "YTDLP_PATH"),
    }.get(name, ())

    for key in explicit_env:
        value = os.getenv(key)
        if value:
            candidates.extend(_expand_tool_value(value, exe_names))
    return candidates


def _tool_candidates(name: str) -> list[Path]:
    exe_names = _executable_names(name)
    candidates = _explicit_tool_candidates(name)

    for key in ("AGENT_VIDEO_TOOL_DIRS", "TOOL_DIRS"):
        value = os.getenv(key)
        if value:
            for directory in value.split(os.pathsep):
                candidates.extend(_paths_from_dir(Path(directory), exe_names))

    for directory in os.getenv("PATH", "").split(os.pathsep):
        if directory:
            candidates.extend(_paths_from_dir(Path(directory), exe_names))

    home = Path.home()
    local_app = Path(os.getenv("LOCALAPPDATA", home / "AppData" / "Local"))
    app_data = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
    common_dirs = [
        Path.cwd() / ".venv" / "Scripts",
        Path.cwd() / ".venv" / "bin",
        Path("C:/ffmpeg/bin"),
        Path("D:/ffmpeg/bin"),
        Path("D:/tools/ffmpeg/bin"),
        Path("C:/ProgramData/chocolatey/bin"),
        home / "scoop" / "shims",
        local_app / "Microsoft" / "WinGet" / "Links",
    ]
    if name == "yt-dlp":
        common_dirs.extend(
            [
                local_app / "Programs" / "Python" / "Python312" / "Scripts",
                app_data / "Python" / "Python312" / "Scripts",
                local_app / "Programs" / "Python" / "Python311" / "Scripts",
                app_data / "Python" / "Python311" / "Scripts",
            ]
        )

    for directory in common_dirs:
        candidates.extend(_paths_from_dir(directory, exe_names))
    return candidates


def _executable_names(name: str) -> list[str]:
    if os.name == "nt":
        return [name, f"{name}.exe", f"{name}.cmd", f"{name}.bat"]
    return [name]


def _expand_tool_value(value: str, exe_names: list[str]) -> list[Path]:
    path = Path(value).expanduser()
    if path.suffix or path.name in exe_names:
        return [path]
    return _paths_from_dir(path, exe_names)


def _paths_from_dir(directory: Path, exe_names: list[str]) -> list[Path]:
    expanded = directory.expanduser()
    return [expanded / exe_name for exe_name in exe_names]


def _path_is_probable_file(path: Path) -> bool:
    try:
        return path.exists() and path.is_file()
    except OSError:
        # Managed sandboxes can deny stat() for user-level install folders even when
        # the command exists. Return it as a probable path so doctor can report it.
        return bool(path.suffix)


def find_media_file(directory: Path, extensions: set[str]) -> Path | None:
    if not directory.exists():
        return None
    candidates = [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in extensions]
    return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[0] if candidates else None


def copy_media(source: Path, target: Path, *, dry_run: bool = False, label: str = "copy") -> Path:
    ensure_dir(target.parent)
    if dry_run:
        write_json(
            target.with_suffix(target.suffix + ".operation.json"),
            {
                "operation": label,
                "mode": "dry-run",
                "source": str(source),
                "target": str(target),
            },
        )
        return target
    if not source.exists():
        raise MediaError(f"Missing media source: {source}")
    shutil.copy2(source, target)
    return target


def run_ffmpeg(args: list[str]) -> None:
    ffmpeg = tool_path("ffmpeg")
    if not ffmpeg:
        raise MediaError("ffmpeg is not installed or not on PATH.")
    try:
        completed = subprocess.run([ffmpeg, *args], text=True, capture_output=True)
    except OSError as exc:
        raise MediaError(f"Could not execute ffmpeg at {ffmpeg}: {exc}") from exc
    if completed.returncode != 0:
        raise MediaError(completed.stderr.strip() or "ffmpeg failed.")


def normalize_copy(source: Path, target: Path, *, dry_run: bool = False) -> Path:
    if dry_run or not tool_path("ffmpeg"):
        return copy_media(source, target, dry_run=dry_run, label="normalize-copy")
    ensure_dir(target.parent)
    run_ffmpeg(["-y", "-i", str(source), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(target)])
    return target


def burn_srt_captions(source: Path, srt: Path, target: Path, *, dry_run: bool = False) -> Path:
    if dry_run or not tool_path("ffmpeg"):
        return copy_media(source, target, dry_run=dry_run, label="burn-captions")
    if not srt.exists():
        raise MediaError(f"Missing SRT caption file: {srt}")
    escaped = str(srt).replace("\\", "/").replace(":", r"\:")
    run_ffmpeg(["-y", "-i", str(source), "-vf", f"subtitles='{escaped}'", "-c:a", "copy", str(target)])
    return target


def mix_background_music(source: Path, music: Path, target: Path, *, dry_run: bool = False) -> Path:
    if dry_run or not tool_path("ffmpeg"):
        return copy_media(source, target, dry_run=dry_run, label="background-music")
    if not music.exists():
        raise MediaError(f"Missing music file: {music}")
    filter_graph = (
        "[1:a]volume=0.18[music];"
        "[0:a][music]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=500[mix]"
    )
    run_ffmpeg(
        [
            "-y",
            "-i",
            str(source),
            "-stream_loop",
            "-1",
            "-i",
            str(music),
            "-filter_complex",
            filter_graph,
            "-map",
            "0:v",
            "-map",
            "[mix]",
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            str(target),
        ]
    )
    return target
