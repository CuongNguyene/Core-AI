# JD-to-Role-Profile Authoring Design

## Goal

Replace the seed-only role target with a reviewable workflow:

```text
accepted JD extraction profile
  -> RoleProfileDraft
  -> reviewer authoring and validation
  -> approval
  -> ACTIVE or PROVISIONAL RoleCompetencyProfile
```

The workflow never promotes an extraction result directly to `ACTIVE`.

## Scope

The milestone adds a persistence-backed draft aggregate, reviewer authoring,
quality-gate validation, approval, safe audit events and development API routes.
The reviewer may edit every `RoleRequirement` field: ID, dimension,
classification, evidence terms, conflicting terms, confidence threshold,
assessment recommendation and rubric version.

The workflow consumes only an accepted, non-superseded JD extraction profile.
It does not accept raw JD text, raw excerpts, model payloads or arbitrary JSON
schema. Drafts and their versions are not eligible for matching or capability
analysis.

## Lifecycle and status rules

`RoleProfileDraft` states are `DRAFT`, `IN_REVIEW`, `NEEDS_REVISION`,
`PROVISIONAL` and `ACTIVE`. Draft creation always starts at `DRAFT`. Authoring
creates an immutable incremented version and returns to `DRAFT`. Reviewer
submission moves a current draft to `IN_REVIEW`; validation then moves it to
`NEEDS_REVISION`, `PROVISIONAL` or `ACTIVE` according to the quality-gate
matrix. Approval requires a reviewer expected-version check.

Approval chooses the output status explicitly:

- A gate with no `BLOCKING` finding may produce `PROVISIONAL` when remaining
  warnings are explicitly allowed by policy.
- `ACTIVE` requires reviewer approval and every mandatory gate to pass.
- A `BLOCKING` finding produces `NEEDS_REVISION` and cannot produce either
  `PROVISIONAL` or `ACTIVE`.
- No path can produce `ACTIVE` without a passing mandatory gate and reviewer
  approval.

The resulting `RoleCompetencyProfile` retains the accepted JD profile ID and
version, immutable versioned requirements, rule-set/policy versions, approval
actor and draft source in safe audit metadata. Existing matching and capability
services continue to accept only `ACTIVE` targets for official use and treat
`PROVISIONAL` as non-official where already supported.

## Quality gate

The gate is deterministic and does not inspect raw source text:

1. The source extraction profile is `JD`, `ACCEPTED` and not superseded.
2. At least one requirement exists.
3. Requirement IDs are unique and match the identifier contract.
4. Each requirement has non-empty evidence terms, valid dimension and
   classification, a threshold in `[0, 1]`, and non-empty recommendation and
   rubric version.
5. No requirement is silently created from an `UNKNOWN` or `INSUFFICIENT` JD
   claim; authoring must supply the complete structured requirement explicitly.

Every finding has severity `INFO`, `WARNING`, `ERROR` or `BLOCKING`. Validation
returns codes, severity and counts only. It never returns raw JD text or source
excerpts.

Requirement fields that the JD does not establish, including target level,
observable behavior, priority and evidence constraints, remain unset. When a
field is filled, it records one provenance value: `jd_extraction`,
`taxonomy_normalization`, `approved_template`, `policy_default` or
`reviewer_authored`.

## Authorization and concurrency

Only actors with the existing `REVIEWER` role can create, edit, validate or
approve drafts. Every mutation requires the draft owner organization and an
`expected_version`; stale writes return a conflict. An approver cannot approve
an unvalidated version. The API uses the existing development identity header
and safe error envelope.

## API

- `POST /role-profile-drafts` with `source_jd_profile_id` and correlation ID.
- `GET /role-profile-drafts/{draft_id}` returns safe current draft state.
- `PATCH /role-profile-drafts/{draft_id}` replaces the full structured title
  and requirement set with an expected version.
- `POST /role-profile-drafts/{draft_id}/validate` validates the expected
  version and returns findings.
- `POST /role-profile-drafts/{draft_id}/approve` accepts expected version and
  requested output (`active` or `provisional`), subject to the gate.

Responses contain IDs, versions, status, requirements and finding codes. They
exclude raw JD, source excerpts, prompt/model data and internal persistence
metadata.

## Testing and acceptance

Tests cover schema boundaries, source eligibility, draft creation, complete
authoring, stale version rejection, deterministic quality findings, forbidden
active promotion, successful active promotion, provisional fallback and safe
audit metadata. An API integration test executes accepted JD profile -> draft
-> edit -> validate -> approve and verifies the resulting role profile can be
read by existing role-profile consumers.
