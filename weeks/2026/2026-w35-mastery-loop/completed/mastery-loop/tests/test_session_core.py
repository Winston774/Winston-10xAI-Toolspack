from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = load_module("mastery_session_core", ROOT / "scripts" / "session_core.py")


AREAS = ("contracts", "recovery", "evidence")


def cycle_spec() -> dict:
    return {
        "schema_version": 3,
        "cycle_id": "agent-workflow-cycle",
        "mission": {
            "intent_id": "review_teach",
            "ultimate_outcome": "Review and teach an end-to-end Agent Workflow.",
            "audience": "workflow designers",
        },
        "knowledge_scope": {
            "title": "Agent Workflow design",
            "direction": "Contracts, recovery, and final-state evidence.",
            "includes": ["handoffs", "idempotency", "acceptance evidence"],
            "excludes": ["vendor-specific deployment"],
            "benchmark_status": "verified",
            "sources": ["Internal workflow acceptance standard v1"],
        },
        "areas": [
            {
                "area_id": area,
                "title": area.title(),
                "description": f"Knowledge and decisions for {area}.",
                "weight": 1,
                "failure_cost": 2,
                "uncertainty": 2,
            }
            for area in AREAS
        ],
        "artifacts": {
            "assessment_spec": "assessment/spec.json",
            "assessment_report": "assessment/report.json",
            "learning_path": "learning/path.json",
            "learning_report": "learning/report.json",
            "review_spec": "review/spec.json",
            "review_report": "review/report.json",
        },
    }


def options(prefix: str, correct_position: int = 0) -> tuple[list[dict], str]:
    correct_id = f"{prefix}-correct"
    values = [
        {
            "id": correct_id,
            "label": f"{prefix} validate the contract",
            "description": f"Covers the {prefix} evidence gate; downstream acceptance remains separate.",
            "explanation": f"In {prefix}, this preserves the invariant before side effects.",
            "misconception_tag": "",
        },
        {
            "id": f"{prefix}-wrong-a",
            "label": f"{prefix} continue with partial state",
            "description": f"Prioritizes {prefix} delivery speed; artifact completeness remains unresolved.",
            "explanation": f"The partial {prefix} state cannot satisfy the handoff contract.",
            "misconception_tag": "partial-is-complete",
        },
        {
            "id": f"{prefix}-wrong-b",
            "label": f"{prefix} infer the missing evidence",
            "description": f"Fills the {prefix} gap by inference; observable evidence remains unresolved.",
            "explanation": f"The {prefix} inference cannot replace observable evidence.",
            "misconception_tag": "inference-as-evidence",
        },
    ]
    correct = values.pop(0)
    values.insert(correct_position, correct)
    return values, correct_id


def question(index: int, *, area: str | None = None) -> dict:
    area_id = area or AREAS[index % len(AREAS)]
    answer_options, correct = options(f"a{index}")
    return {
        "question_id": f"assessment-q{index:02d}",
        "area_id": area_id,
        "concept_id": f"concept-{index:02d}",
        "knowledge_kernel_id": f"kernel-{index:02d}",
        "core_proposition": f"Core decision proposition {index}.",
        "scenario_id": f"assessment-scenario-{index:02d}",
        "scenario_context": f"Assessment scenario context number {index}.",
        "question_family": "application",
        "title": f"Assessment question {index}",
        "prompt": f"What is the defensible next action in case {index}?",
        "sources": ["Internal workflow acceptance standard v1"],
        "options": answer_options,
        "correct_option_id": correct,
        "importance": 9 if index == 0 else 5,
    }


def assessment_spec(count: int = 12) -> dict:
    return {
        "schema_version": 3,
        "phase": "assessment",
        "cycle_id": "agent-workflow-cycle",
        "title": "Agent Workflow baseline",
        "instructions": "Answer every question before reading the final report.",
        "estimated_minutes": 18,
        "area_ids": list(AREAS),
        "questions": [question(index) for index in range(count)],
    }


def checkpoint(area: str, index: int) -> dict:
    answer_options, correct = options(f"cp-{area}")
    return {
        "question_id": f"checkpoint-{area}",
        "area_id": area,
        "concept_id": f"checkpoint-concept-{area}",
        "knowledge_kernel_id": f"checkpoint-kernel-{area}",
        "core_proposition": f"Integrate the decision rules for {area}.",
        "scenario_id": f"checkpoint-scenario-{area}",
        "scenario_context": f"A formative checkpoint for {area}.",
        "question_family": "sequence",
        "title": f"{area.title()} checkpoint",
        "prompt": f"Which sequence integrates {area} safely?",
        "sources": ["Internal workflow acceptance standard v1"],
        "options": answer_options,
        "correct_option_id": correct,
    }


def learning_fixture(counts: dict[str, int] | None = None):
    counts = counts or {area: 5 for area in AREAS}
    path = {
        "schema_version": 3,
        "phase": "learning",
        "cycle_id": "agent-workflow-cycle",
        "title": "Agent Workflow knowledge map",
        "areas": [],
    }
    slices: dict[str, dict] = {}
    for area_index, area in enumerate(AREAS):
        slice_ids = [f"{area}-slice-{index}" for index in range(1, counts[area] + 1)]
        path["areas"].append(
            {
                "area_id": area,
                "title": area.title(),
                "slice_ids": slice_ids,
                "checkpoint": checkpoint(area, area_index),
            }
        )
        for index, slice_id in enumerate(slice_ids, start=1):
            slices[slice_id] = {
                "schema_version": 3,
                "slice_id": slice_id,
                "area_id": area,
                "title": f"{area.title()} slice {index}",
                "order": index,
                "difficulty": "foundation" if index <= 2 else "core",
                "prerequisites": [slice_ids[index - 2]] if index > 1 else [],
                "learning_objective": f"Apply {area} decision {index}.",
                "assessment_question_ids": [
                    f"assessment-q{area_index + 3 * ((index - 1) % 4):02d}"
                ],
                "addresses_gap_ids": [],
                "core_explanation": f"Core explanation for {area} {index}.",
                "mechanism": f"Mechanism for {area} {index}.",
                "boundaries": ["Stop when required evidence is unavailable."],
                "worked_example": {
                    "scenario_id": f"lesson-{area}-{index}",
                    "scenario_context": f"Worked example for {area} slice {index}.",
                    "walkthrough": "Inspect, decide, validate, and record.",
                },
                "common_mistakes": ["Treating a partial result as complete."],
                "key_takeaways": ["Validate the boundary before continuing."],
                "sources": ["Internal workflow acceptance standard v1"],
            }
    return path, slices


