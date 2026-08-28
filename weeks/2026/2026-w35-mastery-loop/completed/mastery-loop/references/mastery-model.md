# Mastery Evidence Model

Classify demonstrated capability per knowledge kernel. Keep mission-critical blockers visible instead of hiding them in area averages.

## Evidence Levels

| Code | Level | Required evidence | Insufficient evidence |
|---|---|---|---|
| U | Unassessed | no relevant independent evidence | exposure, confidence, credentials |
| F | Fragile | recognition, partial recall, or one narrow correct choice | wording repeated from feedback |
| E | Explained | mechanism, boundary, and coherent rationale | jargon or memorized definition |
| A | Applied | correct use on a representative task with relevant constraints | copying a worked example |
| T | Transfer | uncued correct use on an unseen structural variant | same-session correction after teaching |
| D | Durable | delayed uncued transfer with no unresolved contradiction | any single-session result |

Required level is set by the confirmed mission. End-to-end delivery normally requires simulation or artifact evidence in addition to click evidence.

## Version 3 Evidence Sources

### Batch Assessment

- Preserve every first commitment as `independent` unless a hint was actually given.
- Immediate feedback does not change the already-recorded baseline response.
- Because each Assessment question has a unique kernel, later batch items must not become same-kernel feedback checks.
- One correct item supports at most F. Several coherent items across related kernels may raise area confidence, but never promote an untested kernel.
- Area labels summarize accuracy: `穩定訊號` at 80% or above, `混合訊號` from 50% to below 80%, and `待補強` below 50%. They are not mastery levels.

### Learning

- Reading a slice and marking it complete show exposure only.
- A formative checkpoint is usually `feedback_exposed` because the area was just taught.
- A valid checkpoint may support correction, E, or A according to its cognitive demand, but not T or D in the same session.

### New-Scenario Review

- A correct response shows retrieval or application after learning and may support up to A when same-session feedback is fresh.
- Review can support T only when the scenario is a genuine unseen structural variant, the response is uncued and independent, and the spacing is sufficient to avoid direct answer carryover.
- Review failure preserves the lower state and adds counterevidence.
- A delayed uncued follow-up is required for D.

## Click-Evidence Limits

| Evidence | Maximum provisional support | Additional requirement |
|---|---|---|
| one correct factual choice | F | repeat uncued after spacing |
| several coherent mechanism and boundary choices | E | vary wording and constraints |
| representative scenario decisions | A | include failure cost and observable consequences |
| uncued unseen structural variants | T | change the underlying context, not only names |
| delayed unseen transfer | D | meaningful delay and no contradiction |

Choice recognition cannot prove end-to-end production. Require simulation or artifact evidence for a production mission.

## Independence and Feedback

Use one of:

- `independent`: no relevant answer, hint, or teaching was exposed before commitment;
- `light_hint`: a direction or narrowed boundary was given;
- `heavy_hint`: the answer structure or decisive condition was substantially supplied;
- `copied`: the response reproduces provided material;
- `feedback_exposed`: relevant correctness or teaching was shown earlier in the cycle;
- `corrected`: the record explicitly links a later success to a prior miss.

Preserve timing and lineage. Do not relabel a response after seeing its result.

## Promotion Kernel

For every proposed state change ask:

1. What exact capability is claimed?
2. What observable task would falsify it?
3. Which immutable response, checkpoint, simulation, or artifact supports it?
4. Was the evidence independent, hinted, copied, corrected, or feedback-exposed?
5. Did the learner distinguish mechanism and boundary?
6. Did performance survive a novel context?
7. Did it survive a meaningful delay?

Promote only to the highest directly supported level. Conflicting evidence keeps the lower level or lowers confidence.

## Confidence

- **Low**: one weak sample, ambiguous scoring, strong prompting, or provisional benchmark.
- **Medium**: one clean representative performance or several consistent narrow samples.
- **High**: multiple independent samples, a verified rubric, varied contexts, and no material counterevidence.

Avoid numeric mastery percentages without a validated scoring model. Raw correct counts may be reported as counts.

## Evidence Record

```markdown
### [Timestamp] — [Kernel]

- Cycle, phase, and item ID:
- Displayed option order:
- Selected / correct option ID:
- Misconception tag:
- Scenario fingerprint:
- Independence and feedback timing:
- Lineage: assessment | checkpoint | review | delayed
- Evidence level and confidence:
- What it proves:
- Counterevidence:
- Next discriminating probe:
```

## Overall Claim

- **Not assessed**: critical kernels remain U.
- **Fragile**: critical evidence relies on recognition or prompting.
- **Working**: representative applications succeed; transfer or retention remains open.
- **Transferable**: required unseen contexts succeed independently with valid boundaries.
- **Durable**: transferable performance survives the required delay.

Always append the tested scope: `transferable for [mission/task/context]`.
