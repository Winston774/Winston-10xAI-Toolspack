# Evidence-Linked Learning Map

Generate Learning only from a complete version 3 Assessment report. The result is a prerequisite-ordered knowledge map, not a loose collection of explanations.

## 1. Map Construction

Preserve the Assessment's 3-6 major areas. For each area:

```text
slice count = min(5 + distinct independent gap count, 10)
```

A gap is deduplicated by primary knowledge kernel. Repeated misses may raise priority but do not inflate the slice count. With 3-6 areas, the complete path contains roughly 15-60 slices.

Build a directed prerequisite graph and keep difficulty non-decreasing inside each area:

- start with foundations and shared vocabulary;
- follow with mechanisms and boundaries;
- then representative applications, tradeoffs, and failure handling;
- end with integration and one formative area checkpoint.

Reject a path with missing prerequisites, cycles, fewer than five or more than ten slices in an area, or an area without exactly one checkpoint.

## 2. Slice Contract

Each slice is stored separately and contains:

1. stable `slice_id`, `area_id`, and positive integer `order`;
2. title, difficulty, and prerequisite slice IDs;
3. one observable `learning_objective`;
4. one or more `assessment_question_ids`, plus `addresses_gap_ids` where applicable, linking relevant correct and wrong evidence;
5. the minimum core explanation;
6. mechanism, boundary, and failure condition;
7. one worked example with a unique scenario fingerprint;
8. common mistakes derived from actual misconceptions where available;
9. a concise summary;
10. authoritative sources or a visible provisional marker.

Explain enough to support the next performance. Avoid generic motivation, repeated definitions, and content unrelated to the confirmed mission.

## 3. Mapping Assessment Evidence

Every proposed gap in the Assessment report must route to at least one slice, and the same slice must name that gap's source Assessment question. Every slice must name at least one related Assessment question and explain its role through one of:

- a wrong Assessment kernel;
- a prerequisite for a wrong kernel;
- a mission-critical correct kernel that needs deeper application;
- an integration dependency shared across areas.

Show the learner these links in plain language, such as `補強：評估第 4 題` or `鞏固：評估第 7 題`. Do not label a learner globally from a single miss.

Correct Assessment items may shorten explanation emphasis, but they do not remove required foundational slices. Wrong items raise the linked slice's visual priority.

## 4. Progression and Access

- Show the full map structure, current area, completion counts, and prerequisite connections.
- Completed slices remain freely readable.
- The first incomplete slice whose prerequisites are complete is the active node.
- Locked downstream nodes reveal only title, position, and unmet prerequisite.
- A completion action writes one immutable event. Refresh and duplicate requests return the existing event.
- Do not infer completion from scrolling, elapsed time, or browser state.

Learning progress is informational. Completing a slice does not promote mastery.

## 5. Formative Area Checkpoint

After all slices in an area complete, unlock exactly one checkpoint.

- Use 3-5 balanced clickable options and one correct answer; each subdescription neutrally adds a boundary, prerequisite, tradeoff, or omitted factor.
- Test a representative decision that combines the area's most important kernels.
- Do not copy an Assessment prompt or a worked example.
- Persist the response automatically and reveal explanations immediately.
- A wrong response becomes a Learning gap for Review generation.
- The learner must answer the checkpoint, but correctness does not block the next area.

Record checkpoint independence as `feedback_exposed` when its kernel was taught in the same phase. Treat it as correction or application evidence, never clean baseline evidence.

## 6. Learning Completion and Report

Learning completes only when:

- every required slice has one completion event;
- every area checkpoint has one immutable response;
- all event and response IDs resolve to the immutable path;
- no prerequisite or phase lock violation remains.

Build `learning/report.json` from the path, slice completion events, and checkpoint responses. Include:

- completion by area;
- Assessment gaps covered by each slice;
- checkpoint strengths and misses;
- kernels eligible for Review;
- evidence limitations;
- the complete/missing slice and checkpoint state used by the Review gate.

Only a complete Learning state accepted by `ensure_review_ready` permits Review generation.

## 7. Content and UI Quality

- Use concise sections, semantic headings, readable line length, and clear mechanism diagrams only when they materially help.
- Cite factual claims near the claim.
- Keep media optional and local-first.
- Use the Calm / Signal system, keyboard access, visible focus, responsive layout, reduced motion, and `Created by Winston`.
- Keep the learner in one Learning tab from map introduction through the report.

## 8. Evidence Boundary

Reading and completion show exposure. A checkpoint can demonstrate narrow correction or application depending on task quality and independence. Transfer requires an unseen structural variant; Durable requires a delayed uncued check.
