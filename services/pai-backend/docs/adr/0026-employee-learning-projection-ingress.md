# ADR-0026: Core-owned Employee Learning Projection ingress

## Status

Accepted for PAI-CANDIDATE-INPUT-01C.3, 2026-10-06.

## Context

The existing `/api/v1/candidate-sources/snapshots` DTO is a candidate-source
contract (`pai.candidate-source`, `v1`), not the complete frozen HRM projection.
Requiring LMS to construct that internal-oriented contract loses employment,
target-job and auxiliary context. CandidateProfile must not expand to retain it.

## Decision

- Add `/api/v1/candidate-sources/learning-projections` with
  `IntegrationEnvelopeV1[EmployeeLearningProjectionV1]`. Keep the old route.
- Validate strict `pai.employee-learning-projection` / `1.0` DTOs, including
  required nested positive integer `snapshot.source_revision`, full candidate
  collections, recruitment collections and the five-field `AtsAiProfileV1`
  explicitly frozen by the integration owner. Reject unknown fields recursively.
- Adapt identity, company, revision, audit timestamp and existing structured
  records explicitly into `CandidateSourceEnvelope`. Reuse the existing
  transaction, exact organization mapping, employee identity lock/retry,
  revision disposition, evidence storage and current pointer update.
- Store the complete canonical external projection in the existing immutable
  snapshot JSON, with its external schema markers. Preserve supplied field
  presence, UTF-8, HTML and list order. Datetimes use ISO canonical serialization;
  omitted fields are not filled into the stored source JSON.
- Audit fingerprint includes the complete projection. Logical content fingerprint
  includes all source sections and identity/schema, excluding only `snapshot`
  (its only permitted fields are revision and audit timestamp). Revision remains
  the sole ordering authority. Same revision changed source context conflicts.
- Employment/JD/recruitment/auxiliary context stays source-only. Existing
  CandidateProfile projection is unchanged; no extraction, claims, verification,
  gap/readiness or ranking side effects. Recruiter verification is not Core
  capability verification. Responsibilities is retained; the new ingress does
  not accept technologies, project_achievements or career salary.
- Integration bearer key, signed Ed25519 actor, persisted roles, nonce protection,
  exact company mapping and signed-organization equality are unchanged.

## Alternatives considered

- Expand the existing route: rejected because it blurs external/internal
  contracts and risks existing callers.
- Store new relational context columns or extend CandidateProfile: rejected;
  existing immutable JSON already owns source snapshots, not semantic activation.
- Drop context in LMS: rejected; Core owns the adapter and preserves the full
  PAI-specific projection.

## Migration and compatibility

NO_MIGRATION_REQUIRED. Alembic remains at `20261006_53`. Old route and payloads
remain compatible. Do not interchange the two schema shapes as equal-revision
retries: their logical contents differ; switching source contract requires a
new upstream revision. No historical snapshot rewrite/backfill is performed.
