# COURSE-REC-01A.3D-4 Role & LearningNeed Target Adapter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement task-by-task. Steps use checkbox syntax. The user forbids commit/push, so this plan intentionally has no commit steps.

**Goal:** Project an existing role/LearningNeed target into the unchanged COURSE-REC-01B `RecommendationTarget` only through exact, fresh, current-use governed capability mappings.

**Architecture:** Add one pure target-side adapter module that validates RoleCompetencyProfile, CapabilityGapProfile, and LearningNeedProfile lineage, accepts explicit current `SourceSemanticPin` facets, and delegates every mapping to `resolve_governed_mapping_for_use`. Return the existing RecommendationTarget plus a typed provenance sidecar retaining exact mappings, definition pins, role/need/gap identity, explicit constraints, and eligibility. No edits to governance, RecommendationTarget, RecommendationEngine, 3D-5, or LMS.

**Tech Stack:** Python 3.13+, Pydantic v2, existing Core-AI domain models, pytest, Ruff, mypy.

**Spec:** `/Users/mac/.codex/attachments/5ddbe8f2-717f-4648-b664-2bfa8b2dfecd/Pasted text.txt`

## Global Constraints

- Do not redesign capability governance or implement course-side projection.
- Do not modify COURSE-REC-01B, persistence, API, UI, migrations, or LMS.
- Do not modify any `course_projection.py`, course adapter, `CourseCapabilityProfile`, or `NormalizedCourseCandidate` construction.
- Do not migrate or rewrite legacy RoleRequirement, LearningNeed, gap, or RecommendationTarget identities.
- Use current-use 3D-3B resolution for every mapping; historical resolution is not valid for a current target.
- No inference, nearest/fuzzy matching, taxonomy lookup, LLM, or embedding calls.
- No commit and no push.

## Review Focus

1. Role-profile or gap-profile version mismatch must fail instead of silently using a latest profile; Task 2 covers mismatched target ID/version and analysis provenance.
2. A stale mapping among multiple facets must fail closed without dropping a required facet; Task 3 covers stale and missing-facet cases.
3. Same canonical ref plus the same exact definition pin deduplicates with provenance retained; the same canonical ref plus different pins fails closed; Task 3 covers both invariants.
4. An opaque/non-numeric target level must be preserved exactly, and absent levels must remain `None`; Task 3 covers both and verifies capability definitions never supply level.
5. A non-learning/verification-only need must not become an ordinary recommendation target; Task 2 covers eligibility/resolution gates and retained state on success.

---

## File Ownership

- Create `services/pai-backend/backend/app/capability_governance/target_adapter.py` — input facet, lineage/provenance/result contracts, stable adapter errors, and pure projection function.
- Create `services/pai-backend/backend/tests/test_governed_target_adapter.py` — synthetic role/gap/need/pack fixtures and focused behavior tests.
- Create `docs/research/COURSE-REC-01A-3D-4-ROLE-LEARNINGNEED-TARGET-ADAPTER.md` — actual identity/data flow, exact adapter contract, boundaries, limitations, and results.
- Create the 13 suggested JSON artifacts under `test/results/course-rec-01a-3d-4/`.
- Do not edit package initializers or any existing product file unless a proven blocker requires it; if an upstream contract defect is discovered, stop and report it.

## Interfaces

- Input source object types: `RoleCompetencyProfile`, `CapabilityGapProfile`, `LearningNeedProfile`.
- Required facet input: `RequiredTargetFacet(facet_id: str, source_pin: SourceSemanticPin)`. Its ref must be either `ROLE_REQUIREMENT` (`source_namespace="role_profile"`, source ID equal to the exact requirement ID, source version equal to the supplied role profile version) or `LEARNING_NEED_COMPETENCY` (`source_namespace="learning_need"`, source ID equal to the need competency ID). The LearningNeed schema has no independent version field; preserve any supplied source version exactly and require fresh evidence pinning rather than invent a version. A shared `facet_id` is an explicit caller declaration that two source facets represent one requested logical target; never infer Role ↔ LearningNeed equivalence from lineage.
- Mapping input: `tuple[GovernedCapabilityMapping, ...]`; authority always comes from `resolve_governed_mapping_for_use` with the current facet pin and complete supplied mapping context.
- Authority context: `tuple[CapabilityPackRelease, ...]` passed unchanged to the 3D-2/3D-3B resolver.
- Proposed entry point:

