# CAP-DEMO-04D — Capability gap to Learning Need projection

## Boundary

`LearningNeedProjectionService` is a deterministic instructional-design
projection over the canonical capability-gap output. It consumes the persisted
`CombinedGapPortfolio` contract and the exact `RoleCompetencyProfile` version;
it does not rerun matching, retrieve CV/JD evidence, mutate `TargetGap`, or
invoke an LLM.

The existing `LearningNeedProfile` remains the domain shape used by the
learning-authoring compatibility APIs. The new projection service returns
active projection items on demand. No Learning Need table, migration, Learning
Path, Training Brief, or Course Authoring integration is introduced here.

## Deterministic policy

| Source assessment | Dimension | Projection |
| --- | --- | --- |
| supported | any | skipped; no active learning need |
| insufficient | skill | `READY_FOR_LEARNING` / `learning` |
| insufficient | qualification | `READY_FOR_LEARNING` / `learning` |
| insufficient | experience | `UNRESOLVED` / `experience_exposure` |
| requires verification | any | `NEEDS_VERIFICATION` / `verification` |
| not found in evidence | any | `EVIDENCE_MISSING` / `verification` |
| context mismatch with evidence | any | `UNRESOLVED` / `experience_exposure` |
| context mismatch without evidence | any | `UNRESOLVED` / `unresolved` |

Credential and education are never converted into a generic course by absence
of evidence. Responsibilities and exclusions are not input gaps; the service
also rejects a non-scoreable requirement if one is supplied accidentally.
Logical OR semantics are preserved upstream: the projection only consumes the
resolved gaps and does not reopen failed branches.

## Governance and provenance

Projection IDs are deterministic:
`learning-need:<analysis-id>:<source-gap-id>`. Each item preserves candidate
reference, target profile ID/version, capability analysis ID/version, source
gap reference, requirement reference, priority, and evidence references. The
policy identity is `learning_need_projection@0.1`.

When the source track is `PREVIEW`, the projection remains `PREVIEW` and carries
`source_capability_analysis_preview`; it is not an official learning
recommendation. Current state and missing knowledge remain unknown/empty unless
the upstream contract explicitly provides those facts. Raw CV/JD text, prompts,
provider responses, and hidden evidence payloads are not copied.

## Compatibility boundary

The legacy `map_target_gap_to_learning_need` mapper and existing authoring API
remain source-compatible for existing callers. New policy-aware consumers must
use `LearningNeedProjectionService`; this prevents the instructional projection
from changing capability-analysis semantics or forcing a broad downstream
migration in this milestone.

## Verification

The focused policy tests cover supported, insufficient skill, verification,
not-found, credential/education verification, experience exposure, preview
provenance, deterministic IDs, and raw-data non-leakage. The runtime reference
portfolio `cap-demo-04b-20260911-runtime-2` is expected to produce no
`READY_FOR_LEARNING` items when its three assessments are
`not_found_in_evidence`; controlled fixtures are required for the other policy
branches.

No persistence change is required. Lesson/course generation remains a future
consumer and is outside CAP-DEMO-04D.
