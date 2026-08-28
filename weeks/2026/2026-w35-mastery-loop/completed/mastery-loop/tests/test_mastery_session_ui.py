from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from test_session_core import assessment_spec, cycle_spec, learning_fixture, review_spec


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ui = load_module("mastery_session_ui_v3", ROOT / "scripts" / "mastery_session_ui.py")


def write_assessment_workspace(root: Path) -> tuple[Path, ui.SessionBundle]:
    cycle_dir = root / "mastery-sessions" / "agent-workflow-cycle"
    (cycle_dir / "assessment" / "responses").mkdir(parents=True)
    (cycle_dir / "cycle.json").write_text(
        json.dumps(cycle_spec(), ensure_ascii=False), encoding="utf-8"
    )
    (cycle_dir / "assessment" / "spec.json").write_text(
        json.dumps(assessment_spec(), ensure_ascii=False), encoding="utf-8"
    )
    bundle = ui.load_phase_bundle(
        root, "mastery-sessions/agent-workflow-cycle", "assessment"
    )
    return cycle_dir, bundle


def apply_unsafe_choice_case(raw: dict, case: str) -> str:
    question = raw["questions"][0]
    option = question["options"][0]
    if case == "future-prompt":
        description = raw["questions"][1]["prompt"]
    elif case == "short-future-prompt":
        raw["questions"][1]["prompt"] = "Pick now?"
        description = "Boundary note: Pick now? Later context remains separate."
    elif case == "future-correct-label":
        future = raw["questions"][1]
        description = next(
            item["label"]
            for item in future["options"]
            if item["id"] == future["correct_option_id"]
        )
    elif case == "stable-option-id":
        description = (
            f'Internal option key: {question["correct_option_id"]}; tracking only.'
        )
    elif case == "embedded-stable-option-id":
        description = (
            f'Internal marker trace-{question["correct_option_id"]}-copy only.'
        )
    elif case == "plain-stable-option-id":
        option["id"] = "correctanswer"
        question["correct_option_id"] = "correctanswer"
        description = "Internal option key correctanswer for workflow tracking."
    elif case == "prompt-hidden-explanation":
        correct = next(
            item
            for item in question["options"]
            if item["id"] == question["correct_option_id"]
        )
        question["prompt"] = correct["explanation"]
        description = option["description"]
    elif case == "prompt-stable-option-id":
        question["prompt"] = (
            f'Use internal option key {question["correct_option_id"]} before continuing.'
        )
        description = option["description"]
    elif case == "prompt-correct-position":
        question["prompt"] = "The first option is the correct answer."
        description = option["description"]
    elif case == "prompt-correct-label":
        correct = next(
            item
            for item in question["options"]
            if item["id"] == question["correct_option_id"]
        )
        question["prompt"] = f'Choose "{correct["label"]}".'
        description = option["description"]
    elif case == "prompt-future-wrong-explanation":
        future = raw["questions"][1]
        wrong = next(
            item
            for item in future["options"]
            if item["id"] != future["correct_option_id"]
        )
        question["prompt"] = wrong["explanation"]
        description = option["description"]
    elif case == "prompt-future-wrong-label":
        future = raw["questions"][1]
        wrong = next(
            item
            for item in future["options"]
            if item["id"] != future["correct_option_id"]
        )
        question["prompt"] = f'Avoid "{wrong["label"]}"; it fails the contract.'
        description = option["description"]
    elif case == "prompt-current-wrong-label":
        wrong = next(
            item
            for item in question["options"]
            if item["id"] != question["correct_option_id"]
        )
        question["prompt"] = f'Avoid "{wrong["label"]}"; it fails the contract.'
        description = option["description"]
    elif case == "description-other-option-label":
        correct = next(
            item
            for item in question["options"]
            if item["id"] == question["correct_option_id"]
        )
        question["options"][1]["description"] = (
            f'Unlike "{correct["label"]}", this leaves evidence unresolved.'
        )
        description = question["options"][1]["description"]
    elif case == "prompt-option-letter":
        question["prompt"] = "Option A is correct."
        description = option["description"]
    elif case == "prompt-option-number":
        question["prompt"] = "Option 1 is the correct answer."
        description = option["description"]
    elif case == "prompt-option-chinese-letter":
        question["prompt"] = "選項 A 是正確答案。"
        description = option["description"]
    elif case == "prompt-first-full-credit":
        question["prompt"] = (
            "The response shown first earns full credit; explain why."
        )
        description = option["description"]
    elif case == "prompt-top-answer":
        question["prompt"] = "The top response is the answer; explain why."
        description = option["description"]
    elif case == "scenario-option-full-credit":
        question["scenario_context"] = (
            "The evaluator marks option A as full credit."
        )
        description = option["description"]
    elif case == "intro-future-correct-label":
        future = raw["questions"][1]
        correct = next(
            item
            for item in future["options"]
            if item["id"] == future["correct_option_id"]
        )
        raw["instructions"] = (
            f'Answer key for the next item: {correct["label"]}'
        )
        description = option["description"]
    elif case == "intro-stable-option-id":
        raw["instructions"] = (
            f'Internal answer key: {raw["questions"][1]["correct_option_id"]}'
        )
        description = option["description"]
    elif case == "short-correct-id-label":
        for item, option_id in zip(question["options"], ("win", "lose", "bad")):
            item["id"] = option_id
        question["correct_option_id"] = "win"
        question["options"][0]["label"] = "win - validate the contract"
        description = question["options"][0]["description"]
    elif case == "short-wrong-id-label":
        question["options"][1]["id"] = "bad"
        question["options"][1]["label"] = "bad - continue with partial state"
        description = option["description"]
    elif case == "short-stopword-id-suffix-context":
        for item, option_id in zip(question["options"], ("a", "b", "c")):
            item["id"] = option_id
        question["correct_option_id"] = "a"
        question["options"][0]["description"] = (
            "a is the internal option key for workflow tracking."
        )
        description = question["options"][0]["description"]
    elif case == "prompt-equals-correct-label":
        correct = next(
            item
            for item in question["options"]
            if item["id"] == question["correct_option_id"]
        )
        question["prompt"] = correct["label"]
        description = option["description"]
    elif case == "prompt-contains-correct-label":
        correct = next(
            item
            for item in question["options"]
            if item["id"] == question["correct_option_id"]
        )
        question["prompt"] = (
            f'Proceed with "{correct["label"]}" before any side effect.'
        )
        description = option["description"]
    elif case == "prompt-short-correct-label":
        correct = next(
            item
            for item in question["options"]
            if item["id"] == question["correct_option_id"]
        )
        correct["label"] = "Approve"
        question["prompt"] = "Required next action: Approve."
        description = option["description"]
    elif case == "repeated-prompt-correct-label":
        future = raw["questions"][3]
        correct = next(
            item
            for item in future["options"]
            if item["id"] == future["correct_option_id"]
        )
        for item in raw["questions"][:4]:
            item["prompt"] = correct["label"]
        description = option["description"]
    elif case == "description-own-label-positive":
        option["description"] = (
            f'Required next action: {option["label"]}; '
            "downstream reporting remains separate."
        )
        description = option["description"]
    elif case == "description-own-label-negative":
        option["description"] = (
            f'Avoid {option["label"]}; the contract boundary remains unresolved.'
        )
        description = option["description"]
    elif case == "description-short-own-label-negative":
        option["label"] = "Run"
        option["description"] = (
            "Avoid Run; the contract boundary remains unresolved."
        )
        description = option["description"]
    elif case == "description-cjk-own-label-negative":
        option["label"] = "停"
        option["description"] = "不要選停；仍缺少必要條件。"
        description = option["description"]
    elif case == "zero-width-stable-id":
        option["description"] = (
            "Internal key a0-\u200bcorrect remains outside the learner surface."
        )
        description = option["description"]
    elif case == "zero-width-future-correct-label":
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
        description = option["description"]
    elif case == "label-future-correct":
        future = raw["questions"][1]
        option["label"] = next(
            item["label"]
            for item in future["options"]
            if item["id"] == future["correct_option_id"]
        )
        description = option["description"]
    else:
        description = case
    option["description"] = description
    return description


