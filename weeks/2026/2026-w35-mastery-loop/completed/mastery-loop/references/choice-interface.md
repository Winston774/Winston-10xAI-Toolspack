# Click-First Phase Interface

Use this contract for goal selection and all version 3 Assessment, Learning, and Review pages.

## Transport

1. A native clickable control is acceptable for the three-goal gate when it returns stable IDs and does not mark a preferred answer.
2. Use `scripts/mastery_session_ui.py` for every version 3 phase. One phase owns one loopback browser tab from its introduction through its report.
3. When native controls are unavailable before a cycle exists, use `scripts/click_choice_ui.py` for the three-goal gate and its confirmation; navigate the same browser tab to each result. The same script also resumes historical version 1 or 2 single-question sessions.
4. If neither click transport is available, explain the capability limit and pause. Do not request typed option codes.

## Goal Gate

The first interaction contains exactly three domain-adapted choices:

| Stable ID | Intent | Observable outcome |
|---|---|---|
| `end_to_end_delivery` | End-to-end delivery | Independently produce and verify a complete result |
| `diagnose_improve` | Diagnosis and improvement | Find failures, recover safely, and improve the workflow |
| `review_teach` | Review and teaching | Evaluate quality, define standards, or teach the capability |

After selection, show the derived outcome and clickable `確認目標`, `調整範圍`, and `暫停` actions. The Assessment introduction must then show the confirmed knowledge boundary and benchmark.

## Phase State Machines

```text
Assessment:
intro -> question -> committed feedback -> next question -> report

Learning:
map -> available slice -> completion -> next slice
    -> area checkpoint -> checkpoint feedback -> map -> report

Review:
intro -> question -> committed feedback -> next question -> comparison report
```

Keep one primary action per state. `下一題`, `完成 Slice`, and `返回知識地圖` advance only through valid server state. A refresh restores the last committed feedback or current slice; it never silently advances.

## Scored Question Contract

Each question contains 3-5 mutually exclusive choices and exactly one benchmark-supported answer.

Build in this order:

1. state the core proposition, scenario boundary, best answer, and source;
2. explain why the best answer satisfies the mechanism and boundary;
3. add misconception, partial-truth, wrong-boundary, wrong-sequence, missing-evidence, or unsafe-shortcut distractors;
4. explain precisely why each distractor fails;
5. give every option a neutral subdescription that adds its boundary, prerequisite, tradeoff, or omitted factor;
6. balance wording and rotate the correct-answer position;
7. store stable IDs and correctness server-side.

The subdescription supplements the option label before commitment. Use the same tone and level of detail for every option. Do not call an option correct, best, preferred, complete, aligned, passing, or full-credit; do not imply that every requirement is satisfied or that no gap remains. Do not quote hidden core propositions, post-commit explanations, future question content, stable IDs, or misconception tags. Keep correctness and full reasoning inside the post-commit explanation.

- Leaking: `符合這一題的核心命題。`
- Neutral: `只說明染色體數恢復；尚未涵蓋重組與獨立分配。`

If one description is missing, repeats its label, or contains a correctness cue in a sealed historical v3 batch, suppress every description for that question so the choice surface remains balanced. Do not mutate the sealed spec or its evidence.

If an introduction, title, scenario, prompt, or option label exposes an answer position, correct label, explanation, core proposition, future content, or stable internal token, refuse to serve that scored surface and return to Codex for a new phase. Those fields cannot be hidden while preserving an answerable question; keep all existing evidence unchanged.

Before commitment, browser HTML and JSON may contain only the current visible prompt, visible option text, progress, and opaque random tokens. Do not expose future questions, correct status, explanations, stable option IDs, kernel IDs, misconception tags, or scoring rules.

## Commit and Resume Contract

Every state-changing POST carries a unique `request_id`, the current opaque item token, and the selected opaque option token where applicable.

- Write the response or event before rendering success.
- A repeated `request_id` with the same payload returns the existing result.
- A committed question receiving the same answer under a new request ID also returns the existing result.
- A committed question receiving a different answer returns HTTP 409.
- Reject missing, future, stale, cross-phase, or out-of-order item tokens.
- Derive progress, correctness, reports, and resume position from server-side specs and immutable records.
- Keep `checkpoint.json` replaceable and reconstructable; it is navigation state, not evidence.

For version 3, wrong answers are automatically persisted by the answer transaction. Do not implement or display `/record`, `記錄這個錯誤`, recording confirmation, or a close-page gate. Those behaviors remain valid only inside the unchanged legacy version 2 UI.

## Learning Interaction

- The map shows all area and slice positions, completed nodes, the next available node, and locked future nodes.
- A locked node exposes only its title, position, and prerequisite relationship.
- Completed slices remain readable.
- Completing a slice writes an immutable event and returns to the same phase tab.
- An area checkpoint uses the scored-question contract and saves wrong answers without blocking the next area.
- Review generation remains unavailable until every slice and checkpoint has a completion record.

## Loopback and Security Contract

- Bind only to `127.0.0.1`; reject non-loopback hosts and cross-origin requests.
- Use CSRF protection, strict content types, request body limits, path containment, HTML escaping, opaque random tokens, and constant-time token comparison where relevant.
- Send a restrictive CSP plus `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and a no-referrer policy.
- Acquire one cycle-wide operating-system writer lock and record the owning phase. The OS releases ownership after a crash; the next server can safely reuse the persistent lock file. Join every active request handler before releasing ownership during normal shutdown.
- Keep `validate` and pre-lock phase loading read-only. Persist reports and checkpoints only after the writable server owns the cycle lock.
- Before announcing readiness, verify that mutable directories and reserved files have safe types and remain contained inside the cycle. Reject symbolic-link escapes and invalid parent targets.
- Persist immutable records through same-directory temporary files, flush, `fsync`, and atomic publish.
- Exit after phase completion or the configured inactivity timeout; every accepted local request resets that deadline.

## Calm / Signal UI

- Warm ivory canvas, white task surface, ink text, Purple actions, Lime result accents, semantic red and green, and thin gray rules.
- 12px task-surface radius, 4px controls, at least 44px targets, 65-75ch reading width, and visible blue focus.
- Use semantic `<progress>`, headings, labels, and `aria-live` feedback.
- Support keyboard operation, responsive layouts, and `prefers-reduced-motion`.
- Display `Created by Winston` on every introduction, question, feedback, map, slice, checkpoint, and report state.

## Public CLI

```powershell
python scripts/mastery_session_ui.py validate --workspace <workspace> --cycle mastery-sessions/<cycle-id> --phase assessment|learning|review
python scripts/mastery_session_ui.py serve --workspace <workspace> --cycle mastery-sessions/<cycle-id> --phase assessment|learning|review --port 0
```

Validate before serving. Report the generated loopback URL to the learner and reuse that tab for the entire phase.
