from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_format_preset, load_pipeline
from .files import write_json, write_text
from .media import burn_srt_captions, copy_media, mix_background_music, normalize_copy
from .project import EditorProject, create_project, open_project, primary_music, primary_raw


@dataclass
class PipelineContext:
    root: Path
    job: str
    format_name: str
    dry_run: bool
    raw: Path | None = None
    music: Path | None = None
    force: bool = False

    @property
    def project(self) -> EditorProject:
        return open_project(self.root, self.job)

    @property
    def preset(self) -> dict[str, Any]:
        return load_format_preset(self.format_name)


def run_pipeline(ctx: PipelineContext) -> dict[str, Any]:
    project = _ensure_project(ctx)
    state = project.read_state()
    pipeline = load_pipeline()

    for step in pipeline["steps"]:
        name = step["id"]
        if name == "intake":
            result = _step_intake(ctx, project, state)
        elif name == "rough_cut":
            result = _step_rough_cut(ctx, project, state)
        elif name == "graphics":
            result = _step_graphics(ctx, project, state)
        elif name == "second_pass":
            result = _step_second_pass(ctx, project, state)
        elif name == "captions":
            result = _step_captions(ctx, project, state)
        elif name == "background_music":
            result = _step_background_music(ctx, project, state)
        elif name == "export":
            result = _step_export(ctx, project, state)
        else:
            result = {"status": "skipped", "reason": f"Unknown step {name}"}

        state.setdefault("steps", {})[name] = {
            **result,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if result.get("current_media"):
            state["current_media"] = result["current_media"]
        if result.get("final_output"):
            state["final_output"] = result["final_output"]
        project.write_state(state)

    return state


def _ensure_project(ctx: PipelineContext) -> EditorProject:
    project = open_project(ctx.root, ctx.job)
    if project.path.exists():
        if ctx.raw:
            target = project.dir("raw") / ctx.raw.name
            copy_media(ctx.raw, target, dry_run=ctx.dry_run, label="intake")
            state = project.read_state()
            state["current_media"] = str(target)
            project.write_state(state)
        return project
    return create_project(
        ctx.root,
        ctx.job,
        format_name=ctx.format_name,
        raw=ctx.raw,
        force=ctx.force,
        dry_run=ctx.dry_run,
    )


def _current_media(project: EditorProject, state: dict[str, Any]) -> Path | None:
    current = state.get("current_media")
    if current:
        return Path(current)
    return primary_raw(project)


def _step_intake(ctx: PipelineContext, project: EditorProject, state: dict[str, Any]) -> dict[str, Any]:
    raw = primary_raw(project)
    staged = raw or (Path(state["current_media"]) if state.get("current_media") else None)
    if not staged:
        return {
            "status": "waiting",
            "reason": "No raw clip found. Put a video in projects/<job>/raw or rerun with --raw.",
        }
    return {"status": "done", "current_media": str(staged), "summary": "Raw clip staged in project raw folder."}


def _step_rough_cut(ctx: PipelineContext, project: EditorProject, state: dict[str, Any]) -> dict[str, Any]:
    source = _current_media(project, state)
    if not source:
        return {"status": "blocked", "reason": "Rough cut needs an intake clip."}

    target = project.dir("work") / "02-rough-cut.mp4"
    normalize_copy(source, target, dry_run=ctx.dry_run)
    write_json(
        project.dir("work") / "rough-cut-plan.json",
        {
            "step": "rough_cut",
            "engine": "WhisperX plus FFmpeg when available",
            "actions": ["transcribe", "remove filler and dead air", "polish audio", "draft script"],
            "source": str(source),
            "target": str(target),
            "dry_run": ctx.dry_run,
        },
    )
    write_text(
        project.dir("scripts") / "edit-script.md",
        "# Edit Script\n\n"
        "## Hook\n\nTBD from transcript.\n\n"
        "## Beats\n\n- Replace this with the cleaned narrative beats after WhisperX transcript review.\n",
    )
    return {"status": "done", "current_media": str(target), "summary": "Rough cut plan and working media created."}


def _step_graphics(ctx: PipelineContext, project: EditorProject, state: dict[str, Any]) -> dict[str, Any]:
    source = _current_media(project, state)
    if not source:
        return {"status": "blocked", "reason": "Graphics pass needs rough cut media."}

    preset = ctx.preset
    target = project.dir("work") / "03-graphics-pass.mp4"
    copy_media(source, target, dry_run=ctx.dry_run, label="graphics-pass")
    plan = {
        "step": "graphics",
        "format": ctx.format_name,
        "graphics_style": preset["graphics"],
        "beats": [
            {"at": "hook", "type": preset["graphics"]["primary"], "note": "Open with a format-specific hook graphic."},
            {"at": "body", "type": "callout", "note": "Use concise cards only when they clarify the spoken point."},
            {"at": "close", "type": "recap", "note": "Keep the last graphic short and export-safe."},
        ],
    }
    write_json(project.dir("graphics") / "graphics-plan.json", plan)
    write_json(
        project.dir("graphics") / "hyperframes-composition.json",
        {
            "engine": "hyperframes-compatible",
            "format": ctx.format_name,
            "canvas": preset["canvas"],
            "graphics": plan["beats"],
            "source": str(source),
            "target": str(target),
        },
    )
    return {"status": "done", "current_media": str(target), "summary": "Graphics plan and HyperFrames composition manifest created."}


def _step_second_pass(ctx: PipelineContext, project: EditorProject, state: dict[str, Any]) -> dict[str, Any]:
    source = _current_media(project, state)
    if not source:
        return {"status": "blocked", "reason": "Second pass needs graphics media."}

    target = project.dir("work") / "04-second-pass.mp4"
    copy_media(source, target, dry_run=ctx.dry_run, label="second-pass")
    write_text(
        project.dir("review") / "second-pass-checklist.md",
        "# Second Pass Checklist\n\n"
        "- Narrative is understandable without looking at the edit timeline.\n"
        "- Graphics appear only where they increase clarity.\n"
        "- Captions do not cover faces, UI, or important subject motion.\n"
        "- Audio peaks, silence, and music ducking are reviewed before export.\n",
    )
    return {"status": "done", "current_media": str(target), "summary": "Manual review checklist prepared."}


def _step_captions(ctx: PipelineContext, project: EditorProject, state: dict[str, Any]) -> dict[str, Any]:
    source = _current_media(project, state)
    if not source:
        return {"status": "blocked", "reason": "Caption pass needs reviewed media."}

    preset = ctx.preset
    captions = preset["captions"]
    if not captions["enabled"]:
        return {"status": "skipped", "current_media": str(source), "summary": "Format preset uses platform captions instead of burned-in captions."}

    target = project.dir("work") / "05-captioned.mp4"
    srt = project.dir("captions") / "captions.srt"
    if srt.exists():
        burn_srt_captions(source, srt, target, dry_run=ctx.dry_run)
    else:
        copy_media(source, target, dry_run=ctx.dry_run, label="caption-pass")
    write_json(
        project.dir("captions") / "captions-plan.json",
        {
            "step": "captions",
            "style": captions,
            "source_srt": str(srt),
            "target": str(target),
            "note": "Drop captions.srt here to burn captions; otherwise this step records the preset and passes media through.",
        },
    )
    return {"status": "done", "current_media": str(target), "summary": "Caption preset applied or staged."}


def _step_background_music(ctx: PipelineContext, project: EditorProject, state: dict[str, Any]) -> dict[str, Any]:
    source = _current_media(project, state)
    if not source:
        return {"status": "blocked", "reason": "Background music step needs media."}

    music = ctx.music
    if music:
        copied_music = project.dir("music") / music.name
        copy_media(music, copied_music, dry_run=ctx.dry_run, label="music-intake")
        music = copied_music
    else:
        music = primary_music(project)

    if not music:
        return {"status": "skipped", "current_media": str(source), "summary": "No background music provided."}

    target = project.dir("work") / "06-music-mix.mp4"
    mix_background_music(source, music, target, dry_run=ctx.dry_run)
    write_json(
        project.dir("music") / "background-music-plan.json",
        {
            "step": "background_music",
            "music": str(music),
            "ducking": "sidechain duck under voice",
            "target": str(target),
        },
    )
    return {"status": "done", "current_media": str(target), "summary": "Background music staged with ducking plan."}


def _step_export(ctx: PipelineContext, project: EditorProject, state: dict[str, Any]) -> dict[str, Any]:
    source = _current_media(project, state)
    if not source:
        return {"status": "blocked", "reason": "Export needs final media."}

    project_target = project.dir("exports") / f"{ctx.job}.final.mp4"
    root_target = ctx.root / "outputs" / f"{ctx.job}.final.mp4"
    copy_media(source, project_target, dry_run=ctx.dry_run, label="project-export")
    copy_media(project_target, root_target, dry_run=ctx.dry_run, label="final-export")
    write_json(
        project.dir("exports") / "export-manifest.json",
        {
            "step": "export",
            "format": ctx.format_name,
            "source": str(source),
            "project_output": str(project_target),
            "final_output": str(root_target),
            "dry_run": ctx.dry_run,
        },
    )
    return {
        "status": "done",
        "current_media": str(project_target),
        "final_output": str(root_target),
        "summary": "Final output promoted to outputs folder.",
    }
