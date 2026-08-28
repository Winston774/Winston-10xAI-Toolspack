#!/usr/bin/env python3
"""Initialize a Mastery Loop workspace without overwriting files."""

from __future__ import annotations

import argparse
from pathlib import Path


MISSION_TEMPLATE = """# Mission: {topic}

Goal intent: unselected

## Why
{why}

## Success looks like
- To define with learner: an observable real-world performance.

## Constraints
- To define with learner: time, tools, deadline, accessibility, or risk.

## Out of scope
- To define with learner: adjacent topics to defer.
"""

KNOWLEDGE_MAP_TEMPLATE = """# Knowledge Map: {topic}

Benchmark status: provisional
Last verified: NOT VERIFIED

| Concept / performance | Kernel ID | Scenario ID | Required | Prerequisites | Failure signal | Source |
|---|---|---|---:|---|---|---|
| To define with learner | TODO | TODO | T | To define | To define | NOT VERIFIED |

## Open benchmark gaps
- Define mission-critical concepts and verify them against authoritative sources.
"""

MASTERY_TEMPLATE = """# Mastery State: {topic}

Mode: {mode}
Session status: active
Cycle position: {cycle_position}
Last updated: NOT ASSESSED
Overall claim: not assessed
Claim scope: {why}

| Concept / performance | Required | Current | Confidence | Strongest evidence | Counterevidence | Next probe | Due |
|---|---:|---:|---:|---|---|---|---|
| TODO | T | U | Low | None | Unassessed | Establish an uncued Audit baseline | Next session |

## Active misconceptions
- None recorded.

## Session queue
1. Establish an uncued baseline for the highest-priority concept.
"""

RESOURCES_TEMPLATE = """# {topic} Resources

## Knowledge
- To research: an authoritative source annotated with what it supports.

## Practice
- To evaluate: a high-signal practice venue, coach, reviewer, or community.

## Gaps
- The mission benchmark has not yet been verified.
"""

NOTES_TEMPLATE = """# Learning Notes

## Preferences
- Language: match the learner.
- Interaction: mouse-first clickable choices.
- Feedback: immediate explanation after commitment.
- Evidence: v3 answers and learning events save automatically after commitment.
- Session time box: To capture
- Accommodations: To capture
"""


def write_new(path: Path, content: str) -> str:
    if path.exists():
        return f"SKIP {path.name}: already exists"
    path.write_text(content, encoding="utf-8")
    return f"CREATE {path.name}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize a Mastery Loop workspace without overwriting state."
    )
    parser.add_argument("--path", required=True, help="Workspace directory")
    parser.add_argument("--topic", required=True, help="Learning topic")
    parser.add_argument("--why", required=True, help="Observable real-world goal")
    parser.add_argument(
        "--mode", choices=("audit", "learn", "review"), default="audit"
    )
    args = parser.parse_args()

    root = Path(args.path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    for dirname in (
        "mastery-sessions",
        "choice-sessions",
        "review-records",
        "assessment-records",
        "learning-records",
        "lessons",
        "reference",
        "assets",
    ):
        (root / dirname).mkdir(exist_ok=True)

    cycle_position = {
        "audit": "Audit",
        "learn": "Learn",
        "review": "Review",
    }[args.mode]
    outputs = [
        write_new(
            root / "MISSION.md",
            MISSION_TEMPLATE.format(topic=args.topic, why=args.why),
        ),
        write_new(
            root / "KNOWLEDGE-MAP.md", KNOWLEDGE_MAP_TEMPLATE.format(topic=args.topic)
        ),
        write_new(
            root / "MASTERY.md",
            MASTERY_TEMPLATE.format(
                topic=args.topic,
                mode=args.mode,
                cycle_position=cycle_position,
                why=args.why,
            ),
        ),
        write_new(root / "RESOURCES.md", RESOURCES_TEMPLATE.format(topic=args.topic)),
        write_new(root / "NOTES.md", NOTES_TEMPLATE),
    ]

    print(f"Workspace: {root}")
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
