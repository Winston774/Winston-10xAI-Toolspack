# Version 3 Learning Workspace

The schemas in this reference match `scripts/session_core.py`. Keep specs and learner evidence immutable; keep navigation and derived reports replaceable and reconstructable.

## Directory Shape

```text
learning-workspace/
└─ mastery-sessions/
   └─ <cycle-id>/
      ├─ cycle.json
      ├─ checkpoint.json
      ├─ assessment/
      │  ├─ spec.json
      │  ├─ batch-manifest.json
      │  ├─ responses/
      │  │  └─ <question-id>.json
      │  └─ report.json
      ├─ learning/
      │  ├─ path.json
      │  ├─ slices/
      │  │  └─ <slice-id>.json
      │  ├─ events/
      │  │  ├─ slice_completed.<slice-id>.json
      │  │  └─ checkpoint_answered.<area-id>.json
      │  └─ report.json
      └─ review/
         ├─ spec.json
         ├─ batch-manifest.json
         ├─ responses/
         │  └─ <question-id>.json
         └─ report.json
```

Version 3 uses the six fixed relative artifact routes shown below. Omitted keys normalize to these defaults; custom or unknown routes are rejected so declared delivery paths cannot diverge from persisted reports. Resolve and contain every path before access.

## Cycle Manifest

`cycle.json` supplies the canonical mission, scope, areas, and artifact routing. The JSON below abbreviates the `areas` array; a valid manifest contains 3-6 entries:

```json
{
  "schema_version": 3,
  "cycle_id": "agent-workflow-20260827",
  "mission": {
    "intent_id": "review_teach",
    "ultimate_outcome": "Review and teach an end-to-end Agent Workflow.",
    "audience": "Workflow designers"
  },
  "knowledge_scope": {
    "title": "Agent Workflow design",
    "direction": "Design, recover, and verify an end-to-end workflow.",
    "includes": ["handoffs", "recovery", "acceptance evidence"],
    "excludes": ["provider-specific pricing"],
    "benchmark_status": "verified",
    "sources": ["authoritative-source-id"]
  },
  "areas": [
    {
      "area_id": "handoffs",
      "title": "Handoff contracts",
      "description": "Typed artifacts, validation, and failure behavior.",
      "weight": 8,
      "failure_cost": 9,
      "uncertainty": 6
    }
  ],
  "artifacts": {
    "assessment_spec": "assessment/spec.json",
    "assessment_report": "assessment/report.json",
    "learning_path": "learning/path.json",
    "learning_report": "learning/report.json",
    "review_spec": "review/spec.json",
    "review_report": "review/report.json"
  }
}
```

Validation requires 3-6 unique `area_id` values. `mission.intent_id` is exactly one of `end_to_end_delivery`, `diagnose_improve`, or `review_teach`. `benchmark_status` is `verified`, `partially_verified`, or `provisional`; verified scope requires at least one source. `weight`, `failure_cost`, and `uncertainty` are numbers from 0 to 10.

## Assessment Spec

`assessment/spec.json` is sealed before the learner enters question 1. `batch-manifest.json` stores the complete normalized spec digest, the confirmed cycle-contract digest, and ordered question IDs; every response repeats the batch digest. The cycle contract covers mission, knowledge scope, and area semantics. Changing the outcome, scope, benchmark, area meaning, current question, or future question after start invalidates the batch. The JSON below shows one representative question; a valid batch contains 10-20 complete questions and 3-5 complete options per question:

```json
{
  "schema_version": 3,
  "phase": "assessment",
  "cycle_id": "agent-workflow-20260827",
  "title": "Agent Workflow Assessment",
  "instructions": "Choose the best action for each bounded scenario.",
  "estimated_minutes": 20,
  "questions": [
    {
      "question_id": "assessment-q01",
      "area_id": "handoffs",
      "concept_id": "handoff-contract",
      "knowledge_kernel_id": "handoff.explicit-assets",
      "core_proposition": "A handoff must make required artifacts and validation explicit.",
      "scenario_id": "content-pipeline",
      "scenario_context": "A publisher receives text but no required image asset.",
      "question_family": "application",
      "title": "Missing handoff artifact",
      "prompt": "What should happen before publishing?",
      "sources": ["authoritative-source-id"],
      "options": [
        {
          "id": "block-until-verified",
          "label": "Block and validate the contract",
          "description": "Applies at the pre-publication handoff boundary; post-publication monitoring remains outside this action.",
          "explanation": "The required asset is part of the delivery contract.",
          "misconception_tag": ""
        }
      ],
      "correct_option_id": "block-until-verified",
      "importance": 9
    }
  ]
}
```

