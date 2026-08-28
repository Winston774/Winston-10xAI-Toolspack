# Batch Assessment Protocol

Use this protocol to define the scope, generate one complete Assessment batch, and produce its report. Adaptation happens before the batch and again at phase boundaries; never mutate an active batch from interim answers.

## 1. Lock Outcome and Scope

Start with exactly three clickable, topic-specific outcomes: end-to-end delivery, diagnosis and improvement, or review and teaching. Persist the selected stable intent ID and derive an observable ultimate outcome.

Before any scored item, show and confirm:

- the ultimate outcome and learner audience;
- 3-6 major knowledge areas;
- included and excluded topics;
- expected performance and failure cost;
- benchmark status and sources;
- question distribution, total count, and estimated time;
- known evidence limits and accommodations.

Use supplied artifacts and authoritative materials before requesting extra intake. Mark the benchmark `verified`, `partially_verified`, or `provisional`. Defer scoring where no defensible answer exists.

## 2. Build the Benchmark Map

Create one row for each candidate kernel:

```markdown
| Area | Kernel ID | Core proposition | Why critical | Required level | Prerequisite | Failure signal | Source |
|---|---|---|---|---|---|---|---|
```

Choose 3-6 coherent areas. If the confirmed scope cannot support at least ten distinct, benchmark-backed propositions, block Assessment and return to scope expansion.

## 3. Compose the Batch

Generate all 10-20 questions before serving the phase.

- Give every area at least two questions.
- Use one distinct `knowledge_kernel_id` per question, so immediate feedback cannot contaminate another baseline item in the same batch.
- Allocate remaining questions by mission criticality, uncertainty, failure cost, prerequisite leverage, and staleness.
- Order from orientation to representative decisions while avoiding clusters whose wording reveals adjacent answers.
- Seal the confirmed mission/scope/area contract, complete normalized spec, and ordered question IDs before question 1 appears. Store the batch digest in every response and reject any cycle-contract, current-question, or future-question mutation after start.

Use 3-5 options and exactly one benchmark-supported correct answer. Useful question families include recognition, mechanism, prediction, application, critique, comparison, threshold, tradeoff, counterevidence, postmortem, calibration, and sequence. Transfer belongs in Review or a later uncued check.

For each question, define:

- stable area, concept, kernel, question, and scenario IDs;
- one core proposition and bounded scenario;
- one question family;
- one correct option and detailed explanation;
- plausible distractors with explanations and misconception tags;
- a neutral subdescription for every option that states a boundary, prerequisite, tradeoff, or omitted factor without signalling correctness;
- lineage to the benchmark source.

Balance option grammar, length, specificity, tone, and subdescription detail. Reserve correctness language and complete reasoning for post-commit explanations. Include `insufficient evidence; inspect X first` when action is otherwise unjustified.

## 4. Run Without Rhythm Breaks

The Assessment introduction presents the confirmed scope. The question view shows:

- question `n / N`;
- current area;
- completed and remaining counts;
- a semantic progress element.

Before commitment, expose only visible copy and opaque option tokens. After commitment:

1. persist the immutable response in the same transaction;
2. lock the selection;
3. show the selected answer and explanation;
4. show the correct answer and explanation;
5. offer one primary `下一題` action.

Do not show a record button, a recording notice, or cumulative scores. Wrong and correct answers follow the same continuation rhythm. Refresh resumes the committed feedback state until the learner advances.

## 5. Build the Assessment Report

Recompute the report from server-side spec plus immutable response files. Never trust browser totals.

For each area include:

- answered and correct counts;
- `穩定訊號` when area accuracy is at least 80%;
- `混合訊號` when area accuracy is at least 50% and below 80%;
- `待補強` when area accuracy is below 50%;
- kernel-level gaps and misconception tags;
- question-level traceability;
- proposed Learning Slice targets;
- benchmark limitations, evidence level, and confidence.

Keep the status descriptive. Concept-level evidence and mission-critical blockers remain visible even when an area summary looks strong.

The report also lists batch-wide strengths, unresolved prerequisites, open benchmark gaps, and the exact inputs for Learning generation.

## 6. Phase Boundary

Return to Codex only after the report exists. Build Learning from the completed report recomputed from immutable evidence, never from remembered browser state or an unverified report file. If the batch is incomplete, resume the same Assessment tab and immutable spec.

Pause when benchmark gaps block fair scoring, fewer than ten distinct kernels exist, tool friction or fatigue distorts evidence, or the learner reaches the time box. Persist the next action without generating a partial Learning Map.
