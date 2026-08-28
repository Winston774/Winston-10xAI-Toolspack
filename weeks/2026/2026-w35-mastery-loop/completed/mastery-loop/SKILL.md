---
name: mastery-loop
description: Run a stateful, click-first mastery system with a scoped 10-20 question batch assessment, an evidence-linked knowledge map, and an 8-15 question new-scenario review. Use for self-study, tutoring, capability audits, misconception diagnosis, or durable learning; use the legacy path only to resume historical v1/v2 single-question sessions.
---

# Mastery Loop

## Outcome

Run one evidence-aware learning cycle:

```text
three goal choices -> scope and benchmark -> 10-20 question Assessment
                   -> assessment report -> 3-6 area Learning Map
                   -> 5-10 slices per area + area checkpoint
                   -> 8-15 question new-scenario Review
                   -> comparison report + delayed review
```

Judge demonstrated performance. Confidence, credentials, fluency, reading completion, and exposure are context, not mastery evidence.

## Default and Legacy Paths

- Use **version 3** for every new cycle. Each phase runs continuously in one loopback browser tab through `scripts/mastery_session_ui.py`.
- Use `scripts/click_choice_ui.py` for a pre-cycle goal/confirmation gate only when native clickable controls are unavailable, and to resume historical version 1 or 2 single-question sessions. Do not migrate or rewrite legacy specs, answers, or Review records.
- A manual `記錄這個錯誤` action belongs only to the legacy path. Version 3 saves every committed answer atomically and never shows a record button or recording notice.

## Mouse-First Contract

Every learner-facing decision prefers a clickable control. Do not ask the learner to type option codes when a click path is available. Scored controls must not recommend, preselect, reorder unpredictably, or leak correctness.

Read [references/choice-interface.md](references/choice-interface.md) before serving the first goal, Assessment, Learning, or Review page.

## Start or Resume a Cycle

1. Inspect `mastery-sessions/` for an active version 3 cycle and resume it from immutable records plus `checkpoint.json`.
2. If no active cycle exists, present exactly three topic-specific outcomes:
   - end-to-end delivery;
   - diagnosis and improvement;
   - review and teaching.
3. Derive one observable ultimate outcome. Confirm, adjust scope, or pause through clickable actions.
4. Define the knowledge boundary before testing: 3-6 major areas, included and excluded topics, benchmark status and sources, required performance, and evidence limits.
5. Create files only when persistent learning work is in scope. Do not create a workspace for chat-only guidance.

Read [references/workspace-schema.md](references/workspace-schema.md) before creating or changing cycle state.

## Version 3 Workflow

### 1. Assessment / 評估

Generate the complete batch before the phase starts:

- 10-20 questions across 3-6 major areas;
- at least two questions per area;
- one distinct `knowledge_kernel_id` per question;
- 3-5 balanced clickable options and exactly one benchmark-supported answer; every pre-commit subdescription adds a neutral boundary, prerequisite, tradeoff, or omitted factor without evaluating correctness;
- an explanation for every option and a misconception tag for each plausible wrong answer.

The introduction shows the outcome, scope, exclusions, benchmark status and sources, area distribution, question count, and estimated time. During the batch, show question and area progress. After each commitment, lock the answer, save it automatically, show the selected and correct answers with their explanations, and offer one primary `下一題` action. Do not show cumulative scoring until the batch report.

The report is rebuilt from server-side specs and immutable responses. Aggregate by area, show `穩定訊號`, `混合訊號`, or `待補強`, and trace every gap and misconception to source questions and proposed Learning Slices.

Read [references/adaptive-interview.md](references/adaptive-interview.md) before building the scope, batch, or Assessment report.

### 2. Learning / 學習

Generate the Learning Map from the completed Assessment report:

- preserve the same 3-6 areas;
- create `min(5 + independent gap count, 10)` slices per area;
- order slices by prerequisites and increasing complexity;
- link each slice to relevant correct and wrong Assessment responses;
- finish every area with one required formative checkpoint.

