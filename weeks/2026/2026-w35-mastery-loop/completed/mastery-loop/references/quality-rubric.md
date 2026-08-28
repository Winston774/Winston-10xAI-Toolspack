# Quality Rubric

Use before packaging and after any material workflow, schema, persistence, or UI change.

## Version 3 Pass Criteria

| Dimension | Pass condition |
|---|---|
| Triggering | Description routes new self-study, tutoring, capability-audit, and misconception work to version 3 while reserving legacy v1/v2 for historical resume. |
| Goal gate | The first interaction has exactly three clickable, observable outcomes. |
| Scope gate | Before Assessment, the learner sees the mission, 3-6 areas, inclusions, exclusions, benchmark status and sources, distribution, and estimated time. |
| Batch validity | Assessment has 10-20 questions, at least two per area, a unique kernel per question, and exactly one supported answer per item; start seals the whole batch plus confirmed mission/scope/area contract, and every response repeats the batch digest. |
| Click transport | Every phase remains in one loopback tab and never requires typed option codes. |
| Pre-commit secrecy | Initial HTML and APIs expose no future item, correct status, explanation, stable option or kernel ID, misconception tag, or scoring rule. |
| Choice descriptions | Every new option has a neutral, similarly detailed subdescription that adds a boundary, prerequisite, tradeoff, or omitted factor without correctness, position, selection, grading, completeness, or no-gap cues; sealed legacy batches suppress the whole description set when any item is missing, repeats its label, or leaks. A sealed introduction, prompt, or label that exposes server-only content is blocked without rewriting evidence. |
| Immediate feedback | Every committed answer immediately shows the selected and correct explanations without showing cumulative score mid-batch. |
| Automatic record | The answer transaction writes correct and wrong responses; version 3 has no record button, recording notice, or `/record` path. |
| Progress | Question, area, completed, remaining, and semantic progress state are visible and server-derived. |
| Assessment report | Results are recomputed from immutable records and grouped by area; stable is >=80%, mixed is >=50% and <80%, and needs support is <50%, with gaps, misconceptions, traceability, confidence, and proposed slices. |
| Learning Map | The Assessment report produces the same 3-6 areas and 5-10 prerequisite-ordered slices per area, with non-decreasing difficulty. |
| Slice lineage | Every slice links to at least one valid Assessment question, routes every addressed gap, explains any prerequisite/integration role, and contains the complete slice contract. |
| Learning gates | Future nodes remain locked until prerequisites complete; every area has exactly one required checkpoint; wrong checkpoints do not block progression. |
| Learning evidence | Reading and completion affect progress only; checkpoint evidence preserves feedback exposure. |
| Review gate | Review remains unavailable until all slices and area checkpoints complete. |
| Review batch | Review has 8-15 items from the gap-plus-area formula, allocates primary scoring to the capacity-prioritized gap set, includes every overflow gap as an integrated kernel, covers every area and mission-critical correct kernel, and includes cross-area integration. |
| Review novelty | Every item preserves its primary proposition while changing scenario ID/context, fingerprint, family, prompt, all option surfaces, distractors, and correct position; trivial near-duplicates are rejected. |
| Review lineage | One primary kernel determines scoring; integrated kernels and all Assessment/Learning sources remain traceable. |
| Comparison report | The report distinguishes corrected, residual, overflow, newly exposed, reinforced, and cross-area results and schedules every unresolved/new gap three days after the immutable completion anchor. |
| Evidence hygiene | First attempts, independence, feedback timing, confidence, counterevidence, and lineage remain separate. |
| Reliability | Immutable writes are atomic; record bodies and digests are validated; validation and pre-lock loading are read-only; serve preflight validates current evidence and all reserved write targets before `ready:true`; same-selection and navigation retries are idempotent; conflicting answers return 409; invalid sequencing is rejected; the OS lock recovers after owner-process failure and stays held until live request handlers finish. |
| Security | Loopback binding, CSRF, content and body limits, path containment, escaping, CSP, clickjacking, and opaque-token protections remain active. |
| UI system | Calm / Signal tokens, one primary action, 44px targets, visible focus, semantic progress, reduced motion, and `Created by Winston` appear in every state. |
| Legacy | Existing v1/v2 specs, answers, Review seeds, validator, and single-question UI still work unchanged and are never migrated. |
| Continuity | Restart rebuilds reports and navigation from immutable records; `checkpoint.json` is disposable. |
| Artifact routing | Version 3 accepts only the canonical six spec/report paths, so `cycle.json` declarations and persisted deliveries cannot diverge. |

## Reject or Revise When