def write_completed_assessment(
    cycle_dir: Path, *, wrong_indices: set[int] | None = None
) -> tuple[dict, dict]:
    wrong_indices = wrong_indices or set()
    (cycle_dir / "assessment" / "responses").mkdir(parents=True, exist_ok=True)
    raw = assessment_spec()
    normalized = ui.core.validate_assessment_spec(
        raw, ui.core.validate_cycle(cycle_spec())
    )
    (cycle_dir / "assessment" / "spec.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    for index, question in enumerate(normalized["questions"]):
        selected = question["correct_option_id"]
        if index in wrong_indices:
            selected = next(
                option["id"]
                for option in question["options"]
                if option["id"] != question["correct_option_id"]
            )
        ui.core.record_response(
            cycle_dir / "assessment",
            normalized,
            question["question_id"],
            selected,
            [option["id"] for option in question["options"]],
            f"assessment-fixture-{index}",
        )
    report = ui.core.build_assessment_report(
        cycle_dir / "assessment", normalized, persist=True
    )
    return normalized, report


def write_learning_workspace(root: Path) -> tuple[Path, ui.SessionBundle]:
    cycle_dir = root / "mastery-sessions" / "agent-workflow-cycle"
    (cycle_dir / "learning" / "slices").mkdir(parents=True)
    (cycle_dir / "learning" / "events").mkdir(parents=True)
    (cycle_dir / "cycle.json").write_text(
        json.dumps(cycle_spec(), ensure_ascii=False), encoding="utf-8"
    )
    write_completed_assessment(cycle_dir)
    path_spec, slices = learning_fixture()
    (cycle_dir / "learning" / "path.json").write_text(
        json.dumps(path_spec, ensure_ascii=False), encoding="utf-8"
    )
    for slice_id, item in slices.items():
        (cycle_dir / "learning" / "slices" / f"{slice_id}.json").write_text(
            json.dumps(item, ensure_ascii=False), encoding="utf-8"
        )
    bundle = ui.load_phase_bundle(
        root, "mastery-sessions/agent-workflow-cycle", "learning"
    )
    return cycle_dir, bundle


def write_review_workspace(root: Path) -> tuple[Path, ui.SessionBundle]:
    cycle_dir = root / "mastery-sessions" / "agent-workflow-cycle"
    for path in (
        cycle_dir / "assessment" / "responses",
        cycle_dir / "learning" / "slices",
        cycle_dir / "learning" / "events",
        cycle_dir / "review" / "responses",
    ):
        path.mkdir(parents=True)
    (cycle_dir / "cycle.json").write_text(
        json.dumps(cycle_spec(), ensure_ascii=False), encoding="utf-8"
    )
    assessment, assessment_report = write_completed_assessment(
        cycle_dir, wrong_indices=set(range(5))
    )
    gaps_by_area = {
        area: [gap for gap in assessment_report["gaps"] if gap["area_id"] == area]
        for area in ("contracts", "recovery", "evidence")
    }
    counts = {area: 5 + len(gaps) for area, gaps in gaps_by_area.items()}
    path_spec, slices = learning_fixture(counts)
    questions_by_area = {
        area: [question for question in assessment["questions"] if question["area_id"] == area]
        for area in gaps_by_area
    }
    for area in gaps_by_area:
        area_slices = [slices[slice_id] for slice_id in next(
            item["slice_ids"] for item in path_spec["areas"] if item["area_id"] == area
        )]
        for index, gap in enumerate(gaps_by_area[area]):
            area_slices[index]["addresses_gap_ids"].append(gap["gap_id"])
        for index, question in enumerate(questions_by_area[area]):
            links = area_slices[index % len(area_slices)]["assessment_question_ids"]
            if question["question_id"] not in links:
                links.append(question["question_id"])
    (cycle_dir / "learning" / "path.json").write_text(
        json.dumps(path_spec, ensure_ascii=False), encoding="utf-8"
    )
    for slice_id, item in slices.items():
        (cycle_dir / "learning" / "slices" / f"{slice_id}.json").write_text(
            json.dumps(item, ensure_ascii=False), encoding="utf-8"
        )
    normalized_path = ui.core.validate_learning_path(
        path_spec,
        ui.core.validate_cycle(cycle_spec()),
        slices=slices,
        assessment_report=assessment_report,
        assessment_spec=assessment,
    )
    for area in path_spec["areas"]:
        for slice_id in area["slice_ids"]:
            ui.core.record_slice_completion(
                cycle_dir / "learning",
                normalized_path,
                slices,
                slice_id,
                f"slice-fixture-{slice_id}",
            )
        checkpoint = area["checkpoint"]
        ui.core.record_checkpoint_response(
            cycle_dir / "learning",
            normalized_path,
            area["area_id"],
            checkpoint["correct_option_id"],
            [option["id"] for option in checkpoint["options"]],
            f"checkpoint-fixture-{area['area_id']}",
            slices=slices,
        )
    ui.core.build_learning_report(
        cycle_dir / "learning", normalized_path, slices=slices, persist=True
    )
    (cycle_dir / "review" / "spec.json").write_text(
        json.dumps(review_spec(), ensure_ascii=False), encoding="utf-8"
    )
    bundle = ui.load_phase_bundle(
        root, "mastery-sessions/agent-workflow-cycle", "review"
    )
    return cycle_dir, bundle


class AssessmentUiTests(unittest.TestCase):
    def test_start_seals_the_complete_batch_against_future_question_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir, bundle = write_assessment_workspace(root)
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "seal-batch-start"})
            self.assertTrue((cycle_dir / "assessment" / "batch-manifest.json").is_file())

            changed = assessment_spec()
            changed["questions"][1]["prompt"] = "A changed future prompt."
            (cycle_dir / "assessment" / "spec.json").write_text(
                json.dumps(changed, ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaises(ui.core.SpecError):
                ui.load_phase_bundle(
                    root, "mastery-sessions/agent-workflow-cycle", "assessment"
                )

    def test_start_seals_confirmed_mission_scope_and_area_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir, bundle = write_assessment_workspace(root)
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "seal-cycle-contract"})

            changed_cycle = cycle_spec()
            changed_cycle["mission"]["ultimate_outcome"] = "A different outcome"
            changed_cycle["knowledge_scope"]["direction"] = "A different scope"
            changed_cycle["areas"][0]["title"] = "A reinterpreted area"
            (cycle_dir / "cycle.json").write_text(
                json.dumps(changed_cycle, ensure_ascii=False), encoding="utf-8"
            )

            with self.assertRaises(ui.core.SpecError):
                ui.load_phase_bundle(
                    root, "mastery-sessions/agent-workflow-cycle", "assessment"
                )

    def test_intro_has_scope_distribution_and_footer(self):
        with tempfile.TemporaryDirectory() as directory:
            _, bundle = write_assessment_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            page = runtime.render()
            self.assertIn("知識範圍", page)
            self.assertIn("12 題", page)
            self.assertIn("3 個主要領域", page)
            self.assertIn("Contracts · 4 題", page)
            self.assertIn("Benchmark：已驗證", page)
            self.assertIn("Created by Winston", page)
            self.assertIn("lang=\"zh-Hant\"", page)
            self.assertIn("確認範圍並開始", page)
            self.assertIn("調整範圍", page)
            self.assertIn("暫停", page)

    def test_intro_rejects_answer_material_in_cycle_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir = root / "mastery-sessions" / "agent-workflow-cycle"
            (cycle_dir / "assessment" / "responses").mkdir(parents=True)
            raw_spec = assessment_spec()
            first = raw_spec["questions"][0]
            correct = next(
                item
                for item in first["options"]
                if item["id"] == first["correct_option_id"]
            )
            raw_cycle = cycle_spec()
            raw_cycle["knowledge_scope"]["includes"][0] = (
                f'Correct: {correct["label"]}'
            )
            (cycle_dir / "cycle.json").write_text(
                json.dumps(raw_cycle, ensure_ascii=False), encoding="utf-8"
            )
            (cycle_dir / "assessment" / "spec.json").write_text(
                json.dumps(raw_spec, ensure_ascii=False), encoding="utf-8"
            )
            bundle = ui.load_phase_bundle(
                root, "mastery-sessions/agent-workflow-cycle", "assessment"
            )
            with self.assertRaises(ui.core.SpecError):
                ui._validate_phase_state(bundle)
            with self.assertRaises(ui.core.SpecError):
                ui.SessionRuntime(bundle).render()

    def test_intro_allows_plain_scope_term_that_is_also_an_option(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir = root / "mastery-sessions" / "agent-workflow-cycle"
            (cycle_dir / "assessment" / "responses").mkdir(parents=True)
            raw_cycle = cycle_spec()
            raw_cycle["knowledge_scope"]["includes"][0] = (
                "The assessment includes the idempotency concept and recovery evidence."
            )
            raw_spec = assessment_spec()
            raw_spec["questions"][0]["options"][0]["label"] = (
                "idempotency concept"
            )
            raw_spec["questions"][0]["title"] = "Contracts"
            (cycle_dir / "cycle.json").write_text(
                json.dumps(raw_cycle, ensure_ascii=False), encoding="utf-8"
            )
            (cycle_dir / "assessment" / "spec.json").write_text(
                json.dumps(raw_spec, ensure_ascii=False), encoding="utf-8"
            )
            bundle = ui.load_phase_bundle(
                root, "mastery-sessions/agent-workflow-cycle", "assessment"
            )
            state = ui._validate_phase_state(bundle)
            self.assertFalse(state["complete"])
            self.assertIn("idempotency", ui.SessionRuntime(bundle).render())

    def test_intro_rejects_visible_field_equal_to_correct_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir = root / "mastery-sessions" / "agent-workflow-cycle"
            (cycle_dir / "assessment" / "responses").mkdir(parents=True)
            raw_cycle = cycle_spec()
            raw_cycle["mission"]["ultimate_outcome"] = "Approve"
            raw_spec = assessment_spec()
            first = raw_spec["questions"][0]
            correct = next(
                item
                for item in first["options"]
                if item["id"] == first["correct_option_id"]
            )
            correct["label"] = "Approve"
            (cycle_dir / "cycle.json").write_text(
                json.dumps(raw_cycle, ensure_ascii=False), encoding="utf-8"
            )
            (cycle_dir / "assessment" / "spec.json").write_text(
                json.dumps(raw_spec, ensure_ascii=False), encoding="utf-8"
            )
            bundle = ui.load_phase_bundle(
                root, "mastery-sessions/agent-workflow-cycle", "assessment"
            )
            with self.assertRaises(ui.core.SpecError):
                ui._validate_phase_state(bundle)
            with self.assertRaises(ui.core.SpecError):
                ui.SessionRuntime(bundle).render()

    def test_intro_rejects_hidden_explanation_in_cycle_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir = root / "mastery-sessions" / "agent-workflow-cycle"
            (cycle_dir / "assessment" / "responses").mkdir(parents=True)
            raw_spec = assessment_spec()
            first = raw_spec["questions"][0]
            correct = next(
                item
                for item in first["options"]
                if item["id"] == first["correct_option_id"]
            )
            raw_cycle = cycle_spec()
            raw_cycle["knowledge_scope"]["includes"][0] = correct["explanation"]
            (cycle_dir / "cycle.json").write_text(
                json.dumps(raw_cycle, ensure_ascii=False), encoding="utf-8"
            )
            (cycle_dir / "assessment" / "spec.json").write_text(
                json.dumps(raw_spec, ensure_ascii=False), encoding="utf-8"
            )
            bundle = ui.load_phase_bundle(
                root, "mastery-sessions/agent-workflow-cycle", "assessment"
            )
            with self.assertRaises(ui.core.SpecError):
                ui._validate_phase_state(bundle)

    def test_question_hides_future_and_answer_data(self):
        with tempfile.TemporaryDirectory() as directory:
            _, bundle = write_assessment_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-1"})
            page = runtime.render()
            first = bundle.spec["questions"][0]
            future = bundle.spec["questions"][1]
            self.assertIn(first["prompt"], page)
            self.assertIn(first["options"][0]["description"], page)
            self.assertNotIn(future["prompt"], page)
            self.assertNotIn(first["correct_option_id"], page)
            self.assertNotIn(first["options"][0]["explanation"], page)
            self.assertNotIn(first["options"][1]["misconception_tag"], page)
            self.assertNotIn("/record", page)
            self.assertNotIn("記錄這個錯誤", page)
            self.assertIn("<progress", page)
            self.assertIn("第 1 / 12 題", page)

    def test_sealed_legacy_batch_hides_entire_unsafe_description_set(self):
        unsafe_descriptions = (
            "符合這一題的遺傳核心命題。",
            "This is the preferred approach.",
            "This choice should be selected.",
            "這是首選做法。",
            "Status: PASS; all gates are satisfied.",
            "This response earns full credit.",
            "評分：滿分。",
            "Meets every requirement with no unresolved gaps.",
            "所有條件皆已滿足，沒有缺口。",
            "這個說法已涵蓋題目所需的所有機制。",
            "已全面涵蓋題目機制；其他延伸細節另行處理。",
            "Comprehensively covers the requested mechanisms; downstream details remain separate.",
            "Satisfies the criteria in the prompt; downstream cases remain separate.",
            "Meets the condition in the prompt.",
            "The answer; downstream cases remain separate.",
            "Describes a plausible workflow action.",
            "description-other-option-label",
            "description-own-label-positive",
            "description-own-label-negative",
            "description-short-own-label-negative",
            "description-cjk-own-label-negative",
            "zero-width-stable-id",
            "zero-width-future-correct-label",
            "short-stopword-id-suffix-context",
            "✅",
            "future-prompt",
            "short-future-prompt",
            "future-correct-label",
            "stable-option-id",
            "embedded-stable-option-id",
            "plain-stable-option-id",
        )
        for unsafe_case in unsafe_descriptions:
            with self.subTest(description=unsafe_case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cycle_dir, _ = write_assessment_workspace(root)
                raw = assessment_spec()
                apply_unsafe_choice_case(raw, unsafe_case)
                spec_path = cycle_dir / "assessment" / "spec.json"
                spec_path.write_text(
                    json.dumps(raw, ensure_ascii=False), encoding="utf-8"
                )
                normalized = ui.core.validate_assessment_spec(
                    raw, ui.core.validate_cycle(cycle_spec())
                )
                ui.core.write_json_once(
                    cycle_dir / "assessment" / "batch-manifest.json",
                    {
                        "schema_version": 3,
                        "record_type": "batch_manifest",
                        "phase": "assessment",
                        "cycle_id": normalized["cycle_id"],
                        "cycle_contract_digest": normalized[
                            "cycle_contract_digest"
                        ],
                        "spec_digest": ui.core._batch_spec_digest(normalized),
                        "question_ids": [
                            item["question_id"] for item in normalized["questions"]
                        ],
                        "sealed_at": ui.core.utc_now(),
                    },
                )

                bundle = ui.load_phase_bundle(
                    root, "mastery-sessions/agent-workflow-cycle", "assessment"
                )
                page = ui.SessionRuntime(bundle).render()
                first = bundle.spec["questions"][0]
                for option in first["options"]:
                    self.assertIn(option["label"], page)
                    self.assertNotIn(option["description"], page)
                self.assertNotIn('class="choice-desc"', page)

    def test_sealed_legacy_batch_blocks_unsafe_prompt_surface(self):
        for unsafe_case in (
            "prompt-hidden-explanation",
            "prompt-stable-option-id",
            "prompt-correct-position",
            "prompt-correct-label",
            "prompt-future-wrong-explanation",
            "prompt-future-wrong-label",
            "prompt-current-wrong-label",
            "prompt-option-letter",
            "prompt-option-number",
            "prompt-option-chinese-letter",
            "prompt-first-full-credit",
            "prompt-top-answer",
            "scenario-option-full-credit",
            "intro-future-correct-label",
            "intro-stable-option-id",
            "short-correct-id-label",
            "short-wrong-id-label",
            "prompt-equals-correct-label",
            "prompt-contains-correct-label",
            "prompt-short-correct-label",
            "repeated-prompt-correct-label",
            "label-future-correct",
        ):
            with self.subTest(case=unsafe_case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cycle_dir, _ = write_assessment_workspace(root)
                raw = assessment_spec()
                apply_unsafe_choice_case(raw, unsafe_case)
                (cycle_dir / "assessment" / "spec.json").write_text(
                    json.dumps(raw, ensure_ascii=False), encoding="utf-8"
                )
                normalized = ui.core.validate_assessment_spec(
                    raw, ui.core.validate_cycle(cycle_spec())
                )
                ui.core.write_json_once(
                    cycle_dir / "assessment" / "batch-manifest.json",
                    {
                        "schema_version": 3,
                        "record_type": "batch_manifest",
                        "phase": "assessment",
                        "cycle_id": normalized["cycle_id"],
                        "cycle_contract_digest": normalized[
                            "cycle_contract_digest"
                        ],
                        "spec_digest": ui.core._batch_spec_digest(normalized),
                        "question_ids": [
                            item["question_id"] for item in normalized["questions"]
                        ],
                        "sealed_at": ui.core.utc_now(),
                    },
                )
                bundle = ui.load_phase_bundle(
                    root, "mastery-sessions/agent-workflow-cycle", "assessment"
                )
                with self.assertRaises(ui.core.SpecError):
                    ui._validate_phase_state(bundle)
                with self.assertRaises(ui.core.SpecError):
                    ui.SessionRuntime(bundle).render()

    def test_sealed_legacy_batch_allows_repeated_prompt_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir, _ = write_assessment_workspace(root)
            raw = assessment_spec()
            repeated_prompt = "Choose the action that preserves the stated boundary."
            for question in raw["questions"]:
                question["prompt"] = repeated_prompt
            (cycle_dir / "assessment" / "spec.json").write_text(
                json.dumps(raw, ensure_ascii=False), encoding="utf-8"
            )
            normalized = ui.core.validate_assessment_spec(
                raw, ui.core.validate_cycle(cycle_spec())
            )
            ui.core.write_json_once(
                cycle_dir / "assessment" / "batch-manifest.json",
                {
                    "schema_version": 3,
                    "record_type": "batch_manifest",
                    "phase": "assessment",
                    "cycle_id": normalized["cycle_id"],
                    "cycle_contract_digest": normalized["cycle_contract_digest"],
                    "spec_digest": ui.core._batch_spec_digest(normalized),
                    "question_ids": [
                        item["question_id"] for item in normalized["questions"]
                    ],
                    "sealed_at": ui.core.utc_now(),
                },
            )
            bundle = ui.load_phase_bundle(
                root, "mastery-sessions/agent-workflow-cycle", "assessment"
            )
            state = ui._validate_phase_state(bundle)
            self.assertFalse(state["complete"])
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-template"})
            self.assertIn(repeated_prompt, runtime.render())

    def test_wrong_answer_saves_immediately_and_explains_both(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir, bundle = write_assessment_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-1"})
            question = bundle.spec["questions"][0]
            option_tokens = runtime._option_tokens[question["question_id"]]
            wrong_token, wrong = option_tokens[1]
            page = runtime.answer(
                {
                    "request_id": "answer-1",
                    "question_token": runtime._question_tokens[question["question_id"]],
                    "option_token": wrong_token,
                }
            )
            response_path = cycle_dir / "assessment" / "responses" / f"{question['question_id']}.json"
            self.assertTrue(response_path.is_file())
            self.assertIn(wrong["explanation"], page)
            correct = next(
                option for option in question["options"] if option["id"] == question["correct_option_id"]
            )
            self.assertIn(correct["explanation"], page)
            self.assertIn("下一題", page)
            self.assertNotIn("記錄這個錯誤", page)

    def test_refresh_and_restart_restore_feedback_until_next(self):
        with tempfile.TemporaryDirectory() as directory:
            _, bundle = write_assessment_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-1"})
            question = bundle.spec["questions"][0]
            token, _ = runtime._option_tokens[question["question_id"]][0]
            runtime.answer(
                {
                    "request_id": "answer-1",
                    "question_token": runtime._question_tokens[question["question_id"]],
                    "option_token": token,
                }
            )
            restarted = ui.SessionRuntime(bundle)
            page = restarted.render()
            self.assertIn("回答正確", page)
            self.assertIn("下一題", page)
            state = restarted._checkpoint()
            self.assertEqual(state["screen"], "feedback")
            self.assertEqual(state["index"], 0)

    def test_twelve_answers_emit_server_report(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir, bundle = write_assessment_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-1"})
            final_page = ""
            for index, question in enumerate(bundle.spec["questions"]):
                option_token, _ = runtime._option_tokens[question["question_id"]][index % 2]
                runtime.answer(
                    {
                        "request_id": f"answer-{index}",
                        "question_token": runtime._question_tokens[question["question_id"]],
                        "option_token": option_token,
                    }
                )
                final_page = runtime.next(
                    {
                        "request_id": f"next-{index}",
                        "next_token": runtime._next_tokens[question["question_id"]],
                    }
                )
            report_path = cycle_dir / "assessment" / "report.json"
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["answered"], 12)
            self.assertEqual(len(report["area_results"]), 3)
            self.assertIn("你的知識訊號總表", final_page)
            self.assertIn("題目追溯", final_page)
            self.assertIn("請關閉此頁並回到 Codex", final_page)

    def test_future_and_stale_navigation_tokens_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            _, bundle = write_assessment_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-1"})
            second = bundle.spec["questions"][1]
            with self.assertRaises(ui.UiError):
                runtime.answer(
                    {
                        "request_id": "answer-future",
                        "question_token": runtime._question_tokens[second["question_id"]],
                        "option_token": runtime._option_tokens[second["question_id"]][0][0],
                    }
                )
            with self.assertRaises(ui.UiError):
                runtime.next({"request_id": "next-stale", "next_token": "stale"})


class LearningUiTests(unittest.TestCase):
    def test_map_previews_titles_but_lazily_reveals_content(self):
        with tempfile.TemporaryDirectory() as directory:
            _, bundle = write_learning_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            intro = runtime.render()
            first, second = list(bundle.slices.values())[:2]
            self.assertIn(first["title"], intro)
            self.assertIn(second["title"], intro)
            self.assertNotIn(first["core_explanation"], intro)
            self.assertNotIn(second["worked_example"]["walkthrough"], intro)
            first_page = runtime.start({"request_id": "start-learning"})
            self.assertIn(first["core_explanation"], first_page)
            self.assertNotIn(second["core_explanation"], first_page)
            self.assertIn("完成閱讀只計學習進度", intro)
            with self.assertRaises(ui.UiError):
                runtime.view_slice(second["slice_id"])

    def test_map_rejects_checkpoint_explanation_in_locked_slice_title(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir, bundle = write_learning_workspace(root)
            area = bundle.spec["areas"][0]
            correct = next(
                item
                for item in area["checkpoint"]["options"]
                if item["id"] == area["checkpoint"]["correct_option_id"]
            )
            locked_id = area["slice_ids"][1]
            slice_path = cycle_dir / "learning" / "slices" / f"{locked_id}.json"
            raw_slice = json.loads(slice_path.read_text(encoding="utf-8"))
            raw_slice["title"] = correct["explanation"]
            slice_path.write_text(
                json.dumps(raw_slice, ensure_ascii=False), encoding="utf-8"
            )
            reloaded = ui.load_phase_bundle(
                root, "mastery-sessions/agent-workflow-cycle", "learning"
            )
            with self.assertRaises(ui.core.SpecError):
                ui._validate_phase_state(reloaded)
            with self.assertRaises(ui.core.SpecError):
                ui.SessionRuntime(reloaded).render()

    def test_slice_events_are_write_once_and_completed_nodes_can_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir, bundle = write_learning_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-learning"})
            first_id = bundle.spec["areas"][0]["slice_ids"][0]
            next_page = runtime.complete_slice(
                {
                    "request_id": "complete-first",
                    "slice_token": runtime._slice_tokens[first_id],
                }
            )
            event = cycle_dir / "learning" / "events" / f"slice_completed.{first_id}.json"
            self.assertTrue(event.is_file())
            self.assertIn(bundle.spec["areas"][0]["slice_ids"][1], runtime._slice_tokens)
            self.assertIn("知識地圖 · 2 / 15", next_page)
            retry_page = runtime.complete_slice(
                {
                    "request_id": "complete-first-retry",
                    "slice_token": runtime._slice_tokens[first_id],
                }
            )
            self.assertIn("知識地圖 · 2 / 15", retry_page)
            review_page = runtime.view_slice(first_id)
            self.assertIn("回到目前進度", review_page)
            self.assertIn(bundle.slices[first_id]["core_explanation"], review_page)

    def test_three_areas_slices_checks_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir, bundle = write_learning_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-learning"})
            final_page = ""
            for area_index, area in enumerate(bundle.spec["areas"]):
                for slice_id in area["slice_ids"]:
                    final_page = runtime.complete_slice(
                        {
                            "request_id": f"complete-{slice_id}",
                            "slice_token": runtime._slice_tokens[slice_id],
                        }
                    )
                self.assertIn("形成性檢核", final_page)
                tokens = runtime._learning_option_tokens[area["area_id"]]
                if area_index == 0:
                    option_token, _ = next(
                        pair
                        for pair in tokens
                        if pair[1]["id"] != area["checkpoint"]["correct_option_id"]
                    )
                else:
                    option_token, _ = next(
                        pair
                        for pair in tokens
                        if pair[1]["id"] == area["checkpoint"]["correct_option_id"]
                    )
                feedback = runtime.answer_checkpoint(
                    {
                        "request_id": f"check-{area['area_id']}",
                        "question_token": runtime._learning_question_tokens[area["area_id"]],
                        "option_token": option_token,
                    }
                )
                self.assertIn("檢核結果", feedback)
                final_page = runtime.next_checkpoint(
                    {
                        "request_id": f"check-next-{area['area_id']}",
                        "next_token": runtime._learning_next_tokens[area["area_id"]],
                    }
                )
            report_path = cycle_dir / "learning" / "report.json"
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["complete"])
            self.assertEqual(report["completed_slices"], 15)
            self.assertEqual(len(report["gaps"]), 1)
            self.assertIn("知識地圖已走完", final_page)
            self.assertIn("mastery 等級", final_page)


class ReviewUiTests(unittest.TestCase):
    def test_intro_and_question_conceal_future_answer_surfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            _, bundle = write_review_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            intro = runtime.render()
            self.assertIn("整合複習", intro)
            self.assertIn("全新情境", intro)
            self.assertIn("8 題", intro)
            page = runtime.start({"request_id": "start-review"})
            first, future = bundle.spec["questions"][:2]
            self.assertIn(first["prompt"], page)
            self.assertNotIn(future["prompt"], page)
            self.assertNotIn(first["correct_option_id"], page)
            self.assertNotIn(first["options"][0]["explanation"], page)
            self.assertNotIn("/record", page)

    def test_eight_answers_emit_comparison_and_delayed_review(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir, bundle = write_review_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-review"})
            final_page = ""
            for index, question in enumerate(bundle.spec["questions"]):
                choose_correct = index in {0, 1, 2, 3, 6, 7}
                target_id = question["correct_option_id"]
                option_token, option = next(
                    pair
                    for pair in runtime._option_tokens[question["question_id"]]
                    if (pair[1]["id"] == target_id) is choose_correct
                )
                feedback = runtime.answer(
                    {
                        "request_id": f"review-answer-{index}",
                        "question_token": runtime._question_tokens[question["question_id"]],
                        "option_token": option_token,
                    }
                )
                self.assertIn(option["explanation"], feedback)
                final_page = runtime.next(
                    {
                        "request_id": f"review-next-{index}",
                        "next_token": runtime._next_tokens[question["question_id"]],
                    }
                )
            report_path = cycle_dir / "review" / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["complete"])
            self.assertTrue(report["corrected_gap_ids"])
            self.assertTrue(report["remaining_gap_ids"])
            self.assertTrue(report["new_errors"])
            self.assertTrue(report["reinforced_concepts"])
            self.assertTrue(report["delayed_review"])
            self.assertIn("評估錯誤 → 複習修正", final_page)
            self.assertIn("延遲複習清單", final_page)
            self.assertIn("完成日後三天", final_page)
            response = json.loads(
                (cycle_dir / "review" / "responses" / "review-q00.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(response["feedback_exposed"])


class V3HttpContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        _, bundle = write_assessment_workspace(Path(self.temporary.name))
        self.runtime = ui.SessionRuntime(bundle)
        self.runtime.start({"request_id": "http-start"})
        self.server = ui._create_server(self.runtime, 0)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()
        self.temporary.cleanup()

    def get(self, path: str = "/"):
        with urllib.request.urlopen(self.url + path, timeout=3) as response:
            return response.read().decode("utf-8"), response.headers

    def post(
        self,
        path: str,
        payload: dict,
        *,
        token: str | None = None,
        origin: str | None = None,
    ):
        headers = {
            "Content-Type": "application/json",
            "X-Mastery-Token": token if token is not None else self.runtime.csrf,
        }
        if origin is not None:
            headers["Origin"] = origin
        request = urllib.request.Request(
            self.url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.read().decode("utf-8"), response.headers

    def test_security_headers_and_no_record_route(self):
        page, headers = self.get()
        self.assertIn("第 1 / 12 題", page)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.post("/record", {"request_id": "record-does-not-exist"})
        self.assertEqual(rejected.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as csrf_rejected:
            self.post("/next", {"request_id": "csrf-fail"}, token="wrong")
        self.assertEqual(csrf_rejected.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as origin_rejected:
            self.post(
                "/next",
                {"request_id": "origin-fail"},
                origin="https://attacker.example",
            )
        self.assertEqual(origin_rejected.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as body_rejected:
            self.post("/next", {"request_id": "body-limit", "padding": "x" * 70000})
        self.assertEqual(body_rejected.exception.code, 413)

    def test_storage_failure_returns_http_500_instead_of_disconnect(self):
        def fail_storage(_payload):
            raise OSError("simulated storage failure")

        self.runtime.start = fail_storage
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.post("/start", {"request_id": "storage-failure"})
        self.assertEqual(rejected.exception.code, 500)
        self.assertIn("Storage unavailable", rejected.exception.read().decode("utf-8"))

    def test_retry_is_idempotent_and_conflicting_answer_is_409(self):
        question = self.runtime.bundle.spec["questions"][0]
        first_token = self.runtime._option_tokens[question["question_id"]][0][0]
        second_token = self.runtime._option_tokens[question["question_id"]][1][0]
        base = {
            "question_token": self.runtime._question_tokens[question["question_id"]],
            "option_token": first_token,
        }
        first, _ = self.post("/answer", {"request_id": "http-answer-1", **base})
        retry, _ = self.post("/answer", {"request_id": "http-answer-retry", **base})
        self.assertIn("下一題", first)
        self.assertIn("下一題", retry)
        with self.assertRaises(urllib.error.HTTPError) as conflict:
            self.post(
                "/answer",
                {
                    "request_id": "http-answer-conflict",
                    "question_token": base["question_token"],
                    "option_token": second_token,
                },
            )
        self.assertEqual(conflict.exception.code, 409)
        next_payload = {
            "request_id": "http-next-1",
            "next_token": self.runtime._next_tokens[question["question_id"]],
        }
        advanced, _ = self.post("/next", next_payload)
        retried, _ = self.post(
            "/next", {**next_payload, "request_id": "http-next-retry"}
        )
        second = self.runtime.bundle.spec["questions"][1]
        self.assertIn(second["prompt"], advanced)
        self.assertIn(second["prompt"], retried)


class CheckpointRecoveryTests(unittest.TestCase):
    def test_unsealed_first_question_checkpoint_returns_to_intro(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir, bundle = write_assessment_workspace(Path(directory))
            first = bundle.spec["questions"][0]
            ui.core.atomic_write_json(
                cycle_dir / "checkpoint.json",
                {
                    "schema_version": 3,
                    "cycle_id": bundle.cycle["cycle_id"],
                    "phase": "assessment",
                    "screen": "question",
                    "index": 0,
                    "subject_id": first["question_id"],
                },
            )

            runtime = ui.SessionRuntime(bundle)
            page = runtime.render()
            self.assertIn("確認範圍並開始", page)
            self.assertNotIn(first["prompt"], page)
            self.assertFalse(
                (cycle_dir / "assessment" / "batch-manifest.json").exists()
            )

            started = runtime.start({"request_id": "seal-after-recovery"})
            self.assertIn(first["prompt"], started)
            self.assertTrue(
                (cycle_dir / "assessment" / "batch-manifest.json").is_file()
            )

    def test_corrupt_checkpoint_rebuilds_conservative_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir, bundle = write_assessment_workspace(Path(directory))
            runtime = ui.SessionRuntime(bundle)
            runtime.start({"request_id": "start-recovery"})
            question = bundle.spec["questions"][0]
            runtime.answer(
                {
                    "request_id": "answer-recovery",
                    "question_token": runtime._question_tokens[question["question_id"]],
                    "option_token": runtime._option_tokens[question["question_id"]][0][0],
                }
            )
            (cycle_dir / "checkpoint.json").write_text("{broken", encoding="utf-8")
            restarted = ui.SessionRuntime(bundle)
            page = restarted.render()
            self.assertIn("回答正確", page)
            self.assertEqual(restarted._checkpoint()["screen"], "feedback")

    def test_future_checkpoint_cannot_jump_to_last_question(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle_dir, bundle = write_assessment_workspace(Path(directory))
            ui.core.atomic_write_json(
                cycle_dir / "checkpoint.json",
                {
                    "schema_version": 3,
                    "cycle_id": bundle.cycle["cycle_id"],
                    "phase": "assessment",
                    "screen": "question",
                    "index": 11,
                    "subject_id": bundle.spec["questions"][11]["question_id"],
                },
            )
            runtime = ui.SessionRuntime(bundle)
            page = runtime.render()
            self.assertIn("確認範圍並開始", page)
            self.assertNotIn(bundle.spec["questions"][11]["prompt"], page)

    def test_learning_load_rebuilds_report_and_review_rejects_empty_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir, bundle = write_learning_workspace(root)
            (cycle_dir / "assessment" / "report.json").write_text(
                json.dumps({"gaps": [{"gap_id": "forged"}]}), encoding="utf-8"
            )
            rebuilt = ui.load_phase_bundle(
                root, "mastery-sessions/agent-workflow-cycle", "learning"
            )
            self.assertEqual(rebuilt.assessment_report["gaps"], [])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle_dir, _ = write_review_workspace(root)
            first_event = next(
                (cycle_dir / "learning" / "events").glob("slice_completed.*.json")
            )
            first_event.write_text("{}", encoding="utf-8")
            with self.assertRaises(ui.core.SpecError):
                ui.load_phase_bundle(
                    root, "mastery-sessions/agent-workflow-cycle", "review"
                )

    def test_cycle_reference_cannot_escape_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ui.core.SpecError):
                ui.load_phase_bundle(Path(directory), "../outside", "assessment")


class PublicCliTests(unittest.TestCase):
    def command(self, workspace: Path, phase: str, action: str = "validate"):
        values = [
            sys.executable,
            str(ROOT / "scripts" / "mastery_session_ui.py"),
            action,
            "--workspace",
            str(workspace),
            "--cycle",
            "mastery-sessions/agent-workflow-cycle",
            "--phase",
            phase,
        ]
        if action == "serve":
            values.extend(["--port", "0", "--idle-timeout", "1"])
        return subprocess.run(values, capture_output=True, text=True, timeout=8)

    def test_validate_supports_all_three_phases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assessment_root = root / "assessment-workspace"
            learning_root = root / "learning-workspace"
            review_root = root / "review-workspace"
            write_assessment_workspace(assessment_root)
            write_learning_workspace(learning_root)
            write_review_workspace(review_root)
            for workspace, phase in (
                (assessment_root, "assessment"),
                (learning_root, "learning"),
                (review_root, "review"),
            ):
                result = self.command(workspace, phase)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["phase"], phase)

    def test_validate_and_serve_reject_unsafe_choice_copy_before_seal(self):
        for unsafe_case in (
            "符合這一題的遺傳核心命題。",
            "This is the preferred approach.",
            "future-prompt",
            "short-future-prompt",
            "future-correct-label",
            "stable-option-id",
            "embedded-stable-option-id",
            "plain-stable-option-id",
            "prompt-hidden-explanation",
            "prompt-stable-option-id",
            "prompt-correct-position",
            "prompt-correct-label",
            "prompt-future-wrong-explanation",
            "prompt-future-wrong-label",
            "prompt-current-wrong-label",
            "description-other-option-label",
            "prompt-option-letter",
            "prompt-option-number",
            "prompt-option-chinese-letter",
            "prompt-first-full-credit",
            "prompt-top-answer",
            "scenario-option-full-credit",
            "intro-future-correct-label",
            "intro-stable-option-id",
            "short-correct-id-label",
            "short-wrong-id-label",
            "short-stopword-id-suffix-context",
            "description-own-label-positive",
            "description-own-label-negative",
            "description-short-own-label-negative",
            "description-cjk-own-label-negative",
            "zero-width-stable-id",
            "zero-width-future-correct-label",
            "prompt-equals-correct-label",
            "prompt-contains-correct-label",
            "prompt-short-correct-label",
            "repeated-prompt-correct-label",
            "label-future-correct",
            "Status: PASS; all gates are satisfied.",
            "This response earns full credit.",
            "Meets every requirement with no unresolved gaps.",
            "所有條件皆已滿足，沒有缺口。",
            "這個說法已涵蓋題目所需的所有機制。",
            "已全面涵蓋題目機制；其他延伸細節另行處理。",
            "Comprehensively covers the requested mechanisms; downstream details remain separate.",
            "Satisfies the criteria in the prompt; downstream cases remain separate.",
            "Meets the condition in the prompt.",
            "The answer; downstream cases remain separate.",
            "Describes a plausible workflow action.",
        ):
            with self.subTest(description=unsafe_case), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                cycle_dir, _ = write_assessment_workspace(workspace)
                raw = assessment_spec()
                apply_unsafe_choice_case(raw, unsafe_case)
                (cycle_dir / "assessment" / "spec.json").write_text(
                    json.dumps(raw, ensure_ascii=False), encoding="utf-8"
                )

                for action in ("validate", "serve"):
                    result = self.command(workspace, "assessment", action)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    payload = json.loads(result.stderr)
                    self.assertFalse(payload["ok"])
                    self.assertTrue(
                        any(
                            marker in payload["error"]
                            for marker in (
                                "reveals correctness",
                                "hidden or future question content",
                                "stable internal token",
                                "must add an explicit boundary",
                                "must supplement rather than repeat",
                            )
                        ),
                        payload["error"],
                    )
                self.assertFalse(
                    (cycle_dir / "assessment" / "batch-manifest.json").exists()
                )

    def test_validate_and_lock_rejected_serve_do_not_rewrite_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            cycle_dir, _ = write_learning_workspace(workspace)
            report_path = cycle_dir / "assessment" / "report.json"
            sentinel = b'{"sentinel":"preserve-me"}\n'
            report_path.write_bytes(sentinel)

            validated = self.command(workspace, "learning")
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertEqual(report_path.read_bytes(), sentinel)

            with ui.core.PhaseLock(cycle_dir, "assessment"):
                rejected = self.command(workspace, "learning", "serve")
            self.assertEqual(rejected.returncode, 2, rejected.stderr)
            self.assertEqual(report_path.read_bytes(), sentinel)

    def test_validate_rejects_corrupt_phase_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            assessment_root = root / "assessment"
            assessment_cycle, assessment_bundle = write_assessment_workspace(
                assessment_root
            )
            first_question = assessment_bundle.spec["questions"][0]
            ui.core.record_response(
                assessment_cycle / "assessment",
                assessment_bundle.spec,
                first_question["question_id"],
                first_question["correct_option_id"],
                [option["id"] for option in first_question["options"]],
                "corrupt-assessment-fixture",
            )
            response_path = (
                assessment_cycle
                / "assessment"
                / "responses"
                / f"{first_question['question_id']}.json"
            )
            response_path.write_text("{}", encoding="utf-8")
            self.assertEqual(
                self.command(assessment_root, "assessment").returncode, 2
            )
            rejected_serve = self.command(
                assessment_root, "assessment", "serve"
            )
            self.assertEqual(rejected_serve.returncode, 2)
            self.assertNotIn('"ready": true', rejected_serve.stdout.lower())

            learning_root = root / "learning"
            learning_cycle, learning_bundle = write_learning_workspace(learning_root)
            first_slice = learning_bundle.spec["areas"][0]["slice_ids"][0]
            event_path = (
                learning_cycle
                / "learning"
                / "events"
                / f"slice_completed.{first_slice}.json"
            )
            event_path.write_text("{}", encoding="utf-8")
            self.assertEqual(self.command(learning_root, "learning").returncode, 2)

            review_root = root / "review"
            review_cycle, review_bundle = write_review_workspace(review_root)
            review_question = review_bundle.spec["questions"][0]
            review_response = (
                review_cycle
                / "review"
                / "responses"
                / f"{review_question['question_id']}.json"
            )
            review_response.write_text("{}", encoding="utf-8")
            self.assertEqual(self.command(review_root, "review").returncode, 2)

    def test_validate_rejects_invalid_utf8_as_structured_error(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            cycle_dir, _ = write_assessment_workspace(workspace)
            (cycle_dir / "assessment" / "spec.json").write_bytes(b"\xff\xfe\x00")

            result = self.command(workspace, "assessment")
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stderr)
            self.assertFalse(payload["ok"])
            self.assertIn("Invalid JSON object", payload["error"])

    def test_validate_and_serve_reject_evidence_path_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assessment_root = root / "assessment"
            learning_root = root / "learning"
            review_root = root / "review"
            assessment_cycle, assessment_bundle = write_assessment_workspace(
                assessment_root
            )
            learning_cycle, learning_bundle = write_learning_workspace(
                learning_root
            )
            review_cycle, review_bundle = write_review_workspace(review_root)
            blocked_paths = (
                (
                    assessment_root,
                    "assessment",
                    assessment_cycle
                    / "assessment"
                    / "responses"
                    / f"{assessment_bundle.spec['questions'][0]['question_id']}.json",
                ),
                (
                    learning_root,
                    "learning",
                    learning_cycle
                    / "learning"
                    / "events"
                    / f"slice_completed.{learning_bundle.spec['areas'][0]['slice_ids'][0]}.json",
                ),
                (
                    review_root,
                    "review",
                    review_cycle
                    / "review"
                    / "responses"
                    / f"{review_bundle.spec['questions'][0]['question_id']}.json",
                ),
            )
            for workspace, phase, blocked_path in blocked_paths:
                blocked_path.mkdir()
                validated = self.command(workspace, phase)
                served = self.command(workspace, phase, "serve")
                self.assertEqual(validated.returncode, 2, validated.stderr)
                self.assertEqual(served.returncode, 2, served.stderr)
                self.assertNotIn('"ready": true', served.stdout.lower())

    def test_validate_and_serve_reject_invalid_reserved_write_surfaces(self):
        case_names = (
            "responses-file",
            "events-file",
            "review-responses-file",
            "manifest-directory",
            "checkpoint-directory",
            "report-directory",
            "lock-directory",
        )
        for case_name in case_names:
            with self.subTest(case=case_name), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                if case_name == "events-file":
                    cycle_dir, _ = write_learning_workspace(workspace)
                    phase = "learning"
                    blocked = cycle_dir / "learning" / "events"
                    for child in blocked.iterdir():
                        child.unlink()
                    blocked.rmdir()
                    blocked.write_text("blocked", encoding="utf-8")
                elif case_name == "review-responses-file":
                    cycle_dir, _ = write_review_workspace(workspace)
                    phase = "review"
                    blocked = cycle_dir / "review" / "responses"
                    blocked.rmdir()
                    blocked.write_text("blocked", encoding="utf-8")
                else:
                    cycle_dir, _ = write_assessment_workspace(workspace)
                    phase = "assessment"
                    if case_name == "responses-file":
                        blocked = cycle_dir / "assessment" / "responses"
                        blocked.rmdir()
                        blocked.write_text("blocked", encoding="utf-8")
                    elif case_name == "manifest-directory":
                        (cycle_dir / "assessment" / "batch-manifest.json").mkdir()
                    elif case_name == "checkpoint-directory":
                        (cycle_dir / "checkpoint.json").mkdir()
                    elif case_name == "report-directory":
                        (cycle_dir / "assessment" / "report.json").mkdir()
                    else:
                        (cycle_dir / ".cycle.lock").mkdir()

                validated = self.command(workspace, phase)
                served = self.command(workspace, phase, "serve")
                self.assertEqual(validated.returncode, 2, validated.stderr)
                self.assertEqual(served.returncode, 2, served.stderr)
                self.assertNotIn('"ready": true', served.stdout.lower())

    def test_mutable_evidence_directory_cannot_link_outside_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            outside = root / "outside"
            outside.mkdir()
            cycle_dir, _ = write_assessment_workspace(workspace)
            responses = cycle_dir / "assessment" / "responses"
            responses.rmdir()
            try:
                os.symlink(outside, responses, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Symbolic links are unavailable: {exc}")

            validated = self.command(workspace, "assessment")
            served = self.command(workspace, "assessment", "serve")
            self.assertEqual(validated.returncode, 2, validated.stderr)
            self.assertEqual(served.returncode, 2, served.stderr)
            self.assertNotIn('"ready": true', served.stdout.lower())
            self.assertEqual(list(outside.iterdir()), [])

    def test_server_close_waits_for_active_request_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            _, bundle = write_assessment_workspace(workspace)
            runtime = ui.SessionRuntime(bundle)
            entered = threading.Event()
            release = threading.Event()
            closed = threading.Event()
            client_errors: list[Exception] = []
            original_render = runtime.render

            def slow_render():
                entered.set()
                if not release.wait(3):
                    raise AssertionError("slow render was not released")
                return original_render()

            runtime.render = slow_render
            server = ui._create_server(runtime, 0)
            serve_thread = threading.Thread(target=server.serve_forever)
            serve_thread.start()
            url = f"http://127.0.0.1:{server.server_address[1]}/"

            def request_page():
                try:
                    with urllib.request.urlopen(url, timeout=5) as response:
                        response.read()
                except Exception as exc:  # pragma: no cover - asserted below
                    client_errors.append(exc)

            client_thread = threading.Thread(target=request_page)
            client_thread.start()
            try:
                self.assertFalse(server.daemon_threads)
                self.assertTrue(server.block_on_close)
                self.assertTrue(entered.wait(2))
                server.shutdown()
                serve_thread.join(2)
                self.assertFalse(serve_thread.is_alive())

                def close_server():
                    server.server_close()
                    closed.set()

                close_thread = threading.Thread(target=close_server)
                close_thread.start()
                self.assertFalse(closed.wait(0.1))
                release.set()
                close_thread.join(2)
                client_thread.join(2)
                self.assertTrue(closed.is_set())
                self.assertFalse(client_thread.is_alive())
                self.assertEqual(client_errors, [])
            finally:
                release.set()
                server.shutdown()
                server.server_close()
                serve_thread.join(2)
                client_thread.join(2)

    def test_serve_prints_loopback_readiness_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            cycle_dir, _ = write_assessment_workspace(workspace)
            result = self.command(workspace, "assessment", "serve")
            self.assertEqual(result.returncode, 0, result.stderr)
            readiness = json.loads(result.stdout.strip().splitlines()[0])
            self.assertTrue(readiness["ready"])
            self.assertTrue(readiness["url"].startswith("http://127.0.0.1:"))
            lock_state = json.loads(
                (cycle_dir / ".cycle.lock").read_text(encoding="utf-8")
            )
            self.assertFalse(lock_state["active"])


if __name__ == "__main__":
    unittest.main()