Each slice states its map position, prerequisite, difficulty, observable outcome, core mechanism and boundary, worked example, common mistakes, summary, and sources. Completed slices remain available for review; locked downstream slices expose only their title and position. A wrong area checkpoint is saved and explained but does not block the next area.

Reading completion updates progress only. Generate Review only after all slices and all area checkpoints are complete.

Read [references/lesson-design.md](references/lesson-design.md) before producing the Learning Map, slices, checkpoints, or Learning report.

### 3. Review / 複習

Generate one integrated batch after Learning completes:

```text
question count = clamp(unique Assessment/Learning gap kernels + area count, 8, 15)
```

Prioritize Assessment mistakes, then checkpoint mistakes, mission-critical correct concepts, and cross-area integration. Each question has one `primary_kernel_id` for scoring and may name `integrated_kernel_ids`.

Preserve the primary core proposition while changing the scenario, question family, prompt, option IDs and wording, distractors, and correct-answer position. Within the 15-question cap, assign direct primary scoring first to an Assessment gap in every gap-bearing area, then to remaining Assessment gaps by criticality, and then to checkpoint gaps. Every overflow gap must still appear as an integrated kernel with lineage, remain unresolved by direct scoring, and enter delayed review. The batch must cover every area, at least one cross-area integration, and every mission-critical correct kernel. Reject exact or trivial near-duplicate Assessment and Learning scenarios. Use the same continuous progress, immediate explanation, and automatic persistence behavior as Assessment.

The final report compares Assessment and Review, separates corrected, residual, and newly exposed gaps, lists reinforced concepts, and schedules every residual or newly exposed gap for an uncued check three days later. End the current cycle after the report; do not start an unbounded immediate loop.

Read [references/review-loop.md](references/review-loop.md) before generating the Review batch or comparison report.

## Evidence and State

- Preserve first-attempt evidence before feedback.
- Label later same-kernel work `feedback_exposed`, `hinted`, `corrected`, or `independent` accurately.
- A correct choice supports at most Fragile by itself; reading a slice supports no promotion.
- End-to-end capability requires simulation or artifact evidence.
- Transfer requires an uncued unseen structural variant; Durable requires meaningful delay.
- Keep mission-critical blockers visible instead of hiding them in an average.

Read [references/mastery-model.md](references/mastery-model.md) before changing evidence levels, confidence, or mastery claims.

## Public CLI

Validate a version 3 phase before serving it:

```powershell
python scripts/mastery_session_ui.py validate `
  --workspace <workspace> `
  --cycle mastery-sessions/<cycle-id> `
  --phase assessment|learning|review

python scripts/mastery_session_ui.py serve `
  --workspace <workspace> `
  --cycle mastery-sessions/<cycle-id> `
  --phase assessment|learning|review `
  --port 0
```

The server owns sequencing, scoring, reports, and resume state. `validate` is read-only. Assessment start seals the confirmed mission, scope, areas, and complete question batch. A writable server preflights contained write targets, acquires the cycle lock before any persisted report or checkpoint change, and joins active requests before releasing it. Never derive state from browser-supplied counts or correctness.

## Boundaries and Stop Conditions

- Defer scoring when no defensible benchmark-supported answer exists.
- Verify current, niche, public-facing, legal, medical, financial, or safety-sensitive claims with current authoritative sources.
- Pause when scope is incomplete, fewer than ten defensible kernels exist, a required artifact is missing, fatigue distorts evidence, the learner asks to stop, or the time box ends.
- Preserve mouse-first operation, accessibility, respectful language, and the learner's authorization boundaries.
- Do not infer intelligence, employability, personality, or general competence.
- Formal certification requires validated instruments, identity controls, qualified assessors, and domain governance.

## Completion Criteria

A version 3 cycle is complete when the scope and benchmark are visible, Assessment contains 10-20 valid unique-kernel questions, every commitment is saved with immediate explanation, the Assessment report drives a complete Learning Map, all slices and area checkpoints finish, Review contains 8-15 valid new-scenario questions, the comparison report and delayed checks are persisted, and all mastery claims stay inside the tested mission.

Before materially revising, validating, or packaging the skill, read [references/quality-rubric.md](references/quality-rubric.md).
