# E2E CV-JD Capability Analysis Design

## Goal

Provide a controlled end-to-end workflow using two operator-supplied documents:

```text
raw CV -> accepted CandidateProfile
raw JD -> accepted JDExtractionProfile -> RoleProfileDraft
       -> reviewer authoring, validation and approval
       -> PROVISIONAL or ACTIVE RoleCompetencyProfile
accepted CV + approved role profile -> capability analysis
```

JD extraction is evidence extraction only. It never creates a role profile or
an `ACTIVE` competency framework.

## Source and review states

Raw CV/JD files may remain in secured document storage for extraction and human
review. The extraction worker creates only an `ExtractionProfile` in
`PENDING_REVIEW`. Review transitions are:

```text
PENDING_REVIEW -> ACCEPTED | NEEDS_REVISION | REJECTED
NEEDS_REVISION -> PENDING_REVIEW | REJECTED
```

Only an accepted, non-superseded `JDExtractionProfile` can create a
`RoleProfileDraft`. A rejected or needs-revision profile is never a role-target
source.

## Role profile state machine

```text
DRAFT -> IN_REVIEW -> NEEDS_REVISION
                   -> PROVISIONAL
                   -> ACTIVE
NEEDS_REVISION -> DRAFT
```

Reviewer authoring creates a new immutable draft version and returns it to
`DRAFT`. Approval is the only transition to `PROVISIONAL` or `ACTIVE`.
`PROVISIONAL` and `ACTIVE` are immutable materialized `RoleCompetencyProfile`
versions; later changes create another draft/version rather than editing an
approved profile.

## Requirement completion and provenance

JD claims are atomized into structured requirement candidates. The authoring
surface may normalize a capability and complete a requirement, but no field is
invented from absence in the JD. Each of these fields carries field-level
provenance:

| Field | Allowed provenance |
| --- | --- |
| capability / normalized term | `jd_extraction`, `taxonomy_normalization`, `reviewer_authored` |
| priority | `approved_template`, `policy_default`, `reviewer_authored` |
| target level | `approved_template`, `policy_default`, `reviewer_authored` |
| observable behavior | `approved_template`, `reviewer_authored` |
| evidence constraints | `approved_template`, `policy_default`, `reviewer_authored` |

`jd_extraction` may establish only a claim and its locator reference; it cannot
by itself establish target level, observable behavior, priority or evidence
constraints. The approved profile/audit stores only document IDs, hashes, claim
IDs and source locators. It never stores raw CV/JD, excerpts, raw prompts or raw
model output.

## Quality gate matrix

| Severity | Meaning | Approval effect |
| --- | --- | --- |
| `INFO` | Informative normalization or traceability finding | Does not block approval |
| `WARNING` | Data is incomplete but an explicit policy allows review | May approve `PROVISIONAL`; blocks `ACTIVE` when mandatory |
| `ERROR` | Requirement cannot be evaluated as authored | Requires reviewer correction or explicit policy downgrade; never qualifies for `ACTIVE` |
| `BLOCKING` | Source invalid, mandatory structure missing, provenance absent or policy violation | Cannot approve `PROVISIONAL` or `ACTIVE`; transition to `NEEDS_REVISION` |

The gate validates atomization, unique requirement identities, complete
structured metadata, provenance for each completed field, capability
normalization, mandatory priority/target/evidence rules and source eligibility.
It records safe code/severity/reference counts only.

## Capability-analysis modes

An approved role profile determines analysis mode:

| Profile status | Analysis mode | Constraints |
| --- | --- | --- |
| `PROVISIONAL` | `PREVIEW` | Preliminary evidence/gaps only; no combined or final competency decision |
| `ACTIVE` | `OFFICIAL` | Official current-role analysis; still provisional evidence, not a final competency decision |

`DRAFT`, `IN_REVIEW` and `NEEDS_REVISION` are not analysis targets. The
portfolio must retain the selected target status/version and mode.

## Evidence source and retrieval boundary

Capability analysis reads an accepted CV through a semantic evidence view. If
the accepted profile has legacy `CVExtractionOutput` claims, those claims are
the source of truth: an in-memory `EvidenceIndex` projects their
`evidence_type`, source locator and source excerpt reference into a
CandidateProfile-compatible form. A persisted CandidateProfile is used only
when the CV is graph-only and has no legacy claims. This avoids an older,
flattened compatibility projection downgrading `work_experience` or
`project_usage` into `mentioned`.

Normalization, retrieval, eligibility and assessment are distinct stages:

```text
accepted claims / graph evidence
-> EvidenceIndex
-> canonical capability normalization
-> retrieved candidates
-> context and strength ranking
-> deterministic eligibility
-> provisional assessment
```

Every candidate preserves original evidence type and context. Every assessment
returns both `retrieved_candidate_count` and `eligible_candidate_count`.
Consequently, an explicit production requirement can return
`context_mismatch` with retrieved candidates and zero eligible candidates. A
retrieved project deployment never becomes production evidence; a Docker
mention never becomes usage evidence.

## E2E harness

The harness receives `PAI_REAL_CV_PATH`, `PAI_REAL_CV_SHA256`,
`PAI_REAL_JD_PATH` and `PAI_REAL_JD_SHA256`. It verifies both hashes before the
first upload and prints only opaque IDs/statuses/finding codes.

It runs two independent scenarios against exact run-scoped IDs:

1. A source-complete but policy-permitted incomplete draft is reviewer-approved
   as `PROVISIONAL`; capability analysis returns `PREVIEW`, target-local gaps
   and no combined/final decision.
2. A complete, provenance-backed draft passes all mandatory gates and is
   reviewer-approved as `ACTIVE`; capability analysis returns `OFFICIAL` with
   target-local assessments/gaps and no final competency decision.

Cleanup is opt-in and deletes only the two uploaded documents, object keys,
jobs, profiles, drafts, materialized profiles, portfolios and audit children
referenced by the individual run. It never deletes by owner, filename or broad
table scan.

## Required E2E assertions

- Both hash preflights fail before upload on mismatch.
- CV and JD document/job/profile lifecycles are independently clean, succeeded
  and accepted.
- JD extraction does not create a role profile before draft authoring/approval.
- Every completed requirement field has permitted provenance; unspecified JD
  fields remain unset until explicitly authored or policy/template supplied.
- `BLOCKING` findings prohibit both approval statuses.
- `PROVISIONAL` returns `PREVIEW`; `ACTIVE` returns `OFFICIAL`.
- Neither result contains raw document data, excerpt, prompt/model fields or a
  combined/final competency decision.
- Requirement assessments distinguish retrieved from eligible evidence. A
  production mismatch must retain the retrieved count/reference while reporting
  zero eligible candidates; it must not be represented as `not_found`.
- Cleanup removes only exact IDs from its own scenario.