The core requires every question to carry at least one benchmark source and every wrong option to carry a non-empty misconception tag. A correct option may use an empty tag. The core computes `scenario_fingerprint` and a question digest from trusted server-side content.

Assessment validation requires:

- 10-20 questions;
- the same 3-6 areas declared by `cycle.json`, each used at least twice;
- globally unique question IDs and `knowledge_kernel_id` values;
- 3-5 unique option IDs per question and exactly one `correct_option_id`;
- one non-empty, neutral description per option that adds a boundary, prerequisite, tradeoff, or omitted factor without correctness, selection, grading, completeness, or no-gap cues and without repeating the label; introductions, labels, and descriptions cannot quote hidden explanations, future question or option surfaces, stable IDs, or misconception tags;
- an explanation for every option;
- supported question family, bounded scenario, and importance from 0 to 10.

The initial browser receives only current visible copy, progress, and opaque tokens.

## Immutable Assessment and Review Response

```json
{
  "schema_version": 3,
  "record_type": "question_response",
  "phase": "assessment",
  "cycle_id": "agent-workflow-20260827",
  "question_id": "assessment-q01",
  "batch_spec_digest": "sha256...",
  "question_digest": "sha256...",
  "area_id": "handoffs",
  "concept_id": "handoff-contract",
  "knowledge_kernel_id": "handoff.explicit-assets",
  "primary_kernel_id": null,
  "integrated_kernel_ids": [],
  "scenario_id": "content-pipeline",
  "scenario_fingerprint": "sha256...",
  "question_family": "application",
  "lineage": {},
  "displayed_option_order": ["...", "...", "..."],
  "selected_option_id": "...",
  "selected_misconception_tag": "...",
  "correct_option_id": "block-until-verified",
  "is_correct": false,
  "independence": "independent",
  "feedback_exposed": false,
  "feedback_timing": "immediate_after_commit",
  "request_id": "opaque-idempotency-id",
  "answered_at": "RFC-3339 timestamp"
}
```

Assessment records use `independent`; Review records use `feedback_exposed`. Correctness is recomputed against the immutable spec and is never supplied by the browser. For Review, `knowledge_kernel_id` aliases `primary_kernel_id`, and lineage contains source Assessment, slice, and checkpoint IDs.

Write one response per question. Repeating the same selection returns the existing record even under a new `request_id`. A different later selection returns HTTP 409 and never overwrites history. Missing or mismatched batch manifests and response-level batch digests invalidate progress and report generation.

## Assessment Report

`assessment/report.json` is rebuilt from the validated spec and response files. It contains batch completion counts, question results, gaps, critical gaps, evidence limitations, and per-area:

- answered, total, correct, and accuracy;
- `stable_signal` / `穩定訊號` at accuracy >= 0.80;
- `mixed_signal` / `混合訊號` at accuracy >= 0.50 and < 0.80;
- `needs_support` / `待補強` below 0.50;
- gap and critical-gap IDs;
- `suggested_slice_count = min(10, 5 + distinct area gap count)`;
- confidence.

A wrong item creates a stable gap ID such as `assessment.assessment-q01`. Importance 8 or above marks the gap critical. Reports may be atomically regenerated; evidence files remain unchanged.

## Learning Path

`learning/path.json` embeds the complete trusted checkpoint question for each area. The example abbreviates the full 3-6 area array:

```json
{
  "schema_version": 3,
  "phase": "learning",
  "cycle_id": "agent-workflow-20260827",
  "title": "Agent Workflow Learning Map",
  "areas": [
    {
      "area_id": "handoffs",
      "title": "Handoff contracts",
      "slice_ids": [
        "handoffs-01",
        "handoffs-02",
        "handoffs-03",
        "handoffs-04",
        "handoffs-05"
      ],
      "checkpoint": {
        "question_id": "handoffs-checkpoint",
        "area_id": "handoffs",
        "concept_id": "handoff-integration",
        "knowledge_kernel_id": "handoff.integrated-check",
        "core_proposition": "Required artifacts must pass their handoff contract.",
        "scenario_id": "handoff-checkpoint",
        "scenario_context": "A new workflow hands off several required artifacts.",
        "question_family": "critique",
        "title": "Area checkpoint",
        "prompt": "Which defect blocks continuation?",
        "sources": ["authoritative-source-id"],
        "options": ["3-5 complete option objects"],
        "correct_option_id": "one-option-id",
        "importance": 8
      }
    }
  ]
}
```