```python
project_governed_recommendation_target(
    *,
    role_profile: RoleCompetencyProfile,
    gap_profile: CapabilityGapProfile,
    learning_need: LearningNeedProfile,
    required_facets: tuple[RequiredTargetFacet, ...],
    governed_mappings: tuple[GovernedCapabilityMapping, ...],
    active_release_context: tuple[CapabilityPackRelease, ...],
    source_learning_path_ref: str | None = None,
    source_path_step_ref: str | None = None,
    prerequisite_context: RecommendationPrerequisiteContext | None = None,
) -> GovernedRecommendationTargetProjection
```

- Result contains the existing `RecommendationTarget`, sorted unique exact canonical refs, resolved current `GovernedCapabilityBinding` values, exact `CapabilityDefinitionPin` values, and a sidecar retaining mapping/proposal/review/approval fingerprints plus source/role/need/gap lineage and target constraints. It does not claim learner proficiency.
- Validate that role profile ID/version matches exactly one current/future target track in the supplied gap profile; need analysis ID/version, target ID/version, target reference, requirement ID, and all source gap refs must agree with the selected track and requirement.
- Inspect and reuse the actual LearningNeed eligibility/resolution enums and existing projection policy. Require `READY_FOR_LEARNING` plus `LEARNING` only if those remain the actual governed states; do not create or reinterpret states. Preserve eligibility, resolution, usage mode, warnings, role behavior/context/priority, LearningNeed constraints, and target level in the sidecar. Reject mismatched explicit role/need target levels; otherwise use the explicit need target level, falling back only to the explicit RoleRequirement target level. Never infer from a capability definition.
- For each explicit required facet, select only mappings whose source identity matches that facet. Ignore unrelated source mappings in the supplied context deterministically. Missing matching mappings fail with stable `TARGET_CAPABILITY_UNRESOLVED`; a stale exact facet must propagate its source/authority error and cannot be dropped; conflicting matching mappings fail closed. `TARGET_MAPPING_SOURCE_MISMATCH` is reserved for a mapping explicitly assigned to a facet by the caller but carrying a different source.
- If the same canonical ref resolves through the same exact `CapabilityDefinitionPin`, deduplicate the target ref while retaining every provenance record. If one canonical ref resolves with different definition pins, fail closed. Resolve every explicitly supplied source facet independently; when facets share a caller-declared `facet_id`, their canonical result must agree or fail `TARGET_CANONICAL_BINDING_CONFLICT`.
- Identity evidence: COURSE-REC-01B defines `target_ref` as the recommendation target identity and echoes it in result/trace, while its test fixture uses the opaque `learning-target:001`; it does not equate that value to a LearningNeed record ID. Upstream `LearningNeedProfile.target_reference` is the version-pinned target identity (`target-id@version`), while `LearningNeedProfile.id` identifies the need record. Therefore project `target_ref=learning_need.target_reference`, and `source_learning_need_ref=learning_need.id` as the trace field. Keep those semantics distinct.
- Mismatched lineage fails with stable `TARGET_LINEAGE_MISMATCH`. Native 3D-2/3D-3B authority errors propagate.

## Task 1: Adapter Contracts and Fail-Closed Errors

**Files:** create the adapter module and focused test module.

- [x] Write tests for frozen `RequiredTargetFacet` (including explicit `facet_id`), source-kind/namespace/ID/version validation, frozen provenance/result shapes, and stable blank/mismatch error values.
- [x] Run focused pytest and verify it fails because the adapter contracts do not exist.
- [x] Add the small immutable contracts and `TargetAdapterError` with stable codes; import exact upstream contracts directly without changing `__init__.py`.
- [x] Run focused pytest, Ruff, and mypy on the new module.