- fewer than ten or more than twenty Assessment questions are accepted;
- an area has fewer than two items or duplicate Assessment kernel IDs;
- the knowledge boundary or benchmark status is hidden before testing;
- an active batch or its confirmed mission, scope, benchmark, or area semantics mutates after start, or a response lacks the sealed whole-batch digest;
- answer correctness, explanations, lineage, stable IDs, or future questions reach the pre-commit browser;
- an introduction or option surface identifies the correct position or label, or a subdescription identifies the correct, best, complete, preferred, passing, full-credit, no-gap, or core-aligned choice, repeats its label, quotes hidden or future content, exposes a stable ID, or omits useful boundary information;
- cumulative scores interrupt the Assessment rhythm;
- version 3 displays a record button, recording notice, close-page gate, or `/record` route;
- browser-supplied counts or correctness determine progress or reports;
- area summaries hide a mission-critical failed kernel;
- an area contains fewer than five or more than ten slices, invalid prerequisites, no checkpoint, or multiple checkpoints;
- a slice has no Assessment evidence link, maps a gap without its source question, regresses in difficulty, or has a worked example without a scenario fingerprint;
- scrolling, elapsed time, or client state marks a slice complete;
- Review is generated from filenames or persisted reports without validating immutable record bodies and digests;
- Review is generated before every Learning requirement completes;
- Review count falls outside 8-15 or ignores the gap-plus-area formula;
- a Review scenario repeats or trivially rewrites an Assessment, Learning checkpoint, or worked-example context;
- a Review item changes its primary decision truth, has ambiguous primary scoring, or reuses its prompt, option label, description, or explanation surface;
- same-session reading or correction receives Transfer or Durable status;
- duplicate requests create multiple records, a conflicting answer overwrites history, reports unlock a phase without evidence recomputation, reserved write paths escape the cycle or have invalid types, or two phase writers operate concurrently;
- an invalid, stale, future, or cross-phase token advances state;
- a page omits keyboard operation, visible focus, or `Created by Winston`;
- new-cycle documentation routes to the legacy single-question workflow;
- historical v1/v2 files are rewritten or silently upgraded.
- version 3 accepts a custom or unknown artifact route.

## Automated Regression

Run:

```powershell
python -m py_compile scripts/click_choice_ui.py scripts/init_workspace.py scripts/session_core.py scripts/mastery_session_ui.py
python -m unittest discover -s tests -v
python <skill-creator>/scripts/quick_validate.py <skill>
node <impeccable>/scripts/detect.mjs --json scripts/mastery_session_ui.py
```

Verify at least:

- all existing v1/v2 compatibility and record-gate tests remain green;
- 9-item, 21-item, duplicate-ID, missing-explanation, answer-revealing, future-content, stable-ID, or empty subdescription, and insufficient-area-coverage Assessment specs are rejected before sealing;
- a sealed historical v3 question with unsafe subdescription copy resumes without spec mutation and renders labels without any subdescription;
- a 12-item mixed batch produces the expected area report;
- wrong responses persist automatically and version 3 output contains no record control or notice;
- initial HTML omits future questions, answers, explanations, stable IDs, and lineage;
- duplicate answer, timeout retry, conflicting answer, malformed evidence timestamp, stale/future token, forged/unsealed checkpoint, restart, whole-batch future-question mutation, post-start cycle-contract mutation, invalid reserved write surfaces, full Learning contract mutation, concurrent phase-lock, active-handler shutdown, and crash-recovery cases;
- 3 areas x 5 slices x 1 checkpoint with Assessment-source linkage, non-decreasing difficulty, prerequisite enforcement, and wrong-checkpoint continuation;
- Review generation is blocked before full validated Learning completion and rejects empty/tampered event files;
- 8-item Review preserves propositions and lineage while enforcing capacity-prioritized primary scoring, integrated overflow coverage, all-area/cross-area coverage, important-correct coverage, and genuinely new scenario surfaces;
- comparison report and stable three-day delayed queue are rebuilt from the final immutable answer timestamp;
- responsive, keyboard, focus, `aria-live`, semantic progress, reduced-motion, footer, CSP, and clickjacking behavior.

## Independent Forward Test

Give another agent only the skill path and a realistic mission:

```markdown
Mission: assess and teach end-to-end Agent Workflow design.
Required scope: 3 major areas and 12 defensible kernels.
Hidden misconceptions: partial output is treated as a complete handoff; publish timeout is retried without reconciliation.
Required run: scope -> 12-question Assessment with mixed results -> report
              -> 3 areas x 5+ Learning Slices and checkpoints
              -> 8+ new-scenario Review -> comparison and delayed queue.
Evidence boundary: reading is exposure; same-session correction is not Transfer.
```

The skill passes when the evaluator can create valid version 3 artifacts, finish each phase in one tab, conceal pre-commit data, persist responses without a record action, produce traceable reports, enforce Learning and Review gates, generate genuinely new Review contexts, preserve conservative evidence claims, and still resume a legacy v2 session.
