from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import ConfigError, list_format_presets, load_format_preset
from .media import MediaError, dependency_report
from .pipeline import PipelineContext, run_pipeline
from .project import create_project, open_project
from .subtitles import SubtitleError, write_summary, write_vtt_from_segments


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_command(args)
    except (ConfigError, FileExistsError, MediaError, SubtitleError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-video",
        description="Claude Code style Agent Video Editor pipeline.",
    )
    parser.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check external editing tools.")
    doctor.set_defaults(func=cmd_doctor)

    formats = subparsers.add_parser("formats", help="List available format presets.")
    formats.set_defaults(func=cmd_formats)

    init = subparsers.add_parser("init", help="Create a project folder for one editing job.")
    init.add_argument("job")
    init.add_argument("--format", choices=list_format_presets(), default="short-explainer")
    init.add_argument("--raw", type=Path, help="Raw clip to copy into projects/<job>/raw.")
    init.add_argument("--force", action="store_true", help="Overwrite project metadata if it already exists.")
    init.add_argument("--dry-run", action="store_true", help="Create manifests without copying media bytes.")
    init.set_defaults(func=cmd_init)

    run = subparsers.add_parser("run", help="Run the seven-step raw-to-final pipeline.")
    run.add_argument("job")
    run.add_argument("--format", choices=list_format_presets(), default="short-explainer")
    run.add_argument("--raw", type=Path, help="Raw clip to copy into projects/<job>/raw before running.")
    run.add_argument("--music", type=Path, help="Background music file to copy into the job.")
    run.add_argument("--force", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=cmd_run)

    status = subparsers.add_parser("status", help="Print project state.")
    status.add_argument("job")
    status.set_defaults(func=cmd_status)

    subs = subparsers.add_parser("fetch-subtitles", help="Fetch YouTube caption metadata and a summary.")
    subs.add_argument("url")
    subs.add_argument("--language", action="append", dest="languages", default=None)
    subs.add_argument("--output-dir", type=Path, default=Path("references"))
    subs.add_argument("--write-vtt", action="store_true", help="Write full VTT captions.")
    subs.add_argument("--i-own-rights", action="store_true", help="Required with --write-vtt.")
    subs.set_defaults(func=cmd_fetch_subtitles)

    return parser


def run_command(args: argparse.Namespace) -> dict[str, Any] | None:
    return args.func(args)


def cmd_doctor(args: argparse.Namespace) -> dict[str, Any]:
    optional_modules: dict[str, bool] = {}
    for module in ("youtube_transcript_api",):
        try:
            __import__(module)
            optional_modules[module] = True
        except ImportError:
            optional_modules[module] = False
    return {"tools": dependency_report(), "optional_python_modules": optional_modules}


def cmd_formats(args: argparse.Namespace) -> dict[str, Any]:
    return {"formats": {name: load_format_preset(name) for name in list_format_presets()}}


def cmd_init(args: argparse.Namespace) -> dict[str, Any]:
    project = create_project(
        Path(args.root),
        args.job,
        format_name=args.format,
        raw=args.raw,
        force=args.force,
        dry_run=args.dry_run,
    )
    return {"project": str(project.path), "state": str(project.state_path)}


def cmd_run(args: argparse.Namespace) -> dict[str, Any]:
    ctx = PipelineContext(
        root=Path(args.root).resolve(),
        job=args.job,
        format_name=args.format,
        dry_run=args.dry_run,
        raw=args.raw,
        music=args.music,
        force=args.force,
    )
    return run_pipeline(ctx)


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    project = open_project(Path(args.root), args.job)
    return project.read_state()


def cmd_fetch_subtitles(args: argparse.Namespace) -> dict[str, Any]:
    languages = args.languages or ["en"]
    summary = write_summary(args.url, args.output_dir, languages=languages)
    result = {"summary": str(summary)}
    if args.write_vtt:
        result["vtt"] = str(
            write_vtt_from_segments(
                args.url,
                args.output_dir,
                languages=languages,
                rights_confirmed=args.i_own_rights,
            )
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