def review_spec(count: int = 8) -> dict:
    questions = []
    for index in range(count):
        source = question(index)
        review_options, correct = options(f"r{index}", correct_position=1)
        questions.append(
            {
                "question_id": f"review-q{index:02d}",
                "area_id": source["area_id"],
                "concept_id": source["concept_id"],
                "primary_kernel_id": source["knowledge_kernel_id"],
                "integrated_kernel_ids": [f"kernel-{(index + 1) % 12:02d}"],
                "core_proposition": source["core_proposition"],
                "source_question_id": source["question_id"],
                "scenario_id": f"review-scenario-{index:02d}",
                "scenario_context": f"Novel review scenario context number {index}.",
                "question_family": "critique",
                "title": f"Review question {index}",
                "prompt": f"Which defect matters most in novel case {index}?",
                "sources": ["Internal workflow acceptance standard v1"],
                "options": review_options,
                "correct_option_id": correct,
                "lineage": {
                    "assessment_question_ids": [
                        source["question_id"],
                        f"assessment-q{(index + 1) % 12:02d}",
                    ],
                    "learning_slice_ids": [],
                    "learning_checkpoint_ids": [],
                },
            }
        )
    return {
        "schema_version": 3,
        "phase": "review",
        "cycle_id": "agent-workflow-cycle",
        "title": "Integrated review",
        "instructions": "Apply the learned kernels in new situations.",
        "questions": questions,
    }


