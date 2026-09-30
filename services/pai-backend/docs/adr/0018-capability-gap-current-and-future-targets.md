# ADR-0018: Capability Gap Analysis for Current and Future Role Targets

## Status

Accepted.

## Context

Preliminary matching evaluates accepted CV evidence against one active role
profile. Development needs two concurrent, distinct targets: the employee's
current JD (current-role readiness) and an optional future role/level. Evidence
Graph/CandidateProfile already preserves source-backed context and confidence,
but no layer materializes a provisional capability profile and target-aware
gaps. Combining the two targets would lose the distinct urgency, rationale and
unknown inputs for each target.

## Decision

- Add `app.capability_analysis` as a deterministic modular-monolith domain
  module. It reads accepted, non-superseded CV extraction snapshots and
  versioned role profiles. When legacy raw CV claims are present, it derives an
  in-memory EvidenceIndex from those claims rather than trusting a stale
  flattened CandidateProfile; graph-only profiles use their CandidateProfile
  as the evidence source. It does not modify Evidence Graph
  runtime, mutate extraction/matching evidence, call a model provider, create
  competency decisions, or create learning paths.
- The module builds an immutable `ProvisionalCurrentCapabilityProfile` with
  evidence references, environment, participation/context and confidence.
  Capability evidence status is `supported`, `partial`,
  `not_found_in_evidence`, `insufficient`, or `conflicting`; verification
  status is independently `provisional` for every result in this slice.
- A current target resolves by the supplied stable profile ID: `ACTIVE` is an
  approved current-role target; when no active version exists, a
  `PROVISIONAL` JD-derived version may be used and produces a provisional
  current-track warning. The source JD remains the current target; caller does
  not choose a different current target in place of it.
- A future `ACTIVE` role profile supports official analysis. A future
  `PROVISIONAL` role profile runs only in preview mode and emits
  `future_target_profile_provisional`. `DRAFT` and `RETIRED` profiles are
  rejected for analysis. `PROVISIONAL` is added to the existing role-profile
  lifecycle; preliminary matching continues to accept only `ACTIVE` profiles.
- Every requirement assessment and gap has target ID/type, requirement ID,
  evidence references, retrieved/eligible candidate counts, missing signals,
  rationale and a target-local
  preliminary priority. The priority records unavailable business impact,
  risk, frequency, deadline and manager confirmation as missing inputs rather
  than inferring them.
- Current and future analyses are persisted as separate target tracks in one
  immutable `CombinedGapPortfolio`. Optional overlap links reference existing
  gaps only; no gap is merged, no priority is shared, and no combined readiness
  score exists.
- The development API accepts only managed IDs: accepted CV profile ID, current
  target stable profile ID, optional future target stable profile ID and
  correlation ID. Application service performs actor ownership/organization,
  accepted-input, source-JD, lifecycle and stale-version guards. Audit stores
  safe IDs, versions, mode, outcome/warning codes and correlation ID only; an
  audit failure rolls back the portfolio transaction.

## Alternatives considered

- Extend `PreliminaryMatch` with two targets: rejected because it would conflate
  recruitment/current-role matching with development analysis and break its
  existing active-only target contract.
- Return a computed view without persistence: rejected because target versions,
  warnings, priorities and reviewable provenance must be reproducible.
- Create a single shared gap list/score: rejected because a shared prerequisite
  has different target-specific priority and rationale.

## Consequences

- The matching role profile enum/persistence accepts `PROVISIONAL`, while its
  current matching service remains active-only.
- PR-011 adds versioned portfolio, target-track/gap, overlap-link and audit
  persistence with a new Alembic migration; it does not migrate raw CV/JD or
  revise historical matching records.
- Learning path generation remains a later consumer and cannot consume this
  output until an explicit eligibility/review contract is approved.
- Retrieval is not eligibility: a context mismatch preserves retrieved evidence
  references/counts while reporting zero eligible candidates. Downstream
  consumers must not reinterpret evidence gaps as confirmed capability deficits.

## Migration

Add `provisional` as an allowed stored role-profile status and create
`capability_gap_portfolios`, `capability_target_analyses`,
`capability_requirement_assessments`, `capability_gaps`,
`capability_gap_overlap_links` and append-only `capability_analysis_audit_events`.
Unique constraints cover immutable portfolio version, target type per portfolio,
gap identity per target/requirement and overlap source/target pairs. Index
portfolio actor/organization, current/future target IDs and audit lookup.
