# INTEGRATION-01B.1 — Contract Validation Checklist

Use this checklist before approving an implementation, contract revision, or
consumer integration for canonical contract version `v1`.

## Semantic guardrails

- [ ] `CourseBlueprint` is not persisted as an LMS `Course` directly.
- [ ] LMS `Course` is a projection/delivery object with its own lifecycle.
- [ ] `AssessmentBlueprint` is not equivalent to an LMS `Quiz`.
- [ ] Quiz completion cannot create a `VERIFIED` competency.
- [ ] An LMS certificate cannot create a PAI competency credential.
- [ ] Evidence remains PAI-owned.
- [ ] No shared database is introduced.
- [ ] No LMS foreign key points to PAI evidence storage.

## Ownership validation

- [ ] Every exchanged entity has an explicit semantic owner.
- [ ] Every contract field has a source of truth.
- [ ] Lifecycle ownership is explicit and does not transfer through projection.
- [ ] Projection direction is defined, versioned, and acknowledged where required.
- [ ] LMS learning results are delivery facts; PAI evaluates any evidence use under policy.
- [ ] Opaque evidence display references are `display_only` with `persist_allowed: false`.

## Implementation readiness

- [ ] Canonical contract version `v1` is identified.
- [ ] Deprecated contracts are marked and excluded from implementation input.
- [ ] API consumers use the canonical `01b-*.md` v1 contracts.
- [ ] Public error boundary and schema-version handling are documented.
- [ ] Identity contract and trusted actor reference are defined.
- [ ] Organization/tenant authority is resolved, or the implementation is explicitly limited to an approved single-tenant pilot.