Learning areas must exactly match `cycle.json`. Slice IDs are globally unique. Each area has 5-10 slices and one checkpoint belonging to that area; checkpoint kernel IDs and question IDs are globally unique and cannot collide with Assessment kernel or question IDs. Every slice names at least one Assessment question, and every link resolves to a real Assessment question ID. The path becomes immutable after its first Learning event.

## Learning Slice

Each `learning/slices/<slice-id>.json` uses:

```json
{
  "schema_version": 3,
  "slice_id": "handoffs-01",
  "area_id": "handoffs",
  "title": "Explicit handoff assets",
  "order": 1,
  "difficulty": "foundation",
  "prerequisites": [],
  "learning_objective": "Identify every artifact required by a handoff.",
  "assessment_question_ids": ["assessment-q01"],
  "addresses_gap_ids": ["assessment.assessment-q01"],
  "core_explanation": "...",
  "mechanism": "...",
  "boundaries": ["..."],
  "worked_example": {
    "scenario_id": "handoff-example-01",
    "scenario_context": "A different bounded example.",
    "walkthrough": "..."
  },
  "common_mistakes": ["..."],
  "key_takeaways": ["..."],
  "sources": ["authoritative-source-id"]
}
```

`difficulty` is `foundation`, `core`, or `advanced` and must be non-decreasing inside each area. The core derives the worked-example fingerprint. Slice order must match its position in the area's `slice_ids`; every prerequisite must resolve to an earlier slice. Every Assessment gap must appear in at least one `addresses_gap_ids` entry, and that slice must also include the gap's `source_question_id` in `assessment_question_ids`. When an Assessment report is supplied, each area's slice count must equal its `suggested_slice_count`.

## Learning Events and Report

Slice completion is write-once:

```json
{
  "schema_version": 3,
  "record_type": "learning_event",
  "event_type": "slice_completed",
  "cycle_id": "agent-workflow-20260827",
  "slice_id": "handoffs-01",
  "area_id": "handoffs",
  "learning_contract_digest": "sha256...",
  "slice_digest": "sha256...",
  "request_id": "opaque-idempotency-id",
  "completed_at": "RFC-3339 timestamp",
  "mastery_effect": "progress_only"
}
```

A slice event is accepted only when it is the next node in the validated event sequence and every prerequisite completes. The slice digest binds the event to that normalized Slice; `learning_contract_digest` binds it to the complete path plus all ordered Slice files, so changing unfinished content after the first event invalidates the phase. The area checkpoint unlocks only after all area slices complete. Its `checkpoint_answered.<area-id>.json` event stores the same contract digest plus the trusted question digest, kernel, option order, selection, misconception, correctness, immediate-feedback timing, request ID, and timestamp. Empty, malformed, unexpected, out-of-order, or digest-mismatched event files are rejected.

`learning/report.json` contains:

- complete, completed/missing slice IDs and counts;
- completed/missing checkpoint area IDs and counts;
- checkpoint results and Learning gap records;
- `mastery_effect: "learning_progress_only"`;
- generation time.

`ensure_review_ready` validates every event body and permits Review only when no slice or checkpoint is missing. Learning and Review loaders rebuild upstream reports from the immutable specs, responses, and validated events; persisted report files never unlock a later phase by themselves.

## Review Spec

`review/spec.json` uses the Assessment batch header plus 8-15 Review questions. The example shows one representative item:

```json
{
  "schema_version": 3,
  "phase": "review",
  "cycle_id": "agent-workflow-20260827",
  "title": "Integrated Review",
  "instructions": "Apply the learned kernels in new scenarios.",
  "questions": [
    {
      "question_id": "review-q01",
      "area_id": "handoffs",
      "concept_id": "handoff-contract",
      "primary_kernel_id": "handoff.explicit-assets",
      "integrated_kernel_ids": ["recovery.reconcile-state"],
      "source_question_id": "assessment-q01",
      "core_proposition": "Copy the source proposition exactly.",
      "scenario_id": "refund-webhook",
      "scenario_context": "A new domain with the same decision structure.",
      "question_family": "sequence",
      "title": "New-scenario review",
      "prompt": "Which sequence is valid?",
      "sources": ["authoritative-source-id"],
      "options": ["3-5 complete new option objects"],
      "correct_option_id": "new-option-id",
      "importance": 9,
      "lineage": {
        "assessment_question_ids": ["assessment-q01"],
        "learning_slice_ids": ["handoffs-01"],
        "learning_checkpoint_ids": []
      }
    }
  ]
}
```

