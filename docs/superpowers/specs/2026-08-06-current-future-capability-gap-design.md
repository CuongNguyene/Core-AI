# Current-Role and Future-Role Capability Gap Analysis Design

## Goal

Add a deterministic `capability_analysis` module above the existing Evidence
Graph/CandidateProfile and versioned role competency profiles. It produces a
provisional current capability profile, separate current-role and future-role
gap analyses, and a combined portfolio that links related work without
combining readiness or gaps.

The module stops before learning-objective or learning-path generation.

## Scope and boundaries

- Inputs are persistence-managed IDs only: an accepted CV extraction profile
  (or an eligible matching run that snapshots it), a current target profile,
  and an optional future target profile. Public callers cannot submit inline
  CandidateProfile, evidence, JD, or role-profile payloads.
- The module reads CandidateProfile/Evidence Graph entities and their source
  evidence. It does not mutate graph/runtime extraction behavior, extraction
  profiles, role profiles, preliminary matches, or competency records.
- Every current CV/evidence-derived capability remains `verification_status =
  provisional`. The analysis never creates an assessed or verified competency
  decision and never creates a learning path.
- Current JD is the current development target. The current target resolves to
  an approved current-role competency profile when available. Otherwise, a
  profile derived from that current JD is eligible only as a provisional target
  and the resulting current track is explicitly marked provisional.
- A future `ACTIVE` profile supports official analysis. A `PROVISIONAL` future
  profile supports preview only and returns a warning. `DRAFT` and `RETIRED`
  profiles are rejected for official analysis; they are not silently treated as
  provisional.
- Existing `RoleCompetencyProfile` lifecycle behavior remains compatible. The
  capability module introduces target-usage policy rather than changing
  Evidence Graph runtime. A follow-up ADR/migration will make the approved vs
  JD-derived/provisional target provenance explicit where it is persisted.

## Domain model

### Provisional current capability profile

`ProvisionalCurrentCapabilityProfile` is an immutable analysis snapshot. A
capability observation includes a stable capability ID/value, the originating
CandidateProfile entity reference, and a list of evidence observations. Each
observation retains:

- source/evidence reference and locator;
- environment;
- participation/usage context;
- extraction confidence;
- source-backed excerpt/reference only where the upstream contract permits it.

It deliberately does not reduce a capability to a bare keyword or aggregate
confidence into a declared skill level.

Each capability has one of:

- `supported` — source-backed evidence meets the deterministic condition;
- `partial` — relevant evidence exists but is incomplete or below the target
  threshold;
- `not_found_in_evidence` — no relevant evidence was found; this does not mean
  the employee lacks the capability;
- `insufficient` — evidence exists but cannot support the required judgment;
- `conflicting` — source-backed observations materially conflict.

`verification_status` is separate and always `provisional` in this slice.

### Target-aware requirements and gaps

The evaluator creates a requirement assessment for every target requirement.
It contains `target_id`, `target_type` (`current_role` or `future_role`),
`requirement_id`, matched evidence references, missing signals, rationale,
provisional priority, status, and the target/rule/policy versions.

Gaps are target-aware projections of assessments not fully supported. They
retain the same identifiers and evidence/rationale metadata. A missing signal
describes what the evidence cannot establish; it never asserts an absent human
capability.

### Separate tracks and combined portfolio

`CurrentRoleGapAnalysis` and `FutureRoleGapAnalysis` have independent target
snapshots, readiness summaries, warning metadata, assessments, gaps and
priority lists. Future analysis is absent when no future target is selected.

`CombinedGapPortfolio` contains both tracks and optional overlap links. An
overlap link references two existing target-specific gap IDs and describes a
shared prerequisite/evidence theme. It never merges the gaps, rewrites their
priorities, or creates an overall/combined readiness score.

## Deterministic flow

1. Resolve the CV extraction profile and require its accepted, non-superseded
   CandidateProfile snapshot. No raw document is loaded.
2. Resolve the current target: prefer its approved profile; otherwise resolve
   the profile derived from the current JD and mark target usage provisional.
3. Build a source-preserving provisional capability snapshot from CandidateProfile
   entities/evidence. This reuses existing source locator, context and
   confidence semantics without altering extraction runtime.
4. Evaluate every current target requirement independently and create the
   current-role track.
5. If a future profile is supplied, enforce its target-usage policy and
   evaluate the same capability snapshot independently for the future track.
6. Create overlap links only after both tracks exist, using shared prerequisite
   keys/references. Preserve each source gap and priority unchanged.
7. Persist one immutable analysis/run snapshot and safe audit metadata. Audit
   stores IDs, versions, target usage mode, outcome, warning/reason codes and
   correlation ID—not raw CV/JD, excerpts, CandidateProfile payload or PII.

## Prioritization

Priority is explicitly `preliminary`. It may derive only from target-local
requirement classification and known target-local policy metadata. The result
must record `missing_priority_inputs` when business impact, risk, frequency,
deadline, or manager confirmation is unavailable. It must not infer those
values from CV text, title, classification, or the other target track.

Priority and rationale are calculated and stored per target-specific gap. A
shared prerequisite link is informational, not a priority override.

## API and persistence

The development API will create/read an analysis by references, for example:

```json
{
  "cv_profile_id": "accepted-cv-profile-id",
  "current_target_profile_id": "current-role-profile-id",
  "future_target_profile_id": "optional-future-role-profile-id",
  "correlation_id": "request-correlation-id"
}
```

The service enforces ownership/organization and target eligibility; a router
does not bypass the guard. A matching-run reference may be added as an
alternative request shape only when it resolves the same accepted CV and
current target snapshots, never as inline payload.

Persistence will use immutable, versioned analysis records with child target
assessment/gap and overlap-link rows. The exact CandidateProfile/extraction,
target-profile, rule and policy versions are snapshotted. A failed audit write
rolls back the analysis record. No learning tables are written.

## Errors and warnings

Fail closed for unavailable/unaccepted/superseded CV input, a missing current
target, unusable current target, a `DRAFT`/`RETIRED` future target, cross-owner
or cross-organization access, and stale input versions. A future provisional
profile succeeds only as `preview` and returns the stable warning
`future_target_profile_provisional`.

## Testing strategy

TDD starts with pure schema/rule tests before production code. Required cases:

- CandidateProfile evidence preserves context/environment/participation and
  confidence in the provisional profile;
- every provisional capability uses the required evidence status and separate
  provisional verification status;
- current approved target is preferred, while JD-derived target is allowed with
  a provisional warning;
- active future target is official; provisional is preview-only; draft/retired
  are rejected;
- the same evidence can appear as explanatory references in both tracks, while
  each target retains separate assessments, gaps, rationale and priority;
- overlaps link, rather than merge, current/future gaps; no combined readiness
  score is present;
- missing priority inputs are recorded rather than guessed;
- service/API guards accept IDs only, enforce ownership/organization and do
  not mutate extraction/Evidence Graph/competency/learning state;
- persistence snapshots versions and rolls back on audit failure;
- deterministic golden fixture reruns produce equivalent normalized output.

## Explicit non-goals

- changing Evidence Graph extraction or CandidateProfile runtime;
- competency verification/assessment decisions;
- target recommendation/manager confirmation workflow;
- business-impact, risk, frequency or deadline inference;
- learning-objective generation, learning-path creation, LMS progress, or
  credential issuance;
- combined readiness or a single undifferentiated gap list.
