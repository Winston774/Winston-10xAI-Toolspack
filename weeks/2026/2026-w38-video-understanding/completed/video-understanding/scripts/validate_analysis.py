#!/usr/bin/env python3
"""Validate a video-understanding index. No model calls or semantic verification."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys


def validate(data, base):
    errors = []
    base = Path(base).resolve()

    def error(where, message):
        errors.append(f"{where}: {message}")

    def obj(value, where):
        if not isinstance(value, dict):
            error(where, "must be an object")
            return {}
        return value

    def array(value, where):
        if not isinstance(value, list):
            error(where, "must be an array")
            return []
        return value

    def string(value, where):
        if not isinstance(value, str) or not value.strip():
            error(where, "must be a nonempty string")
            return ""
        return value

    def boolean(value, where):
        if type(value) is not bool:
            error(where, "must be a boolean")

    def number(value):
        try:
            return type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            return False

    def choice(value, values, where):
        if not isinstance(value, str) or value not in values:
            error(where, "must be one of " + ", ".join(sorted(values)))

    def strings(value, where):
        values = array(value, where)
        return [string(item, f"{where}[{i}]") for i, item in enumerate(values)]

    data = obj(data, "root")
    if data.get("schema_version") != "1.0":
        error("schema_version", "must be 1.0")
    source = obj(data.get("source"), "source")
    string(source.get("path"), "source.path")
    if not isinstance(source.get("sha256"), str) or not re.fullmatch(r"[a-fA-F0-9]{64}", source["sha256"]):
        error("source.sha256", "must be a SHA-256 hex digest")
    duration = source.get("duration_seconds")
    if not number(duration) or duration <= 0:
        error("source.duration_seconds", "must be finite and positive")
        duration = 0
    choice(source.get("clock"), {"video_start"}, "source.clock")
    boolean(source.get("audio_present"), "source.audio_present")

    def interval(row, where, point=False, frame=False):
        start, end = row.get("start"), row.get("end")
        if not number(start) or not number(end):
            error(where, "start/end must be finite numbers")
            return None
        if start < 0 or end > duration + 0.001 or end < start or (end == start and not point):
            error(where, "invalid interval or outside source duration")
            return None
        if frame and (start != end or start >= duration):
            error(where, "frame evidence must be a single timestamp strictly before duration")
            return None
        return (start, end)

    def covers(ranges, start=0.0, end=None):
        end = duration if end is None else end
        if not ranges or end <= start:
            return False
        cursor, uncovered = start, 0.0
        for left, right in sorted(ranges):
            if right <= start or left >= end:
                continue
            left, right = max(start, left), min(end, right)
            uncovered += max(0.0, left - cursor)
            cursor = max(cursor, right)
        uncovered += max(0.0, end - cursor)
        return uncovered <= min(0.001, (end - start) * 0.001)

    def evidence_bounds(ids):
        result = []
        for ident in ids:
            row = registry["evidence"].get(ident, {})
            left, right = row.get("start"), row.get("end")
            if number(left) and number(right) and right >= left:
                result.append((left, right))
        return result

    registry = {}
    for name in ("evidence", "systems", "events", "assets", "unknowns"):
        registry[name] = {}
        for i, raw in enumerate(array(data.get(name), name)):
            where = f"{name}[{i}]"
            row = obj(raw, where)
            ident = string(row.get("id"), where + ".id")
            if ident in registry[name]:
                error(where, f"duplicate id {ident}")
            if ident:
                registry[name][ident] = row

    def refs(row, key, target, where, nonempty=False, reviewed=False):
        ids = strings(row.get(key), where + "." + key)
        if nonempty and not ids:
            error(where + "." + key, "requires at least one reference")
        for ident in ids:
            if ident not in registry[target]:
                error(where, f"unknown {target} reference {ident}")
            elif reviewed and registry[target][ident].get("reviewed") is not True:
                error(where, f"evidence {ident} has not been reviewed")
        return ids

    for ident, row in registry["evidence"].items():
        where = "evidence." + ident
        choice(row.get("kind"), {"frame", "clip", "audio", "transcript", "metadata"}, where + ".kind")
        interval(row, where, point=row.get("kind") == "frame", frame=row.get("kind") == "frame")
        boolean(row.get("reviewed"), where + ".reviewed")
        path = string(row.get("path"), where + ".path")
        try:
            resolved = (base / path).resolve()
            if Path(path).is_absolute() or not resolved.is_relative_to(base):
                error(where + ".path", "must remain relative and inside the analysis directory")
            elif not resolved.is_file():
                error(where + ".path", "evidence file does not exist")
        except (OSError, ValueError):
            error(where + ".path", "invalid evidence path")

    for ident, row in registry["systems"].items():
        choice(row.get("role"), {"a_roll", "b_roll", "caption", "typography", "mg_ui", "effect", "audio"}, "systems." + ident)
        string(row.get("description"), "systems." + ident + ".description")

    event_ranges = []
    for ident, row in registry["events"].items():
        where = "events." + ident
        bounds = interval(row, where)
        if bounds:
            event_ranges.append(bounds)
        refs(row, "system_ids", "systems", where, nonempty=True)
        ids = refs(row, "evidence_ids", "evidence", where, nonempty=True, reviewed=True)
        if bounds and not any(right >= bounds[0] and left < bounds[1] for left, right in evidence_bounds(ids)):
            error(where, "no cited evidence overlaps this event")
        for key in ("observed", "interpretation"):
            string(row.get(key), where + "." + key)
        choice(row.get("confidence"), {"high", "medium", "low"}, where + ".confidence")
        anchor = obj(row.get("anchor"), where + ".anchor")
        choice(anchor.get("kind"), {"speech", "action", "clock"}, where + ".anchor.kind")
        string(anchor.get("cue"), where + ".anchor.cue")
        choice(anchor.get("timing_precision"), {"frame_verified", "aligned", "estimated"}, where + ".anchor.timing_precision")
        cited_kinds = {registry["evidence"][i].get("kind") for i in ids if i in registry["evidence"] and isinstance(registry["evidence"][i].get("kind"), str)}
        if anchor.get("timing_precision") == "frame_verified" and not cited_kinds.intersection({"frame", "clip"}):
            error(where, "frame_verified requires frame/clip evidence")
        if anchor.get("kind") == "speech" and not cited_kinds.intersection({"audio", "clip", "transcript"}):
            error(where, "speech anchor requires audio/clip/transcript evidence")
        if anchor.get("timing_precision") == "aligned" and not cited_kinds.intersection({"audio", "transcript"}):
            error(where, "aligned timing requires audio/transcript evidence")
        occurrence = anchor.get("occurrence")
        if anchor.get("kind") == "clock":
            if occurrence is not None:
                error(where, "clock occurrence must be null")
        elif type(occurrence) is not int or occurrence < 1:
            error(where, "speech/action occurrence must be a positive integer")

    for ident, row in registry["assets"].items():
        where = "assets." + ident
        for key in ("kind", "description", "generation_brief"):
            string(row.get(key), where + "." + key)
        refs(row, "event_ids", "events", where, nonempty=True)
        refs(row, "depends_on", "assets", where)

    visited, active = set(), set()

    def visit(ident):
        if ident in active:
            error("assets", "cyclic dependency at " + ident)
            return
        if ident in visited:
            return
        active.add(ident)
        deps = registry["assets"][ident].get("depends_on")
        for dep in deps if isinstance(deps, list) else []:
            if isinstance(dep, str) and dep in registry["assets"]:
                visit(dep)
        active.remove(ident)
        visited.add(ident)

    for ident in registry["assets"]:
        visit(ident)

    blockers = []
    for ident, row in registry["unknowns"].items():
        where = "unknowns." + ident
        string(row.get("question"), where + ".question")
        interval(row, where, point=True)
        boolean(row.get("blocks_generation"), where + ".blocks_generation")
        if row.get("blocks_generation") is True:
            blockers.append(ident)

    inspected = {"video": [], "audio": []}
    inspection = obj(data.get("inspection"), "inspection")
    kinds = {"playback": {"clip"}, "dense_frames": {"frame"}, "sampled_frames": {"frame"}, "listened": {"audio", "clip"}, "transcript_only": {"transcript"}}
    for channel in inspected:
        rows = array(inspection.get(channel), "inspection." + channel)
        if channel == "audio" and source.get("audio_present") is False and rows:
            error("inspection.audio", "must be empty when source has no audio stream")
        for i, raw in enumerate(rows):
            where = f"inspection.{channel}[{i}]"
            row = obj(raw, where)
            bounds = interval(row, where)
            allowed = {"playback", "dense_frames", "sampled_frames"} if channel == "video" else {"listened", "transcript_only"}
            method = row.get("method")
            choice(method, allowed, where + ".method")
            ids = refs(row, "evidence_ids", "evidence", where, nonempty=True, reviewed=True)
            for ident in ids:
                evidence = registry["evidence"].get(ident, {})
                if isinstance(method, str) and evidence.get("kind") not in kinds.get(method, set()):
                    error(where, f"evidence {ident} kind does not support {method}")
            spans = evidence_bounds(ids)
            if bounds and method in ("playback", "listened", "transcript_only") and not covers(spans, *bounds):
                error(where, "cited evidence does not cover the declared inspection interval")
            if bounds and method in ("dense_frames", "sampled_frames"):
                points = sorted({left for left, right in spans if left == right and bounds[0] <= left < bounds[1]})
                if not points:
                    error(where, "no cited frame lies inside the inspection interval")
                if method == "dense_frames":
                    if len(points) < 2:
                        error(where, "dense_frames requires at least two distinct frame timestamps")
                    maximum = row.get("max_gap_seconds")
                    edges = [bounds[0], *points, bounds[1]]
                    actual = max(b - a for a, b in zip(edges, edges[1:]))
                    if not number(maximum) or maximum <= 0 or abs(maximum - actual) > 1e-6:
                        error(where, f"max_gap_seconds must equal measured frame/boundary gap {actual:.9g}")
            if bounds and method in ("playback", "dense_frames", "listened"):
                inspected[channel].append(bounds)

    handoff = obj(data.get("handoff"), "handoff")
    choice(handoff.get("status"), {"ready", "partial"}, "handoff.status")
    for key in ("invariants", "changeable", "next_steps"):
        strings(handoff.get(key), "handoff." + key)

    if handoff.get("status") == "ready":
        for key, ranges in (("events", event_ranges), ("inspection.video", inspected["video"])):
            if not covers(ranges):
                error(key, "ready requires full-duration coverage")
        if source.get("audio_present") is True and not covers(inspected["audio"]):
            error("inspection.audio", "ready requires full-duration listening")
        if blockers:
            error("handoff", "ready has blocking unknowns: " + ", ".join(blockers))
        if not registry["assets"]:
            error("assets", "ready requires generation requirements")
        if not handoff.get("invariants"):
            error("handoff.invariants", "ready requires preservation rules")
    elif not handoff.get("next_steps"):
        error("handoff.next_steps", "partial requires a next action")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--source", type=Path, help="also verify the supplied original file's SHA-256")
    args = parser.parse_args()
    try:
        data = json.loads(args.analysis.read_text(encoding="utf-8-sig"))
        errors = validate(data, args.analysis.parent)
        if args.source:
            digest = hashlib.sha256()
            with args.source.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            source = data.get("source") if isinstance(data, dict) else None
            expected = source.get("sha256", "") if isinstance(source, dict) else ""
            if digest.hexdigest() != str(expected).lower():
                errors.append("source.sha256: supplied file does not match")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("\n".join("ERROR: " + e for e in errors), file=sys.stderr)
        return 1
    print(f"VALID ({data['handoff']['status']}): structure only; audiovisual and semantic quality not verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
