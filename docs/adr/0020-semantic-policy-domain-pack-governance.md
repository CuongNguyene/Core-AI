# ADR-0020: Semantic Policy and Domain Pack Governance

## Status

Accepted.

## Decision

Semantic interpretation is governed by an explicit, immutable reference:

```text
RoleCompetencyProfile.semantic_policy_ref
  -> SemanticPolicy(policy_id, version, ACTIVE)
  -> DomainKnowledgePack(pack_id, version, ACTIVE, checksum)
  -> domain-neutral capability core
```

`SemanticPolicy` has the intentionally small lifecycle `DRAFT -> ACTIVE ->
DEPRECATED`. A released policy version and its pack binding are never edited in
place. A semantic change creates a new policy version; a pack behavior change
creates a new pack version/checksum.

Runtime resolution is exact and target-specific. There is no latest-version
lookup, domain guessing, or implicit `it_ai@1` fallback. Current and future
targets resolve independently. New analysis requires an ACTIVE policy and an
ACTIVE exact pack; a deprecated dependency is readable only for explicit
historical replay.

Domain packs provide normalization and semantic hints only. They cannot emit
assessment status, verification state, gap decisions, readiness, or scores.
Eligibility and assessment remain owned by the domain-neutral core.

## Persistence and audit

Migration `20260810_23` adds the versioned `semantic_policies` registry,
append-only lifecycle audit events, and nullable exact policy binding columns on
role profiles. Existing role profiles and portfolios remain readable without a
policy; they are not backfilled. New portfolios retain target-specific,
immutable semantic snapshots with policy/pack provenance and checksums.

The minimal governance API exposes draft creation, exact-version read,
activation, deprecation, and role-profile binding. Audit metadata contains IDs,
versions, actor IDs, and timestamps only; raw CV/JD text and model payloads are
never included.

## Compatibility

The pre-existing `core_version + pack_refs` metadata remains readable for
legacy profiles. It is an explicit legacy mapping path, not a default domain
selection. New approved profiles can persist `semantic_policy_ref`; approval
validates the referenced ACTIVE policy and exact pack binding while preserving
the existing competency quality gates.
