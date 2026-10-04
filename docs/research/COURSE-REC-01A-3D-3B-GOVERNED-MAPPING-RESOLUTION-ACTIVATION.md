# COURSE-REC-01A.3D-3B — Governed Mapping Resolution & Activation

## Result

Status: COMPLETE for the bounded domain contract. Pure Python/Pydantic domain values only; no persistence, API, database, migration, UI, LMS change, model call, or network call. The 3D-3B additions live under `services/pai-backend/backend/app/capability_governance/` and are directly imported from focused modules; the package initializer is untouched.

## Contract

The activation path is `CapabilityMappingProposal(EXACT) → CapabilityMappingReview(APPROVE) → proposal/review integrity → fresh SourceSemanticPin → 3D-2 resolve_for_new_binding → exact CapabilityDefinitionPin → MappingActivationApproval pin checks → immutable GovernedCapabilityMapping(ACTIVE)`. A 3D-3A review or an active 3D-2 capability alone does not create mapping authority. `AI_ASSISTED` proposals use the same human review and explicit activation approval gates.

`SourceSemanticPin` covers the complete `SourceSemanticRef` (including source version) and canonical full-value evidence tuple with deterministic SHA-256 over compact sorted-key JSON. Empty evidence, cross-source evidence, source-version drift, source-identity drift, and changed evidence fail closed.

`MappingActivationApproval` pins proposal ID/fingerprint, exact review fingerprint, source pin, and target definition pin. It records an approver as domain evidence, not authentication. No new reviewer/approver separation rule was added.

`GovernedCapabilityMapping` stores mapping identity, proposal/review fingerprints, source/evidence pin, mapping type/scope, exact target `CapabilityDefinitionPin`, activation approval reference, approver, lifecycle and stable authority fingerprint. It is frozen. The fingerprint covers the stable authority payload and deliberately excludes deprecation metadata, so deprecation preserves the original authority identity.

Conflict identity is `(source_ref, mapping_scope, evidence_fingerprint)`. Only a different target ref under the same key among ACTIVE EXACT mappings conflicts. Same mapping ID plus identical content is idempotent; same ID plus different content fails. Distinct source-semantic facet identities are allowed. No fuzzy semantic comparison occurs.

Current resolution requires an ACTIVE mapping, exact current source/evidence pin, and a still-active exact target pin with active dependency closure. A newer release is never silently adopted. Historical resolution accepts ACTIVE or DEPRECATED mapping lifecycle and resolves the exact source and target pins through 3D-2 historical resolution; draft target authority is rejected. The returned `GovernedCapabilityBinding` is explicitly marked `current` or `historical`; neither is a recommendation, learner verification, or course profile.

## Verification

Focused 3D-3B suite: 37 passed. Regressions: 260 passed (3D-1 identity 35; 3D-2 definition/pack/resolution 73; 3D-3A mapping contracts 49; catalog fixtures/schema/semantic enrichment 24; recommendation 25; role/LearningNeed 30; semantic-core/policy 24). Aggregate: 297 passed.

Changed-scope Ruff check and format passed; mypy passed on all four production modules. Evidence JSON is in `test/results/course-rec-01a-3d-3b/`. Synthetic contract examples only; no live provider/network/model execution.

## Boundaries and readiness

3D-1, 3D-2, 3D-3A contracts and package exports were not modified. 01B recommendation code is untouched. LMS checkout is untouched. 3D-4 target adapters and 3D-5 course adapters may consume the immutable governed mapping and current/historical resolver outputs in parallel, subject to their own approved scopes. Persistence/API/authenticity is intentionally deferred: the approval model is domain evidence and must be supplied by a separately authorized boundary if/when persisted or exposed.

No commit or push was performed. Core-AI had pre-existing user-owned tracked changes and many untracked artifacts before this milestone; all were preserved. LMS remained clean.

## Evidence index

See `test/results/course-rec-01a-3d-3b/summary.json` and the individual prerequisite, pin, review, approval, target authority, mapping lifecycle, current/historical resolution, stale input, conflict, negative-case, compatibility, test, and static-check JSON artifacts.
