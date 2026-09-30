# ADR-0019: Domain-neutral Capability Semantics and Versioned Knowledge Packs

## Status

Accepted.

## Context

The PREVIEW capability pipeline is source-preserving and deterministic:

```text
accepted CV claims -> EvidenceIndex -> CandidateProfile -> retrieval
-> eligibility -> provisional assessment -> verification queue -> portfolio
```

Its current normalization implementation contains IT/AI terminology (for
example Kafka, Docker, Python, model evaluation, and MLOps). It also has two
semantic paths: the tested retrieval helper produces `EvidenceCandidate`s, but
the persisted assessment currently matches provisional capabilities directly.
That arrangement risks domain overfitting and allows retrieval/assessment
semantics to diverge.

## Decision

- Introduce a domain-neutral semantic core. It owns typed requirement/evidence
  semantics, generic constraints, candidate retrieval, compatibility,
  eligibility, coverage, provisional assessment, and verification.
- Introduce immutable, versioned `DomainKnowledgePack`s. A pack owns aliases,
  canonical terms, vocabulary mappings, and source-grounded semantic hints. A
  pack never returns a capability status or bypasses core compatibility.
- The core accepts generic dimensions only: capability concept, behavior,
  object, context, participation, outcome, source kind, confidence, and
  requirement constraint. `production` is a context value, not a special core
  feature; Docker, IFRS, enterprise sales, and recruiting remain pack data.
- Make retrieval candidates the single semantic input to assessment. A
  requirement assessment must retain both `retrieved_candidate_count` and
  `eligible_candidate_count`; relevant-but-ineligible evidence remains an
  explicit mismatch rather than becoming `not_found_in_evidence`.
- Select packs explicitly from approved role-profile semantic policy metadata.
  New approved profiles store ordered pack references (`pack_id`, `version`) and
  a core policy version. The service must reject an unavailable referenced pack
  rather than infer a domain from CV/JD text.
- `RoleCompetencyProfile` currently has no typed semantic-policy metadata. Its
  compatibility path is therefore an immutable, versioned mapping keyed by the
  exact `(role_profile_id, role_profile_version)`, not a domain heuristic. Each
  mapping stores `core_version`, ordered pack refs, and
  `selection_source=legacy_profile_version_mapping`. A profile without metadata
  may run only when that exact mapping exists; otherwise analysis fails closed
  with `semantic_policy_not_configured`. No legacy row is updated. A new
  portfolio copies either `selection_source=profile_metadata` or
  `legacy_profile_version_mapping` into its snapshot provenance.
- Preserve the current EvidenceIndex priority: accepted raw CV claims override
  a stale flattened CandidateProfile; graph-only profiles retain their graph
  CandidateProfile. The index and semantic views remain in-memory and never
  mutate accepted extraction profiles.

## Consequences

- Existing IT/AI aliases migrate out of `app.capability_analysis` into an
  `it_ai@1` pack without broadening the ontology.
- A role requirement is adapted in-memory into `RequirementSemantics`; missing
  semantic fields remain unresolved. No model call, world-knowledge inference,
  or automatic authoring enrichment is permitted.
- Generic compatibility is requirement-aware: education can be direct evidence
  for an education requirement, credentials for a credential requirement, and
  work/project evidence for demonstrated usage. There is no universal ranking
  that makes work stronger than every other source type.
- New snapshots record the semantic core/policy and selected pack references
  for reproducibility. Existing portfolios keep their historical schema and
  remain readable through defaulted additive fields; historical rows are never
  rewritten.
- PREVIEW governance remains unchanged: no OFFICIAL invocation, VERIFIED
  capability, final competency decision, combined readiness score, learning
  objective, or learning path is introduced.

## Alternatives considered

- Keep adding aliases to `capability_analysis/retrieval.py`: rejected because
  the core would become an implicit IT ontology and could not safely generalize.
- Build a complete enterprise ontology or vector database: rejected because the
  immediate need is a small, deterministic abstraction test, not taxonomy scale.
- Infer a pack/domain from CV/JD wording: rejected because it is unversioned,
  non-reproducible, and can silently apply inappropriate semantics.
- Put eligibility logic inside packs: rejected because different packs would
  produce incompatible assessment and governance outcomes.

## Migration

1. Add contracts and adapters as additive in-memory code.
2. Add typed pack references to newly approved role-profile policy metadata.
   Add a `role_profile_semantic_policy_mappings` store for exact legacy
   profile/version mappings. Its immutable unique key is
   `(role_profile_id, role_profile_version)`; mappings are created explicitly
   by migration/seed or an approved admin workflow, never inferred at runtime.
   Add defaulted semantic snapshot metadata. JSON assessment payloads are
   additive; use a migration for the profile metadata/mapping store.
3. Migrate the current aliases/morphology into `it_ai@1` and run the existing
   AI fixture regressions unchanged.
4. Keep extraction-side PyTorch/Torch entity deduplication unchanged in this
   ADR. It is a compatibility behavior of extraction, not capability assessment
   vocabulary; any later consolidation requires its own migration decision.