## Task 2: Exact Role, Gap, and LearningNeed Lineage

**Files:** adapter module and focused tests.

- [x] Add RED tests for requirement membership/uniqueness; exact role ID/version to one gap-profile track; exact Need ID, competency/requirement reference, analysis ID/version, target ID/version, target reference, and gap-ref lineage; reject cross-track and non-learning eligibility/resolution.
- [x] Implement pure lineage validation. Do not perform latest lookup, alter source models, or replace competency/requirement IDs.
- [x] Test source identity remains separate from canonical refs and explicit role behavior/context/priority, need learning constraints/eligibility, and gap provenance are retained in sidecar.
- [x] Verify focused tests pass.

## Task 3: Governed Current Mapping and RecommendationTarget Projection

**Files:** adapter module and focused tests.

- [x] Add RED tests for no mapping, unrelated context mappings being ignored, stale source, deprecated mapping, inactive target/dependency propagation, wrong exact target pin, historical-only rejection, multiple explicit facets, exact-pin duplicate canonical refs, conflicting pins for one canonical ref, same declared-facet conflict, independently resolved Role/Need facets, and no fuzzy/taxonomy fallback.
- [x] Implement mapping selection by exact source identity and `SourceSemanticPin`; for every consumed mapping call `resolve_governed_mapping_for_use` with the current pin and supplied mapping context. Do not read `mapping.status` as a substitute for resolution.
- [x] Build the existing `RecommendationTarget` without changing its schema: `target_ref=learning_need.target_reference`; `source_learning_need_ref=learning_need.id`; role requirement and source gap refs from the validated source; level only from explicit Need/RoleRequirement data; exact path/prerequisite refs passed through unchanged.
- [x] Ignore unrelated mappings in broad context; resolve each explicit required facet independently. Sort/deduplicate canonical refs only when their exact definition pins agree; retain one provenance record per successfully resolved mapping. A missing/stale/conflicting required facet blocks the entire projection.
- [x] For a caller-declared shared `facet_id`, verify Role/Need canonical outputs agree; do not synthesize any equivalence from lineage.
- [x] Verify focused tests pass and existing RecommendationTarget/01B tests remain green.

## Task 4: Documentation, Evidence, and Regression

**Files:** research report and `test/results/course-rec-01a-3d-4/*.json`.

- [x] Record actual identity flow, resolver reuse, lineage/eligibility rules, target level, unresolved behavior, provenance sidecar, and explicit 3D-5/01B/LMS boundaries.
- [x] Run focused tests and regressions for 3D-1, 3D-2, 3D-3A, 3D-3B, role profile/source adapter, capability gap profile, LearningNeed, LearningPath, and COURSE-REC-01B.
- [x] Run changed-scope Ruff format/check and mypy; validate JSON, whitespace, secret scan, and `git diff --check`.
- [x] Recheck Core-AI and LMS HEAD/status; confirm 3D-5 files are untouched, no files staged, and no commit/push occurred.
- [x] Self-review against all 42 acceptance checks and produce the requested 20-section final report; no independent reviewer is assumed available.

## Self-Review Coverage

The task suite maps identity/lineage checks to Task 2; current authority, stale/unresolved/conflict and multi-facet behavior to Task 3; exact RecommendationTarget fields, level, trace, and deterministic ordering to Task 3; learner-verification boundary and legacy isolation to Tasks 2–4; and all specified upstream regressions/static checks to Task 4. No test relies on course projection or live network.

## Execution Constraints

- Work in place: canonical Core-AI is dirty with pre-existing user changes and prior milestone modules are untracked dependencies; an isolated HEAD worktree would omit them.
- The LMS checkout is read-only and clean at preflight.
- No 3D-5-owned projection file was present at preflight; recheck before edits and leave any newly appearing concurrent file untouched.
- User forbids commits/pushes; do not stage or commit any work.
