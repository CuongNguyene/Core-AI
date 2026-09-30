# INTEGRATION-01B — Versioning Strategy

## Canonical Contract Set

The canonical integration contract version is **v1**. Implementation MUST use
these canonical documents:

- `01b-api-contract-design.md`
- `01b-course-blueprint-contract.md`
- `01b-learning-result-contract.md`
- `01b-identity-contract.md`

Older unprefixed documents in this directory are historical references only.
They MUST NOT be used as implementation specifications. New contract changes
MUST update the canonical v1 documents first, then update any historical
reference only when preservation/context requires it.

## Version locations

- REST endpoints: `/api/v1/integration/...`.
- Payload envelope: required `schema_version`, initially `v1`.
- Immutable sources: `blueprint_id` plus semantic `version`; assessment references likewise include ID/version.
- Events: dot-versioned names such as `learning.result.completed.v1`.

## Compatibility rules

- Additive optional fields within `v1` are backward compatible; consumers ignore unknown fields.
- Removing a field, changing a type/meaning, or making an optional field required requires `v2`.
- An event name version never changes meaning after publication. Corrections are a new event with a new `event_id`, correlation ID, and explicit relation to the corrected event where needed.
- Each consumer validates `schema_version` before business processing and returns `unsupported_schema_version` for unsupported versions.
- New blueprint semantic versions create explicit LMS projection decisions; they do not patch an existing delivery record implicitly.

## Deprecation

PAI publishes a replacement version, compatibility window, migration examples, and an end-of-support date before deprecating a contract version. LMS acknowledges supported versions through deployment/configuration, not by a runtime database dependency. A deprecated field remains accepted/readable for the published window and is never repurposed with a new meaning.

## Delivery evolution

MVP may send `LearningResultEvent v1` to the PAI REST intake synchronously and receive a receipt. A later broker/outbox implementation reuses the event name and payload; it does not turn an LMS delivery record into a PAI persistence model or alter the source-of-truth rules.