The core derives scenario fingerprints and validates:

- question count equals `clamp(distinct Assessment/Learning gap-kernel count + area count, 8, 15)`;
- capacity-prioritized gap kernels appear as primary scoring kernels: seed each gap-bearing area from its highest-priority gap, then fill with Assessment gaps before checkpoint gaps and critical Assessment gaps before other Assessment gaps;
- every overflow gap beyond direct-scoring capacity appears as an integrated kernel with complete lineage and remains unresolved for delayed review;
- `primary_kernel_id`, `area_id`, and `source_question_id` agree and preserve the exact core proposition;
- all integrated kernels resolve;
- every major area is covered, at least one question integrates a kernel from another area, and every mission-critical correct Assessment kernel is included;
- scenario ID and fingerprint are new, and deterministic near-duplicate screening rejects trivial rewrites of prior contexts;
- question family, normalized prompt, all option IDs, labels, descriptions, explanations, and correct-answer position differ from the source;
- Review fingerprints are unique and do not match any Assessment scenario, Learning checkpoint, or Learning worked example;
- lineage includes the primary source plus the Assessment or checkpoint source for every integrated kernel, and names only known Assessment, Slice, and checkpoint IDs.

## Review Report

`review/report.json` is derived from the Review spec, responses, Assessment report, and Learning report. It contains:

- question results with primary/integrated kernels and prior gap IDs;
- `corrected_gap_ids`;
- `remaining_gap_ids`;
- `directly_reviewed_gap_ids` and `not_directly_reviewed_gap_ids`;
- `new_errors`;
- `reinforced_concepts`;
- `delayed_review` entries for residual and new gaps;
- missing question IDs and completion counts.

Each delayed entry uses the gap ID, `due_date` three calendar days after the immutable final Review response timestamp, and `mode: "uncued"`. `completion_anchor` records that timestamp, so report regeneration on a later day cannot move the due date. The report closes the current cycle; it does not start an immediate nested loop.

## Checkpoint, Persistence, and Locking

`checkpoint.json` is reconstructable navigation only, for example:

```json
{
  "schema_version": 3,
  "cycle_id": "agent-workflow-20260827",
  "phase": "assessment",
  "screen": "feedback",
  "index": 0,
  "subject_id": "assessment-q01",
  "updated_at": "RFC-3339 timestamp",
  "evidence_source": false
}
```

- Treat checkpoint as a cache and rebuild it from specs and immutable records when stale, missing, or corrupt.
- Acquire the cycle-wide operating-system lock through `.cycle.lock` before serving any writable phase; record active/released state and reject every second writer. OS lock ownership is released automatically after process failure, so a restart can safely recover without deleting lock evidence. The server joins every live request handler before releasing this lock.
- Publish immutable evidence once through flushed, synced, atomic same-directory operations that never replace an existing target.
- Publish the batch manifest once; replace only derived reports and checkpoint through a flushed same-directory temporary file and atomic rename.
- Before `ready:true`, require `responses/` or `events/` to be a contained directory or absent, and require manifest, checkpoint, report, and lock targets to be contained regular files or absent. Reject symbolic-link escapes, traversal, out-of-cycle artifact paths, stale/future/cross-phase tokens, and spec/record digest mismatches.
- Treat an unsealed question checkpoint as invalid. If a manifest was sealed before a crash and no answer exists yet, resume at question 1 without resealing or exposing a future item.
- Recompute progress and reports after restart from immutable records. CLI validation and phase loading keep recomputed upstream reports in memory; a server validates current phase evidence after acquiring the lock and before printing `ready:true`. Persist a report only while the cycle lock is held at its phase-completion transaction.

## Legacy Compatibility

Keep the existing root-level version 1 and 2 workspace readable:

```text
MISSION.md
KNOWLEDGE-MAP.md
MASTERY.md
choice-sessions/
review-records/
assessment-records/
learning-records/
lessons/
```

- Missing `schema_version` remains version 1.
- Existing version 2 specs, answers, and learner-created Review seeds remain unchanged.
- Use `scripts/click_choice_ui.py` for legacy validation and serving.
- Never silently import or rewrite legacy evidence inside a version 3 cycle.
