# COURSE-REC-01A.3D-4 — Role & LearningNeed Target Adapter

## Status

Implementation and focused regressions: PASS. The adapter is a pure, in-memory projection and does not change COURSE-REC-01B, LMS, persistence, APIs, migrations, or course projection.

## Identity flow

- `RoleCompetencyProfile.id/version` pins exactly one current/future `CapabilityGapProfile` track by target ID/version.
- `RoleRequirement.id` must occur exactly once in the role profile and selected gap track.
- `LearningNeedProfile.competency.id` and the required `requirement_reference` must match that requirement. Its analysis/source-profile/target provenance must match the supplied gap profile and selected track; every source gap ref must uniquely map to that requirement.
- Existing semantic source refs remain separate: role source is `role_profile` + `ROLE_REQUIREMENT` + requirement ID + role-profile version; LearningNeed source is `learning_need` + `LEARNING_NEED_COMPETENCY` + competency ID. LearningNeed has no independent version, so the adapter does not fabricate one; the caller supplies a source version/pin and freshness is resolved exactly.
- `RecommendationTarget.target_ref` is the actual version-pinned learning target, `LearningNeedProfile.target_reference` (e.g. `role-1@2`). `source_learning_need_ref` is the separate LearningNeed record ID. COURSE-REC-01B keeps target refs opaque and echoes them to result trace; its fixture does not conflate target identity and need-record identity.

## Eligibility and target constraints

The adapter reuses the existing `LearningNeedEligibility.READY_FOR_LEARNING` and `LearningNeedResolution.LEARNING` states, which the current LearningNeed projection policy emits for eligible insufficient skill/qualification needs. All other combinations fail closed. It does not introduce or reinterpret eligibility states. Full role requirement and LearningNeed snapshots, gap entries, usage mode, warning codes, explicit learning constraints, and provenance are retained in the typed sidecar. Explicit need/role target levels are preserved; conflicting explicit values fail, absent values stay absent, and definitions never supply a level.

## Mapping resolution and multi-facet rules

Each explicit `RequiredTargetFacet` has a bounded `facet_id` and exact source pin. The adapter ignores unrelated mappings in a broad context, filters on exact source semantic identity, then consumes only exact source pins. If same-source candidates exist but none match the current evidence fingerprint, it invokes current-use resolution to propagate stale/deprecated/authority failures; it never drops a required stale facet. Every accepted mapping passes through `resolve_governed_mapping_for_use`, preserving native 3D-2/3D-3B authority errors and exact `CapabilityDefinitionPin`.

Each caller-declared facet is resolved independently. Role ↔ LearningNeed equivalence is never inferred from shared requirement/lineage. A shared caller-supplied `facet_id` requires all resolved canonical outputs to agree. Same canonical ref plus same complete definition pin deduplicates the target ref and retains every mapping provenance row; canonical ref with different pins fails closed. Output ordering is deterministic.

## 01B and course-projection boundaries

The existing `RecommendationTarget` schema is constructed unchanged. Original role, need, gap, path, and step refs are preserved as trace identity, not replaced by canonical capability refs. The adapter does not claim verified learner proficiency, infer mappings from text, query taxonomy, call an LLM/embedding, or mutate source objects. 3D-5 code is not imported or edited; LMS remains untouched.

## Verification

- Focused adapter suite: 20 passed.
- Combined 3D-1/3D-2/3D-3A/3D-3B/Role/Gap/LearningNeed/LearningPath/01B regressions plus adapter: 274 passed.
- Ruff and mypy results are recorded in `static-checks.json`.
- No live service or external network is part of this milestone.