class CycleAndAssessmentValidationTests(unittest.TestCase):
    def test_cycle_rejects_custom_artifact_routing(self):
        value = cycle_spec()
        value["artifacts"]["assessment_report"] = "custom/report.json"
        with self.assertRaises(core.SpecError):
            core.validate_cycle(value)

    def setUp(self):
        self.cycle = core.validate_cycle(cycle_spec())

    def test_load_cycle_returns_directory_and_normalized_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            cycle_dir = workspace / "mastery-sessions" / "agent-workflow-cycle"
            cycle_dir.mkdir(parents=True)
            (cycle_dir / "cycle.json").write_text(
                json.dumps(cycle_spec(), ensure_ascii=False), encoding="utf-8"
            )
            loaded_dir, loaded = core.load_cycle(
                workspace, "mastery-sessions/agent-workflow-cycle"
            )
            self.assertEqual(loaded_dir, cycle_dir.resolve())
            self.assertEqual(loaded["cycle_id"], "agent-workflow-cycle")

    def test_assessment_accepts_12_questions_and_three_areas(self):
        normalized = core.validate_assessment_spec(assessment_spec(), self.cycle)
        self.assertEqual(len(normalized["questions"]), 12)
        self.assertEqual(
            {question["area_id"] for question in normalized["questions"]}, set(AREAS)
        )

    def test_assessment_rejects_question_count_outside_bounds(self):
        with self.assertRaises(core.SpecError):
            core.validate_assessment_spec(assessment_spec(9), self.cycle)
        with self.assertRaises(core.SpecError):
            core.validate_assessment_spec(assessment_spec(21), self.cycle)

    def test_assessment_rejects_area_with_fewer_than_two_questions(self):
        spec = assessment_spec()
        for item in spec["questions"]:
            if item["area_id"] == "evidence":
                item["area_id"] = "contracts"
        with self.assertRaises(core.SpecError):
            core.validate_assessment_spec(spec, self.cycle)

    def test_assessment_rejects_duplicate_kernel_and_missing_explanation(self):
        duplicated = assessment_spec()
        duplicated["questions"][1]["knowledge_kernel_id"] = duplicated["questions"][0][
            "knowledge_kernel_id"
        ]
        with self.assertRaises(core.SpecError):
            core.validate_assessment_spec(duplicated, self.cycle)
        incomplete = assessment_spec()
        del incomplete["questions"][0]["options"][1]["explanation"]
        with self.assertRaises(core.SpecError):
            core.validate_assessment_spec(incomplete, self.cycle)
        missing_tag = assessment_spec()
        missing_tag["questions"][0]["options"][1]["misconception_tag"] = ""
        with self.assertRaises(core.SpecError):
            core.validate_assessment_spec(missing_tag, self.cycle)

    def test_new_batch_rejects_unhelpful_or_leaking_choice_surfaces(self):
        cases = {
            "answer-leak": "符合這一題的遺傳核心命題。",
            "preferred-approach": "This is the preferred approach.",
            "select-this-choice": "This choice should be selected.",
            "chinese-preferred": "這是首選做法。",
            "direct-selection": "請選這個；它就是答案。",
            "answer-location": "答案就在這個選項。",
            "pick-me": "Pick me; all stated prerequisites are satisfied.",
            "select-me": "選我；所有前置條件都已滿足。",
            "status-pass": "Status: PASS; all gates are satisfied.",
            "full-credit": "This response earns full credit.",
            "maximum-score-with-boundary": "This earns the maximum score, but downstream cases remain outside scope.",
            "guaranteed-pass-with-boundary": "This choice is guaranteed to pass, but later checks remain separate.",
            "chinese-guaranteed-pass": "這個選項保證會通過，但後續檢查仍需另行進行。",
            "chinese-perfect-score": "評分：滿分。",
            "all-requirements-met": "Meets every requirement with no unresolved gaps.",
            "all-conditions-met": "所有條件皆已滿足，沒有缺口。",
            "complete-mechanisms": "這個說法已涵蓋題目所需的所有機制。",
            "comprehensive-with-boundary": "已全面涵蓋題目機制；其他延伸細節另行處理。",
            "fully-covers-with-boundary": "Comprehensively covers the requested mechanisms; downstream details remain separate.",
            "criteria-with-boundary": "Satisfies the criteria in the prompt; downstream cases remain separate.",
            "condition-in-prompt": "Meets the condition in the prompt.",
            "standalone-answer": "The answer; downstream cases remain separate.",
            "this-one-is-right": "This one is right; downstream cases remain separate.",
            "correct-one": "Correct one; downstream cases remain separate.",
            "chinese-this-one-is-correct": "這個才正確，但其他條件仍需另行確認。",
            "generic-without-boundary": "Describes a plausible workflow action.",
            "symbol-only": "✅",
            "too-short": "x",
            "future-prompt": "future-prompt",
            "stable-option-id": "stable-option-id",
            "embedded-stable-option-id": "embedded-stable-option-id",
            "plain-stable-option-id": "plain-stable-option-id",
            "short-future-prompt": "short-future-prompt",
            "future-correct-label": "future-correct-label",
            "short-wrong-stable-id-context": "short-wrong-stable-id-context",
            "prompt-hidden-explanation": "prompt-hidden-explanation",
            "prompt-stable-option-id": "prompt-stable-option-id",
            "prompt-correct-position": "prompt-correct-position",
            "prompt-correct-label": "prompt-correct-label",
            "prompt-future-wrong-explanation": "prompt-future-wrong-explanation",
            "prompt-future-wrong-label": "prompt-future-wrong-label",
            "prompt-current-wrong-label": "prompt-current-wrong-label",
            "description-other-option-label": "description-other-option-label",
            "prompt-option-letter": "prompt-option-letter",
            "prompt-option-number": "prompt-option-number",
            "prompt-option-chinese-letter": "prompt-option-chinese-letter",
            "prompt-first-full-credit": "prompt-first-full-credit",
            "prompt-top-answer": "prompt-top-answer",
            "scenario-option-full-credit": "scenario-option-full-credit",
            "intro-future-correct-label": "intro-future-correct-label",
            "intro-stable-option-id": "intro-stable-option-id",
            "short-correct-id-label": "short-correct-id-label",
            "short-wrong-id-label": "short-wrong-id-label",
            "short-stopword-id-suffix-context": "short-stopword-id-suffix-context",
            "prompt-equals-correct-label": "prompt-equals-correct-label",
            "prompt-contains-correct-label": "prompt-contains-correct-label",
            "prompt-short-correct-label": "prompt-short-correct-label",
            "repeated-prompt-correct-label": "repeated-prompt-correct-label",
            "description-own-label-positive": "description-own-label-positive",
            "description-own-label-negative": "description-own-label-negative",
            "description-short-own-label-negative": "description-short-own-label-negative",
            "description-cjk-own-label-negative": "description-cjk-own-label-negative",
            "zero-width-stable-id": "zero-width-stable-id",
            "zero-width-future-correct-label": "zero-width-future-correct-label",
            "empty": "",
            "label-repeat": None,
            "label-repeat-punctuation": "punctuation",
        }
        for case_name, description in cases.items():
            with self.subTest(case=case_name), tempfile.TemporaryDirectory() as directory:
                raw = assessment_spec()
                option = raw["questions"][0]["options"][0]
                if description is None:
                    option["description"] = option["label"]
                elif description == "punctuation":
                    option["description"] = f'{option["label"]}。'
                elif description == "future-prompt":
                    option["description"] = raw["questions"][1]["prompt"]
                elif description == "stable-option-id":
                    option["description"] = (
                        "Internal option key: "
                        f'{raw["questions"][0]["correct_option_id"]}; tracking only.'
                    )
                elif description == "embedded-stable-option-id":
                    option["description"] = (
                        "Internal marker trace-"
                        f'{raw["questions"][0]["correct_option_id"]}-copy only.'
                    )
                elif description == "plain-stable-option-id":
                    option["id"] = "correctanswer"
                    raw["questions"][0]["correct_option_id"] = "correctanswer"
                    option["description"] = (
                        "Internal option key correctanswer for workflow tracking."
                    )
                elif description == "short-future-prompt":
                    raw["questions"][1]["prompt"] = "Pick now?"
                    option["description"] = (
                        "Boundary note: Pick now? Later context remains separate."
                    )
                elif description == "future-correct-label":
                    future = raw["questions"][1]
                    future_correct = next(
                        item
                        for item in future["options"]
                        if item["id"] == future["correct_option_id"]
                    )
                    option["description"] = future_correct["label"]
                elif description == "short-wrong-stable-id-context":
                    question = raw["questions"][0]
                    for item, option_id in zip(
                        question["options"], ("a", "b", "c")
                    ):
                        item["id"] = option_id
                    question["correct_option_id"] = "a"
                    question["options"][1]["description"] = (
                        "Internal option key b for workflow tracking."
                    )
                elif description == "prompt-hidden-explanation":
                    question = raw["questions"][0]
                    correct = next(
                        item
                        for item in question["options"]
                        if item["id"] == question["correct_option_id"]
                    )
                    question["prompt"] = correct["explanation"]
                elif description == "prompt-stable-option-id":
                    question = raw["questions"][0]
                    question["prompt"] = (
                        "Use internal option key "
                        f'{question["correct_option_id"]} before continuing.'
                    )
                elif description == "prompt-correct-position":
                    raw["questions"][0]["prompt"] = (
                        "The first option is the correct answer."
                    )
                elif description == "prompt-correct-label":
                    question = raw["questions"][0]
                    correct = next(
                        item
                        for item in question["options"]
                        if item["id"] == question["correct_option_id"]
                    )
                    question["prompt"] = f'Choose "{correct["label"]}".'
                elif description == "prompt-future-wrong-explanation":
                    future = raw["questions"][1]
                    wrong = next(
                        item
                        for item in future["options"]
                        if item["id"] != future["correct_option_id"]
                    )
                    raw["questions"][0]["prompt"] = wrong["explanation"]
                elif description == "prompt-future-wrong-label":
                    future = raw["questions"][1]
                    wrong = next(
                        item
                        for item in future["options"]
                        if item["id"] != future["correct_option_id"]
                    )
                    raw["questions"][0]["prompt"] = (
                        f'Avoid "{wrong["label"]}"; it fails the contract.'
                    )
                elif description == "prompt-current-wrong-label":
                    question = raw["questions"][0]
                    wrong = next(
                        item
                        for item in question["options"]
                        if item["id"] != question["correct_option_id"]
                    )
                    question["prompt"] = (
                        f'Avoid "{wrong["label"]}"; it fails the contract.'
                    )
                elif description == "description-other-option-label":
                    question = raw["questions"][0]
                    correct = next(
                        item
                        for item in question["options"]
                        if item["id"] == question["correct_option_id"]
                    )
                    question["options"][1]["description"] = (
                        f'Unlike "{correct["label"]}", this leaves evidence unresolved.'
                    )
                elif description == "prompt-option-letter":
                    raw["questions"][0]["prompt"] = "Option A is correct."
                elif description == "prompt-option-number":
                    raw["questions"][0]["prompt"] = (
                        "Option 1 is the correct answer."
                    )
                elif description == "prompt-option-chinese-letter":
                    raw["questions"][0]["prompt"] = "選項 A 是正確答案。"
                elif description == "prompt-first-full-credit":
                    raw["questions"][0]["prompt"] = (
                        "The response shown first earns full credit; explain why."
                    )
                elif description == "prompt-top-answer":
                    raw["questions"][0]["prompt"] = (
                        "The top response is the answer; explain why."
                    )
                elif description == "scenario-option-full-credit":
                    raw["questions"][0]["scenario_context"] = (
                        "The evaluator marks option A as full credit."
                    )
                elif description == "intro-future-correct-label":
                    future = raw["questions"][1]
                    correct = next(
                        item
                        for item in future["options"]
                        if item["id"] == future["correct_option_id"]
                    )
                    raw["instructions"] = (
                        f'Answer key for the next item: {correct["label"]}'
                    )
                elif description == "intro-stable-option-id":
                    raw["instructions"] = (
                        "Internal answer key: "
                        f'{raw["questions"][1]["correct_option_id"]}'
                    )
                elif description == "short-correct-id-label":
                    question = raw["questions"][0]
                    for item, option_id in zip(
                        question["options"], ("win", "lose", "bad")
                    ):
                        item["id"] = option_id
                    question["correct_option_id"] = "win"
                    question["options"][0]["label"] = (
                        "win - validate the contract"
                    )
                elif description == "short-wrong-id-label":
                    question = raw["questions"][0]
                    question["options"][1]["id"] = "bad"
                    question["options"][1]["label"] = (
                        "bad - continue with partial state"
                    )
                elif description == "short-stopword-id-suffix-context":
                    question = raw["questions"][0]
                    for item, option_id in zip(
                        question["options"], ("a", "b", "c")
                    ):
                        item["id"] = option_id
                    question["correct_option_id"] = "a"
                    question["options"][0]["description"] = (
                        "a is the internal option key for workflow tracking."
                    )
                elif description == "prompt-equals-correct-label":
                    question = raw["questions"][0]
                    correct = next(
                        item
                        for item in question["options"]
                        if item["id"] == question["correct_option_id"]
                    )
                    question["prompt"] = correct["label"]
                elif description == "prompt-contains-correct-label":
                    question = raw["questions"][0]
                    correct = next(
                        item
                        for item in question["options"]
                        if item["id"] == question["correct_option_id"]
                    )
                    question["prompt"] = (
                        f'Proceed with "{correct["label"]}" before any side effect.'
                    )
                elif description == "prompt-short-correct-label":
                    question = raw["questions"][0]
                    correct = next(
                        item
                        for item in question["options"]
                        if item["id"] == question["correct_option_id"]
                    )
                    correct["label"] = "Approve"
                    question["prompt"] = "Required next action: Approve."
                elif description == "repeated-prompt-correct-label":
                    future = raw["questions"][3]
                    correct = next(
                        item
                        for item in future["options"]
                        if item["id"] == future["correct_option_id"]
                    )
                    for question in raw["questions"][:4]:
                        question["prompt"] = correct["label"]
                elif description == "description-own-label-positive":
                    option["description"] = (
                        f'Required next action: {option["label"]}; '
                        "downstream reporting remains separate."
                    )
                elif description == "description-own-label-negative":
                    option["description"] = (
                        f'Avoid {option["label"]}; '
                        "the contract boundary remains unresolved."
                    )
                elif description == "description-short-own-label-negative":
                    option["label"] = "Run"
                    option["description"] = (
                        "Avoid Run; the contract boundary remains unresolved."
                    )
                elif description == "description-cjk-own-label-negative":
                    option["label"] = "停"
                    option["description"] = "不要選停；仍缺少必要條件。"
                elif description == "zero-width-stable-id":
                    option["description"] = (
                        "Internal key a0-\u200bcorrect remains outside the learner surface."
                    )
                elif description == "zero-width-future-correct-label":
                    future = raw["questions"][1]
                    correct = next(
                        item
                        for item in future["options"]
                        if item["id"] == future["correct_option_id"]
                    )
                    disguised = correct["label"][:3] + "\u200b" + correct["label"][3:]
                    option["description"] = (
                        f'Avoid {disguised} before approval; the boundary remains open.'
                    )
                else:
                    option["description"] = description
                normalized = core.validate_assessment_spec(raw, self.cycle)
                phase_dir = Path(directory) / "assessment"
                phase_dir.mkdir()
                with self.assertRaises(core.SpecError):
                    core.ensure_batch_manifest(phase_dir, normalized)
                self.assertFalse((phase_dir / "batch-manifest.json").exists())

    def test_short_correct_option_id_does_not_confuse_an_english_article(self):
        raw = assessment_spec()
        first = raw["questions"][0]
        for option, option_id in zip(first["options"], ("a", "b", "c")):
            option["id"] = option_id
        first["correct_option_id"] = "a"
        first["options"][0]["description"] = (
            "Use a question boundary before execution."
        )
        normalized = core.validate_assessment_spec(raw, self.cycle)
        with tempfile.TemporaryDirectory() as directory:
            manifest, created = core.ensure_batch_manifest(
                Path(directory), normalized
            )
            self.assertTrue(created)
            self.assertEqual(manifest["phase"], "assessment")

    def test_stable_id_requires_an_identifier_boundary(self):
        raw = assessment_spec()
        first = raw["questions"][0]
        first["options"][0]["id"] = "safe"
        first["correct_option_id"] = "safe"
        first["options"][0]["label"] = "Safety boundary before execution"
        first["options"][0]["description"] = (
            "Applies only before execution; downstream acceptance remains separate."
        )
        normalized = core.validate_assessment_spec(raw, self.cycle)
        with tempfile.TemporaryDirectory() as directory:
            manifest, created = core.ensure_batch_manifest(
                Path(directory), normalized
            )
            self.assertTrue(created)
            self.assertEqual(manifest["phase"], "assessment")

    def test_new_batch_rejects_answer_revealing_option_label(self):
        for label in ("這就是正確答案", "The answer", "答案"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                raw = assessment_spec()
                raw["questions"][0]["options"][0]["label"] = label
                normalized = core.validate_assessment_spec(raw, self.cycle)
                with self.assertRaises(core.SpecError):
                    core.ensure_batch_manifest(Path(directory), normalized)

    def test_question_rejects_conflicting_or_multiple_correct_answers(self):
        conflicting = assessment_spec()
        conflicting["questions"][0]["correct_option_ids"] = [
            conflicting["questions"][0]["options"][1]["id"]
        ]
        with self.assertRaises(core.SpecError):
            core.validate_assessment_spec(conflicting, self.cycle)
        multiple = assessment_spec()
        multiple["questions"][0]["correct_option_ids"] = [
            multiple["questions"][0]["options"][0]["id"],
            multiple["questions"][0]["options"][1]["id"],
        ]
        with self.assertRaises(core.SpecError):
            core.validate_assessment_spec(multiple, self.cycle)

        duplicate_surface = assessment_spec()
        duplicate_surface["questions"][0]["options"][1]["label"] = (
            duplicate_surface["questions"][0]["options"][0]["label"]
        )
        duplicate_surface["questions"][0]["options"][1]["description"] = (
            duplicate_surface["questions"][0]["options"][0]["description"]
        )
        with self.assertRaises(core.SpecError):
            core.validate_assessment_spec(duplicate_surface, self.cycle)


class ResponseAndAssessmentReportTests(unittest.TestCase):
    def setUp(self):
        self.cycle = core.validate_cycle(cycle_spec())
        self.spec = core.validate_assessment_spec(assessment_spec(), self.cycle)

    def answer(self, phase_dir: Path, question: dict, correct: bool, request_id: str):
        selected = (
            question["correct_option_id"]
            if correct
            else next(
                option["id"]
                for option in question["options"]
                if option["id"] != question["correct_option_id"]
            )
        )
        return core.record_response(
            phase_dir,
            self.spec,
            question["question_id"],
            selected,
            [option["id"] for option in question["options"]],
            request_id,
        )

    def test_response_is_write_once_and_request_id_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            phase_dir = Path(directory)
            question_item = self.spec["questions"][0]
            first, created = self.answer(phase_dir, question_item, True, "request-one")
            second, created_again = self.answer(
                phase_dir, question_item, True, "request-one"
            )
            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(first, second)
            self.assertEqual(first["correct_option_id"], question_item["correct_option_id"])
            self.assertFalse(first["feedback_exposed"])
            with self.assertRaises(core.ConflictError):
                self.answer(phase_dir, question_item, False, "request-one")
            timeout_retry, retry_created = self.answer(
                phase_dir, question_item, True, "request-two"
            )
            self.assertFalse(retry_created)
            self.assertEqual(timeout_retry, first)

    def test_report_rejects_response_after_server_spec_is_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            phase_dir = Path(directory)
            question_item = self.spec["questions"][0]
            self.answer(phase_dir, question_item, True, "request-one")
            changed = json.loads(json.dumps(self.spec))
            changed["questions"][0]["options"].reverse()
            with self.assertRaises(core.SpecError):
                core.build_assessment_report(
                    phase_dir, changed, require_complete=False
                )

    def test_response_rejects_invalid_evidence_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            phase_dir = Path(directory)
            question_item = self.spec["questions"][0]
            self.answer(phase_dir, question_item, True, "timestamp-fixture")
            path = (
                phase_dir
                / "responses"
                / f"{question_item['question_id']}.json"
            )
            record = core.read_json_object(path)
            record["answered_at"] = "garbage"
            path.write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaises(core.SpecError):
                core.build_assessment_report(
                    phase_dir, self.spec, require_complete=False
                )

    def test_report_recomputes_threshold_signals_and_critical_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            phase_dir = Path(directory)
            results = {
                "contracts": [True, True, True, True],
                "recovery": [True, True, True, False],
                "evidence": [True, False, False, False],
            }
            seen = {area: 0 for area in AREAS}
            for index, item in enumerate(self.spec["questions"]):
                offset = seen[item["area_id"]]
                seen[item["area_id"]] += 1
                self.answer(
                    phase_dir,
                    item,
                    results[item["area_id"]][offset],
                    f"request-{index}",
                )
            report = core.build_assessment_report(phase_dir, self.spec, persist=True)
            signals = {item["area_id"]: item["signal"] for item in report["area_results"]}
            self.assertEqual(signals["contracts"], "stable_signal")
            self.assertEqual(signals["recovery"], "mixed_signal")
            self.assertEqual(signals["evidence"], "needs_support")
            self.assertEqual(len(report["gaps"]), 4)
            self.assertEqual(len(report["strengths"]), 8)
            self.assertEqual(
                len(next(item for item in report["area_results"] if item["area_id"] == "contracts")["strength_question_ids"]),
                4,
            )
            self.assertTrue((phase_dir / "report.json").is_file())

    def test_incomplete_assessment_cannot_emit_final_report(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(core.IncompletePhaseError):
                core.build_assessment_report(Path(directory), self.spec)


class LearningValidationAndGateTests(unittest.TestCase):
    def setUp(self):
        self.cycle = core.validate_cycle(cycle_spec())
        raw_path, raw_slices = learning_fixture()
        self.raw_slices = raw_slices
        self.path = core.validate_learning_path(
            raw_path, self.cycle, slices=raw_slices
        )

    def test_three_areas_five_slices_and_checkpoint_are_valid(self):
        self.assertEqual(len(self.path["areas"]), 3)
        self.assertTrue(all(len(area["slice_ids"]) == 5 for area in self.path["areas"]))
        self.assertTrue(all(area["checkpoint"] for area in self.path["areas"]))

    def test_every_slice_requires_assessment_evidence_link(self):
        raw_path, raw_slices = learning_fixture()
        raw_slices["contracts-slice-1"]["assessment_question_ids"] = []
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(
                raw_path,
                self.cycle,
                slices=raw_slices,
                assessment_spec=assessment_spec(),
            )

    def test_learning_rejects_forward_prerequisite(self):
        raw_path, raw_slices = learning_fixture()
        raw_slices["contracts-slice-1"]["prerequisites"] = ["contracts-slice-2"]
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(raw_path, self.cycle, slices=raw_slices)

        difficulty_path, difficulty_slices = learning_fixture()
        difficulty_slices["contracts-slice-1"]["difficulty"] = "advanced"
        difficulty_slices["contracts-slice-2"]["difficulty"] = "foundation"
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(
                difficulty_path, self.cycle, slices=difficulty_slices
            )

    def test_learning_rejects_checkpoint_and_assessment_id_collisions(self):
        duplicated_path, duplicated_slices = learning_fixture()
        duplicated_path["areas"][1]["checkpoint"]["question_id"] = duplicated_path[
            "areas"
        ][0]["checkpoint"]["question_id"]
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(
                duplicated_path, self.cycle, slices=duplicated_slices
            )

        colliding_path, colliding_slices = learning_fixture()
        colliding_path["areas"][0]["checkpoint"]["question_id"] = "assessment-q00"
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(
                colliding_path,
                self.cycle,
                slices=colliding_slices,
                assessment_spec=assessment_spec(),
            )

        kernel_path, kernel_slices = learning_fixture()
        kernel_path["areas"][0]["checkpoint"]["knowledge_kernel_id"] = "kernel-00"
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(
                kernel_path,
                self.cycle,
                slices=kernel_slices,
                assessment_spec=assessment_spec(),
            )

        linked_path, linked_slices = learning_fixture()
        linked_slices["contracts-slice-1"]["assessment_question_ids"] = [
            "missing-question"
        ]
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(
                linked_path,
                self.cycle,
                slices=linked_slices,
                assessment_spec=assessment_spec(),
            )

    def test_learning_completion_rejects_tampered_event_content(self):
        with tempfile.TemporaryDirectory() as directory:
            learning_dir = Path(directory)
            first = self.path["areas"][0]["slice_ids"][0]
            core.record_slice_completion(
                learning_dir,
                self.path,
                self.raw_slices,
                first,
                "tamper-fixture",
            )
            event = learning_dir / "events" / f"slice_completed.{first}.json"
            event.write_text("{}", encoding="utf-8")
            with self.assertRaises(core.SpecError):
                core.learning_completion_state(
                    learning_dir, self.path, slices=self.raw_slices
                )

    def test_first_event_seals_future_learning_content(self):
        with tempfile.TemporaryDirectory() as directory:
            learning_dir = Path(directory)
            first = self.path["areas"][0]["slice_ids"][0]
            core.record_slice_completion(
                learning_dir,
                self.path,
                self.raw_slices,
                first,
                "seal-learning-contract",
            )
            changed_slices = json.loads(json.dumps(self.raw_slices))
            changed_slices["contracts-slice-2"]["core_explanation"] = (
                "Mutated future learning content."
            )
            with self.assertRaises(core.SpecError):
                core.learning_completion_state(
                    learning_dir, self.path, slices=changed_slices
                )

    def test_first_learning_event_rejects_answer_revealing_checkpoint_copy(self):
        raw_path, raw_slices = learning_fixture()
        raw_path["areas"][0]["checkpoint"]["options"][0]["description"] = (
            "這個選項就是正確答案。"
        )
        path = core.validate_learning_path(
            raw_path, self.cycle, slices=raw_slices
        )
        with tempfile.TemporaryDirectory() as directory:
            learning_dir = Path(directory)
            first = path["areas"][0]["slice_ids"][0]
            with self.assertRaises(core.SpecError):
                core.record_slice_completion(
                    learning_dir,
                    path,
                    raw_slices,
                    first,
                    "unsafe-learning-copy",
                )
            self.assertFalse((learning_dir / "events").exists())

    def test_gap_formula_and_mapping_are_enforced(self):
        raw_path, raw_slices = learning_fixture(
            {"contracts": 6, "recovery": 5, "evidence": 5}
        )
        gap = {
            "gap_id": "assessment.assessment-q00",
            "area_id": "contracts",
            "knowledge_kernel_id": "kernel-00",
            "source_question_id": "assessment-q00",
        }
        report = {"gaps": [gap]}
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(
                raw_path,
                self.cycle,
                slices=raw_slices,
                assessment_report=report,
            )
        raw_slices["contracts-slice-1"]["addresses_gap_ids"] = [gap["gap_id"]]
        normalized = core.validate_learning_path(
            raw_path,
            self.cycle,
            slices=raw_slices,
            assessment_report=report,
        )
        self.assertEqual(len(normalized["areas"][0]["slice_ids"]), 6)
        unlinked_path, unlinked_slices = learning_fixture(
            {"contracts": 6, "recovery": 5, "evidence": 5}
        )
        unlinked_slices["contracts-slice-1"]["addresses_gap_ids"] = [
            gap["gap_id"]
        ]
        unlinked_slices["contracts-slice-1"]["assessment_question_ids"] = [
            "assessment-q03"
        ]
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(
                unlinked_path,
                self.cycle,
                slices=unlinked_slices,
                assessment_report=report,
            )
        wrong_area_path, wrong_area_slices = learning_fixture(
            {"contracts": 6, "recovery": 5, "evidence": 5}
        )
        wrong_area_slices["recovery-slice-1"]["addresses_gap_ids"] = [gap["gap_id"]]
        with self.assertRaises(core.SpecError):
            core.validate_learning_path(
                wrong_area_path,
                self.cycle,
                slices=wrong_area_slices,
                assessment_report=report,
            )

    def test_review_gate_requires_every_slice_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            learning_dir = Path(directory)
            with self.assertRaises(core.IncompleteLearningError):
                core.ensure_review_ready(
                    learning_dir, self.path, slices=self.raw_slices
                )
            for area in self.path["areas"]:
                for slice_id in area["slice_ids"]:
                    core.record_slice_completion(
                        learning_dir,
                        self.path,
                        self.raw_slices,
                        slice_id,
                        f"complete-{slice_id}",
                    )
                checkpoint_item = area["checkpoint"]
                core.record_checkpoint_response(
                    learning_dir,
                    self.path,
                    area["area_id"],
                    checkpoint_item["correct_option_id"],
                    [option["id"] for option in checkpoint_item["options"]],
                    f"checkpoint-{area['area_id']}",
                    slices=self.raw_slices,
                )
            state = core.ensure_review_ready(
                learning_dir, self.path, slices=self.raw_slices
            )
            self.assertTrue(state["complete"])
            report = core.build_learning_report(
                learning_dir, self.path, slices=self.raw_slices
            )
            self.assertEqual(report["mastery_effect"], "learning_progress_only")
            self.assertTrue(report["review_ready"])
            self.assertEqual(report["gaps"], [])

    def test_checkpoint_wrong_is_saved_without_blocking_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            learning_dir = Path(directory)
            for area in self.path["areas"]:
                for slice_id in area["slice_ids"]:
                    core.record_slice_completion(
                        learning_dir,
                        self.path,
                        self.raw_slices,
                        slice_id,
                        f"complete-{slice_id}",
                    )
                checkpoint_item = area["checkpoint"]
                wrong = next(
                    option["id"]
                    for option in checkpoint_item["options"]
                    if option["id"] != checkpoint_item["correct_option_id"]
                )
                selected = wrong if area["area_id"] == "contracts" else checkpoint_item["correct_option_id"]
                core.record_checkpoint_response(
                    learning_dir,
                    self.path,
                    area["area_id"],
                    selected,
                    [option["id"] for option in checkpoint_item["options"]],
                    f"checkpoint-{area['area_id']}",
                    slices=self.raw_slices,
                )
            report = core.build_learning_report(
                learning_dir, self.path, slices=self.raw_slices
            )
            self.assertTrue(report["complete"])
            self.assertEqual(len(report["gaps"]), 1)
            self.assertEqual(report["gaps"][0]["area_id"], "contracts")


class ReviewValidationAndReportTests(unittest.TestCase):
    def setUp(self):
        self.cycle = core.validate_cycle(cycle_spec())
        self.assessment = core.validate_assessment_spec(assessment_spec(), self.cycle)
        raw_path, raw_slices = learning_fixture()
        self.slices = raw_slices
        self.learning = core.validate_learning_path(raw_path, self.cycle, slices=raw_slices)

    def validate(self, value: dict):
        return core.validate_review_spec(
            value,
            self.cycle,
            assessment_spec=self.assessment,
            learning_path=self.learning,
            learning_slices=self.slices,
        )

    def test_review_accepts_eight_new_scenarios_with_lineage(self):
        normalized = self.validate(review_spec())
        self.assertEqual(len(normalized["questions"]), 8)
        self.assertTrue(
            all(question["source_question_id"] for question in normalized["questions"])
        )

    def test_new_review_batch_rejects_answer_revealing_description(self):
        raw = review_spec()
        raw["questions"][0]["options"][0]["description"] = (
            "This is the best answer."
        )
        normalized = self.validate(raw)
        with tempfile.TemporaryDirectory() as directory:
            phase_dir = Path(directory)
            with self.assertRaises(core.SpecError):
                core.ensure_batch_manifest(phase_dir, normalized)
            self.assertFalse((phase_dir / "batch-manifest.json").exists())

    def test_review_rejects_reused_scenario_family_options_and_position(self):
        cases = []
        reused_scenario = review_spec()
        reused_scenario["questions"][0]["scenario_context"] = self.assessment["questions"][0][
            "scenario_context"
        ]
        cases.append(reused_scenario)
        trivial_rewrite = review_spec()
        trivial_rewrite["questions"][0]["scenario_context"] = (
            self.assessment["questions"][0]["scenario_context"] + " Paraphrased."
        )
        cases.append(trivial_rewrite)
        reused_scenario_id = review_spec()
        reused_scenario_id["questions"][0]["scenario_id"] = self.assessment["questions"][1][
            "scenario_id"
        ]
        cases.append(reused_scenario_id)
        reused_family = review_spec()
        reused_family["questions"][0]["question_family"] = "application"
        cases.append(reused_family)
        reused_option = review_spec()
        reused_option["questions"][0]["options"][0]["id"] = self.assessment["questions"][0][
            "options"
        ][0]["id"]
        cases.append(reused_option)
        reused_description = review_spec()
        reused_description["questions"][0]["options"][0]["description"] = (
            self.assessment["questions"][0]["options"][0]["description"]
        )
        cases.append(reused_description)
        reused_explanation = review_spec()
        reused_explanation["questions"][0]["options"][0]["explanation"] = (
            self.assessment["questions"][0]["options"][0]["explanation"]
        )
        cases.append(reused_explanation)
        reused_position = review_spec()
        first = reused_position["questions"][0]["options"]
        correct_index = next(
            index
            for index, option in enumerate(first)
            if option["id"] == reused_position["questions"][0]["correct_option_id"]
        )
        first[0], first[correct_index] = first[correct_index], first[0]
        cases.append(reused_position)
        reused_checkpoint = review_spec()
        checkpoint_source = self.learning["areas"][0]["checkpoint"]
        checkpoint_item = reused_checkpoint["questions"][0]
        checkpoint_item["area_id"] = checkpoint_source["area_id"]
        checkpoint_item["concept_id"] = checkpoint_source["concept_id"]
        checkpoint_item["primary_kernel_id"] = checkpoint_source[
            "knowledge_kernel_id"
        ]
        checkpoint_item["core_proposition"] = checkpoint_source[
            "core_proposition"
        ]
        checkpoint_item["source_question_id"] = checkpoint_source["question_id"]
        checkpoint_item["scenario_id"] = checkpoint_source["scenario_id"]
        checkpoint_item["scenario_context"] = checkpoint_source[
            "scenario_context"
        ]
        checkpoint_item["lineage"]["assessment_question_ids"] = [
            "assessment-q01"
        ]
        checkpoint_item["lineage"]["learning_checkpoint_ids"] = [
            checkpoint_source["question_id"]
        ]
        cases.append(reused_checkpoint)
        for value in cases:
            with self.subTest(value=value["questions"][0]):
                with self.assertRaises(core.SpecError):
                    self.validate(value)

    def test_review_rejects_duplicate_scenario_unknown_lineage_and_no_integration(self):
        duplicate_scenario = review_spec()
        duplicate_scenario["questions"][1]["scenario_id"] = duplicate_scenario[
            "questions"
        ][0]["scenario_id"]
        with self.assertRaises(core.SpecError):
            self.validate(duplicate_scenario)

        unknown_lineage = review_spec()
        unknown_lineage["questions"][0]["lineage"]["assessment_question_ids"].append(
            "unknown-assessment"
        )
        with self.assertRaises(core.SpecError):
            self.validate(unknown_lineage)

        no_integration = review_spec()
        for item in no_integration["questions"]:
            item["integrated_kernel_ids"] = []
            item["lineage"]["assessment_question_ids"] = [item["source_question_id"]]
        with self.assertRaises(core.SpecError):
            self.validate(no_integration)

    def test_review_requires_mission_critical_correct_kernel(self):
        value = review_spec()
        replacement = self.assessment["questions"][8]
        first = value["questions"][0]
        first["area_id"] = replacement["area_id"]
        first["concept_id"] = replacement["concept_id"]
        first["primary_kernel_id"] = replacement["knowledge_kernel_id"]
        first["core_proposition"] = replacement["core_proposition"]
        first["source_question_id"] = replacement["question_id"]
        first["lineage"]["assessment_question_ids"] = [
            replacement["question_id"],
            "assessment-q01",
        ]
        with self.assertRaises(core.SpecError):
            core.validate_review_spec(
                value,
                self.cycle,
                assessment_spec=self.assessment,
                learning_path=self.learning,
                learning_slices=self.slices,
                assessment_report={
                    "gaps": [],
                    "question_results": [
                        {"question_id": "assessment-q00", "is_correct": True}
                    ],
                },
            )

    def test_review_report_compares_prior_gaps_and_schedules_three_days(self):
        normalized = self.validate(review_spec())
        assessment_report = {
            "gaps": [
                {
                    "gap_id": "assessment.assessment-q00",
                    "area_id": "contracts",
                    "knowledge_kernel_id": "kernel-00",
                    "source_question_id": "assessment-q00",
                },
                {
                    "gap_id": "assessment.assessment-q01",
                    "area_id": "recovery",
                    "knowledge_kernel_id": "kernel-01",
                    "source_question_id": "assessment-q01",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            review_dir = Path(directory)
            for index, item in enumerate(normalized["questions"]):
                correct = index != 1
                selected = item["correct_option_id"] if correct else next(
                    option["id"]
                    for option in item["options"]
                    if option["id"] != item["correct_option_id"]
                )
                core.record_response(
                    review_dir,
                    normalized,
                    item["question_id"],
                    selected,
                    [option["id"] for option in item["options"]],
                    f"review-request-{index}",
                )
            last_response_path = (
                review_dir
                / "responses"
                / f"{normalized['questions'][-1]['question_id']}.json"
            )
            last_response = core.read_json_object(last_response_path)
            last_response["answered_at"] = "2026-08-27T12:00:00+00:00"
            last_response_path.write_text(
                json.dumps(last_response, ensure_ascii=False), encoding="utf-8"
            )
            report = core.build_review_report(
                review_dir,
                normalized,
                assessment_report,
                now=dt.datetime(2026, 9, 12, tzinfo=dt.timezone.utc),
            )
            self.assertIn("assessment.assessment-q00", report["corrected_gap_ids"])
            self.assertIn("assessment.assessment-q01", report["remaining_gap_ids"])
            self.assertNotIn("assessment.assessment-q01", report["corrected_gap_ids"])
            first_result = next(
                item
                for item in report["question_results"]
                if item["question_id"] == "review-q00"
            )
            self.assertIn(
                "assessment.assessment-q01", first_result["integrated_gap_ids"]
            )
            self.assertTrue(
                all(item["due_date"] == "2026-08-30" for item in report["delayed_review"])
            )
            reopened = core.build_review_report(
                review_dir,
                normalized,
                assessment_report,
                now=dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc),
            )
            self.assertEqual(
                report["delayed_review"], reopened["delayed_review"]
            )
            self.assertEqual(
                report["completion_anchor"], reopened["completion_anchor"]
            )
            self.assertEqual(len(report["integration_results"]), 8)

    def test_review_question_count_follows_gap_plus_area_formula(self):
        gaps = [
            {
                "gap_id": f"assessment.assessment-q{index:02d}",
                "area_id": AREAS[index % len(AREAS)],
                "knowledge_kernel_id": f"kernel-{index:02d}",
                "source_question_id": f"assessment-q{index:02d}",
            }
            for index in range(6)
        ]
        counts = {
            area: 5 + sum(gap["area_id"] == area for gap in gaps)
            for area in AREAS
        }
        raw_learning, slices = learning_fixture(counts)
        for area in AREAS:
            area_gaps = [gap for gap in gaps if gap["area_id"] == area]
            area_slice_ids = next(
                item["slice_ids"]
                for item in raw_learning["areas"]
                if item["area_id"] == area
            )
            for index, gap in enumerate(area_gaps):
                slices[area_slice_ids[index]]["addresses_gap_ids"].append(
                    gap["gap_id"]
                )
                source_id = gap["source_question_id"]
                links = slices[area_slice_ids[index]]["assessment_question_ids"]
                if source_id not in links:
                    links.append(source_id)
        assessment_report = {"gaps": gaps}
        learning = core.validate_learning_path(
            raw_learning,
            self.cycle,
            slices=slices,
            assessment_report=assessment_report,
            assessment_spec=self.assessment,
        )
        with self.assertRaises(core.SpecError):
            core.validate_review_spec(
                review_spec(8),
                self.cycle,
                assessment_spec=self.assessment,
                learning_path=learning,
                learning_slices=slices,
                assessment_report=assessment_report,
            )
        normalized = core.validate_review_spec(
            review_spec(9),
            self.cycle,
            assessment_spec=self.assessment,
            learning_path=learning,
            learning_slices=slices,
            assessment_report=assessment_report,
        )
        self.assertEqual(len(normalized["questions"]), 9)

    def test_review_caps_primary_gaps_and_integrates_overflow(self):
        expanded_assessment = core.validate_assessment_spec(
            assessment_spec(20), self.cycle
        )
        gaps = [
            {
                "gap_id": f"assessment.assessment-q{index:02d}",
                "source": "assessment",
                "area_id": AREAS[index % len(AREAS)],
                "knowledge_kernel_id": f"kernel-{index:02d}",
                "source_question_id": f"assessment-q{index:02d}",
                "core_proposition": f"Core decision proposition {index}.",
                "critical": index in {0, 18},
            }
            for index in range(20)
        ]
        assessment_report = {
            "gaps": gaps,
            "question_results": [
                {"question_id": f"assessment-q{index:02d}", "is_correct": False}
                for index in range(20)
            ],
        }
        counts = {area: 10 for area in AREAS}
        raw_learning, slices = learning_fixture(counts)
        for area in AREAS:
            area_gaps = [gap for gap in gaps if gap["area_id"] == area]
            area_slice_ids = next(
                item["slice_ids"]
                for item in raw_learning["areas"]
                if item["area_id"] == area
            )
            for index, gap in enumerate(area_gaps):
                slices[area_slice_ids[index]]["addresses_gap_ids"].append(
                    gap["gap_id"]
                )
                links = slices[area_slice_ids[index]]["assessment_question_ids"]
                if gap["source_question_id"] not in links:
                    links.append(gap["source_question_id"])
        learning = core.validate_learning_path(
            raw_learning,
            self.cycle,
            slices=slices,
            assessment_report=assessment_report,
            assessment_spec=expanded_assessment,
        )

        value = review_spec(15)
        critical_source = question(18)
        critical_item = value["questions"][14]
        critical_item["area_id"] = critical_source["area_id"]
        critical_item["concept_id"] = critical_source["concept_id"]
        critical_item["primary_kernel_id"] = critical_source["knowledge_kernel_id"]
        critical_item["core_proposition"] = critical_source["core_proposition"]
        critical_item["source_question_id"] = critical_source["question_id"]
        critical_item["lineage"]["assessment_question_ids"][0] = critical_source[
            "question_id"
        ]
        for overflow_index, gap_index in enumerate((14, 15, 16, 17, 19)):
            item = value["questions"][overflow_index]
            item["integrated_kernel_ids"].append(f"kernel-{gap_index:02d}")
            item["lineage"]["assessment_question_ids"].append(
                f"assessment-q{gap_index:02d}"
            )
        normalized = core.validate_review_spec(
            value,
            self.cycle,
            assessment_spec=expanded_assessment,
            learning_path=learning,
            learning_slices=slices,
            assessment_report=assessment_report,
        )
        self.assertEqual(len(normalized["questions"]), 15)

        with tempfile.TemporaryDirectory() as directory:
            review_dir = Path(directory)
            for index, item in enumerate(normalized["questions"]):
                core.record_response(
                    review_dir,
                    normalized,
                    item["question_id"],
                    item["correct_option_id"],
                    [option["id"] for option in item["options"]],
                    f"overflow-review-{index}",
                )
            report = core.build_review_report(
                review_dir, normalized, assessment_report
            )
            self.assertEqual(len(report["directly_reviewed_gap_ids"]), 15)
            self.assertEqual(len(report["not_directly_reviewed_gap_ids"]), 5)
            self.assertEqual(len(report["corrected_gap_ids"]), 15)
            self.assertEqual(len(report["remaining_gap_ids"]), 5)
            self.assertTrue(
                set(report["not_directly_reviewed_gap_ids"])
                <= {item["gap_id"] for item in report["delayed_review"]}
            )


class PersistenceTests(unittest.TestCase):
    def test_atomic_write_replaces_and_write_once_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atomic_path = root / "report.json"
            core.atomic_write_json(atomic_path, {"value": 1})
            core.atomic_write_json(atomic_path, {"value": 2})
            self.assertEqual(core.read_json_object(atomic_path)["value"], 2)
            once_path = root / "answer.json"
            core.write_json_once(once_path, {"value": 1})
            with self.assertRaises(FileExistsError):
                core.write_json_once(once_path, {"value": 2})
            self.assertEqual(core.read_json_object(once_path)["value"], 1)

    def test_phase_lock_is_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir = Path(directory)
            with core.PhaseLock(cycle_dir, "assessment"):
                with self.assertRaises(core.ConflictError):
                    with core.PhaseLock(cycle_dir, "learning"):
                        pass
            state = core.read_json_object(cycle_dir / ".cycle.lock")
            self.assertFalse(state["active"])

    def test_phase_lock_recovers_after_owner_process_crashes(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir = Path(directory)
            script = """
import importlib.util
import os
import sys
spec = importlib.util.spec_from_file_location('crash_core', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
lock = module.PhaseLock(sys.argv[2], 'assessment')
lock.__enter__()
os._exit(0)
"""
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    script,
                    str(ROOT / "scripts" / "session_core.py"),
                    str(cycle_dir),
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with core.PhaseLock(cycle_dir, "review"):
                self.assertTrue((cycle_dir / ".cycle.lock").is_file())
            self.assertFalse(
                core.read_json_object(cycle_dir / ".cycle.lock")["active"]
            )


if __name__ == "__main__":
    unittest.main()
