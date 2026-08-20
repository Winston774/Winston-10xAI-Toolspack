#!/usr/bin/env python3
"""Validate a kinetic character-reveal prompt using only the Python standard library."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

CUT_RE = re.compile(
    r"CUT\s+(\d{1,2})\s*\|\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*s",
    re.IGNORECASE,
)


def contains_any(text: str, terms: Iterable[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a motion-graphics character reveal prompt.")
    parser.add_argument("prompt", type=Path, help="Path to a UTF-8 text or Markdown prompt")
    parser.add_argument("--cuts", type=int, default=13, help="Expected cut count")
    parser.add_argument("--duration", type=float, default=15.0, help="Expected total duration in seconds")
    parser.add_argument("--fps", type=int, default=24, help="Expected frames per second")
    parser.add_argument("--aspect", default="16:9", help="Expected aspect-ratio token")
    args = parser.parse_args()

    if not args.prompt.exists():
        print(f"ERROR: file not found: {args.prompt}")
        return 2

    text = args.prompt.read_text(encoding="utf-8")
    matches = list(CUT_RE.finditer(text))
    errors: list[str] = []
    warnings: list[str] = []

    if len(matches) != args.cuts:
        errors.append(f"Expected {args.cuts} cuts, found {len(matches)}.")

    numbers = [int(m.group(1)) for m in matches]
    expected_numbers = list(range(1, args.cuts + 1))
    if numbers != expected_numbers:
        errors.append(f"Cut numbering is not sequential: {numbers}")

    spans = [(float(m.group(2)), float(m.group(3))) for m in matches]
    tolerance = 0.011
    if spans:
        if abs(spans[0][0] - 0.0) > tolerance:
            errors.append(f"First cut starts at {spans[0][0]:.2f}s, expected 0.00s.")
        for index, ((start, end), next_span) in enumerate(zip(spans, spans[1:]), start=1):
            if end <= start:
                errors.append(f"CUT {index:02d} has non-positive duration: {start:.2f}-{end:.2f}s.")
            next_start = next_span[0]
            if abs(end - next_start) > tolerance:
                relation = "gap" if next_start > end else "overlap"
                errors.append(
                    f"Timeline {relation} between CUT {index:02d} and CUT {index + 1:02d}: "
                    f"{end:.2f}s vs {next_start:.2f}s."
                )
        if spans[-1][1] <= spans[-1][0]:
            errors.append("Final cut has non-positive duration.")
        if abs(spans[-1][1] - args.duration) > tolerance:
            errors.append(
                f"Final cut ends at {spans[-1][1]:.2f}s, expected {args.duration:.2f}s."
            )

    normalized_aspect = args.aspect.replace(" ", "")
    if normalized_aspect not in text.replace(" ", ""):
        errors.append(f"Missing aspect ratio token: {args.aspect}")

    fps_patterns = [f"{args.fps}fps", f"{args.fps} fps"]
    if not contains_any(text, fps_patterns):
        errors.append(f"Missing fps declaration: {args.fps}fps")

    if not ("80%" in text and "20%" in text):
        warnings.append("Missing explicit 80% motion-graphics / 20% character ratio.")

    if not contains_any(text, ["preserve", "never redesign", "identity lock", "exact face"]):
        errors.append("Missing an explicit character identity lock.")

    if not contains_any(text, ["palette:", "palette", "色盤"]):
        warnings.append("No explicit palette declaration detected.")

    if not contains_any(text, ["typography", "kinetic type", "kinetic typography", "動態字體"]):
        warnings.append("No kinetic typography language detected.")

    if not contains_any(text, ["beat", "percussive", "snap", "on the beat", "逐拍", "節拍"]):
        warnings.append("No explicit beat-synchronization or percussive motion language detected.")

    if not contains_any(text, ["freeze", "frozen", "凍結"]):
        warnings.append("No freeze beat detected.")
    if not contains_any(text, ["release", "releases", "burst", "釋放"]):
        warnings.append("No release beat detected.")

    banned_drift = [
        "different outfit",
        "new outfit in each shot",
        "alternate hairstyle",
        "changes hair color",
        "costume changes",
        "warm rainbow palette",
        "soft dissolve",
        "long dialogue",
    ]
    lower_text = text.lower()
    for term in banned_drift:
        for match in re.finditer(re.escape(term), lower_text):
            sentence_start = max(
                lower_text.rfind(".", 0, match.start()),
                lower_text.rfind("!", 0, match.start()),
                lower_text.rfind("?", 0, match.start()),
                lower_text.rfind("\n", 0, match.start()),
            )
            clause = lower_text[sentence_start + 1 : match.start()].strip()
            negated = (
                clause.startswith(("no ", "never ", "avoid ", "without ", "do not ", "don't "))
                or re.search(r"\b(no|never|avoid|without|do not|don't)\b[^.;!?\n]{0,160}$", clause)
            )
            if not negated:
                warnings.append(f"Possible style-drift phrase detected: '{term}'.")
                break

    descriptions: list[str] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        desc = re.sub(r"\s+", " ", text[start:end]).strip(" -–—|\n\r\t")
        descriptions.append(desc)
        if len(desc) < 35:
            warnings.append(f"CUT {idx + 1:02d} description may be too thin ({len(desc)} chars).")

    duplicates: list[tuple[int, int]] = []
    normalized = [re.sub(r"[^a-z0-9]+", " ", d.lower()).strip() for d in descriptions]
    for i in range(len(normalized)):
        for j in range(i + 1, len(normalized)):
            if normalized[i] and normalized[i] == normalized[j]:
                duplicates.append((i + 1, j + 1))
    if duplicates:
        errors.append(f"Duplicate cut descriptions detected: {duplicates}")

    print("Kinetic Character Reveal Prompt Validator")
    print(f"File: {args.prompt}")
    print(f"Cuts detected: {len(matches)}")
    if spans:
        print(f"Timeline detected: {spans[0][0]:.2f}-{spans[-1][1]:.2f}s")

    if warnings:
        print("\nWARNINGS")
        for item in warnings:
            print(f"- {item}")

    if errors:
        print("\nFAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("\nPASS")
    print("- Required structural checks succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
