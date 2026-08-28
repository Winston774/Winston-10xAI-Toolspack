# Integrated Review Protocol

Version 3 Review converts completed Assessment and Learning evidence into one new-scenario retrieval batch. It reinforces prior errors and mission-critical ideas without repeating Assessment questions or Learning examples.

## 1. Entry Gate

Generate Review only when:

- `assessment/report.json` is complete;
- `learning/report.json` is complete and `ensure_review_ready` accepts the immutable event set;
- every required slice completion and area checkpoint response exists;
- benchmark lineage still resolves;
- no active Assessment or Learning writer owns the cycle.

Use immutable responses and reports as inputs. Do not infer gaps from browser state or memory.

## 2. Select Review Coverage

Deduplicate Assessment and Learning gaps by knowledge kernel while preserving every stable gap ID for lineage, then compute:

```text
question count = clamp(
  independent Assessment and checkpoint gap-kernel count + major area count,
  8,
  15
)
```

Allocate in this priority order:

1. wrong Assessment kernels, weighted by mission criticality and failure cost;
2. wrong formative checkpoint kernels;
3. important Assessment kernels that were correct but need deeper application;
4. cross-area combinations that test integrated judgment.

Use direct-scoring capacity in this order:

1. seed every gap-bearing area with its highest-priority gap;
2. fill remaining primary slots with Assessment gaps before checkpoint gaps;
3. within Assessment gaps, place critical gaps first;
4. reserve one primary slot for every area that has no prior gap.

When independent gaps exceed the available primary slots, include every overflow gap as an integrated kernel with complete lineage. Integrated exposure does not count as correction: keep those gap IDs unresolved and place them in delayed review. Cover every major area, include every mission-critical Assessment kernel that was answered correctly, and include at least one kernel from another area. Multiple gap records may share a primary kernel; use distinct new scenarios when the required question count needs more than one item over that kernel.

## 3. Question Lineage

Each Review question declares:

- one `primary_kernel_id` used for scoring and comparison;
- its unchanged `core_proposition`;
- zero or more `integrated_kernel_ids`;
- source Assessment and Learning item IDs;
- a new `scenario_id` and `scenario_fingerprint`;
- a question family, option set, explanations, and misconception tags.

Integrated kernels add realistic constraints. They do not blur which primary proposition determines correctness.

## 4. Novelty Contract

Preserve the primary decision truth. Change all answer surfaces:

- scenario ID, actors, constraints, artifacts, and scenario fingerprint;
- question family and demanded cognitive operation;
- prompt;
- every option ID, label, description, and explanation;
- distractor construction;
- correct-answer position.

The Review scenario ID, fingerprint, and context must differ from every Assessment scenario, Learning checkpoint, and Learning worked example. The deterministic validator also rejects trivial near-duplicates by normalized text similarity. Renaming actors, swapping nouns, or paraphrasing the original does not qualify, so the generator must still perform a semantic novelty review beyond the lexical check.

Useful transformations:

| Prior demand | Review demand | New-scenario transformation |
|---|---|---|
| recognition | critique | locate the same violation in a different workflow |
| application | sequence | order recovery actions under new constraints |
| threshold | counterevidence | identify evidence that crosses the same boundary |
| prediction | postmortem | infer the causal failure in another domain |
| compare | tradeoff | apply the same priority rule under a new cost profile |

Every option receives detailed post-commit reasoning. The correct explanation states mechanism and boundary; each wrong explanation identifies the missing condition, wrong sequence, unsafe shortcut, or overgeneralization.

Before commitment, every rewritten option description must remain neutral and supplement the label with a boundary, prerequisite, tradeoff, or omitted factor. It must not identify the correct, best, complete, or core-aligned choice.

## 5. Review Interaction

Use one Review tab for introduction, all 8-15 questions, and the report.

- Show total and per-area progress.
- Hide future questions, answers, explanations, stable IDs, and lineage before commitment.
- Commit each answer automatically and immutably.
- Show selected and correct explanations immediately.
- Continue through one primary `下一題` action.
- Do not show a record button or recording notice.

Wrong Review responses remain gaps automatically; they do not start an immediate nested loop.

## 6. Comparison Report

Rebuild the report from server-side specs and immutable records. Include:

- Assessment error -> correct Review correction;
- residual Assessment or checkpoint gaps;
- gaps reviewed through a primary kernel and overflow gaps included only as integrated constraints;
- newly exposed Review gaps;
- mission-critical concepts reinforced after initial success;
- cross-area integration results;
- evidence level, confidence, and feedback-exposure limitations;
- source question, slice, checkpoint, and Review lineage.

Schedule every residual, overflow, and newly exposed gap for an uncued review three calendar days after the immutable final Review answer. Persist that completion anchor, the due date, and the kernel list so reopening the report cannot move the schedule. End the current cycle at the report.

## 7. Evidence Rules

- Same-session new-scenario success usually supports correction or Applied evidence, depending on cognitive demand.
- Transfer requires a genuine unseen structural variant, no cue, independent commitment, and sufficient spacing.
- Durable requires a meaningful delayed uncued success.
- A report comparison never erases the original miss; append correction evidence through lineage.

## 8. Legacy Version 2 Review

Historical version 2 sessions keep their original behavior:

- enter from a learner-created immutable `review-records/<question-id>.json` seed;
- preserve `knowledge_kernel_id`, `core_proposition`, `scenario_id`, and `scenario_context`;
- change question family, prompt, every option ID and wording, distractors, and correct position;
- require the legacy record button after a wrong response.

Use `scripts/click_choice_ui.py` for that path. Do not apply the version 3 new-scenario contract to historical specs and do not migrate their records.
