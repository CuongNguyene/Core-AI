# INTEGRATION-06E.1.5 Contract Hardening Report

## Status

PAI Candidate API v1 is hardened for the LMS adapter boundary. No LMS code,
frontend code, or LMS database was changed.

## Decisions

- Candidate list uses organization-scoped keyset pagination with opaque cursors,
  `limit` 1..100, lifecycle `status` filtering, and deterministic `sort`.
- Candidate detail exposes `candidate_id`, lifecycle/review state, stable
  profile `version`, and claims. Internal actor, organization, storage, and
  extraction identifiers remain hidden from the read contract.
- PAI keeps a deliberate two-step flow: create Candidate, then associate an
  already-ingested clean CV document. Association returns candidate, document,
  and candidate-document references and rejects duplicates.
- Review responses use `version` as the stable extraction-profile concurrency
  version. `current_profile_version` remains an internal domain field.
- Review idempotency is persisted in `candidate_review_actions`. Same key and
  action replay the same decision; same key with a different action conflicts.

## Changes

- Added list query validation, filtering, deterministic sorting, and opaque
  cursor pagination.
- Added stable `version` response field.
- Added candidate/document references to association response.
- Added in-memory and SQL review idempotency repositories.
- Added additive Alembic migration `20260818_27`.
- Added contract regression tests for list, detail, upload association, review,
  idempotency, and authorization behavior.

## Remaining gaps

- Multipart upload remains an LMS-facing composition concern; PAI receives an
  existing document reference in this v1 boundary.
- Production identity bridge remains outside the development-header test
  fixture and must be wired before production LMS deployment.
