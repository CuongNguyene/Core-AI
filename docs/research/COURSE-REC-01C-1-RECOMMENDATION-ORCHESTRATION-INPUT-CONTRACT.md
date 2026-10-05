# COURSE-REC-01C.1 — Recommendation Orchestration Input Contract

## Decision

**Status: `GOVERNANCE_AUTHORITY_NOT_DURABLY_RESOLVABLE`.** Do not implement or expose a stable-reference orchestration API yet. The existing 3D-4 and 3D-5 adapters require exact governed domain objects as inputs; current capability-definition, pack-release, mapping and activation authority has no durable repository/table/API in the application. Reconstructing those objects from fixtures or caller payloads would violate the governance boundary.

The 01C endpoint remains an internal execution boundary. A later orchestration service can call the unchanged 3D-4 → 3D-5 → 01B → 01C chain once authoritative persistence and the other durable input sources are available.

## Repository and runtime scope

- Core-AI: `/Users/mac/Developers/work/LMS/Core-AI`, branch `feat/deterministic-ai-course-planning-workspace`, HEAD `ee0c85a21b9646ce1ea8b152b5cb4a8b4cd69c39`.
- LMS: `/Users/mac/Developers/work/LMS/lms`, branch `feat/learning-operations-phase-1`, HEAD `f8d51b9dda0a4cbe67c3331d566faf4f9afef60f`; unchanged.
- Core-AI pre-existing untracked user artifacts were preserved: `docs/research/PAI-CURRICULUM-VERIFY-01.md`, `graphify-out/`, `test/results/frappe-core-auth-smoke-01/`, `test/results/pai-curriculum-verify-01/`.
- Local PAI containers are running. PostgreSQL is reachable and reports Alembic `20260929_50`; current source head is `20261005_51`. Runtime is therefore not current with the checked-out/pushed 01C source. No migrations, restarts, or writes were performed.
- Count-only runtime inventory found 2 role competency profiles, 6 gap portfolios, and 1 learning path. The current runtime schema has no `course_recommendation_executions` table and no tables for capability definitions, pack releases, governed mappings, LearningNeed profiles, course capability profiles, or external courses.

## Existing execution path

1. Target-side source data is loaded by existing candidate, matching and capability-gap repositories. `LearningNeedProjectionService` derives `LearningNeedProfile` values in memory from a gap portfolio and exact role profile; its identity is `learning-need:{portfolio.id}:{gap.id}`.
2. `project_governed_recommendation_target(...)` in `app/capability_governance/target_adapter.py` validates exact role/need/gap lineage and resolves each explicitly supplied source pin against supplied `GovernedCapabilityMapping` objects and active `CapabilityPackRelease` context. It returns `GovernedRecommendationTargetProjection` containing the existing 01B target and governance provenance.
3. Course-side source objects are `CourseCapabilityProfile`, outcome/direct-claim inputs, mappings and active release context. `project_governed_course_capabilities(...)` in `app/capability_governance/course_projection.py` resolves current exact mappings and returns `GovernedCourseProjectionResult`.
4. `CourseRecommendationExecutionService.execute(...)` builds immutable snapshots and calls the unchanged deterministic `CourseRecommendationEngine.recommend(...)`.
5. The 01C repository persists `CourseRecommendationExecutionRecord`; request-key idempotency is scoped by organization and actor, and GET reads the stored record without re-execution.

## Persistence audit

| Input/authority | Current state | Assessment |
|---|---|---|
| Candidate and extraction profile | SQLAlchemy tables/repositories; profile links pin profile identity/version; candidate carries organization and actor ownership | Durable source exists; recommendation orchestration-specific ownership composition is not implemented |
| RoleCompetencyProfile | `role_competency_profiles`, exact-version repository lookup; requirements are embedded JSON with stable requirement IDs | Durable and exactly addressable by profile ID/version; no complete recommendation resolution adapter |
| CapabilityGapProfile/portfolio | `capability_gap_portfolios` and related assessment/target-gap tables; repository has candidate/org/actor-scoped access | Durable, versioned snapshot source exists |
| LearningNeedProfile | Pydantic projection only; deterministic ID generated from gap portfolio/gap; no ORM table/repository/API | `IN_MEMORY_ONLY`; cannot resolve directly after restart from `learning_need_ref` |
| LearningPath | `learning_paths` SQL table and repository; ID/version, status, subject and organization; lessons/modules are nested JSON | Durable and versioned; no recommendation adapter pins a path or step to target projection |
| LearningPathStep | No standalone model/table identified; path contents are nested JSON | Not independently addressable; exact stable step contract is absent |
| ExternalCourse | Provider-normalized Pydantic model. SkillsCommons and Open edX adapters can fetch provider data; no durable catalog repository/table | `IN_MEMORY_ONLY` at application catalog boundary |
| CourseCapabilityProfile / outcomes / direct claims | Pydantic domain contracts and enrichment/projection code; no durable tables/repository found | `IN_MEMORY_ONLY`; no ACTIVE profile query |
| CapabilityDefinition / PackRelease / GovernedMapping / activation approvals | Pure Pydantic/domain lifecycle and resolution functions; no SQLAlchemy models, migration tables, durable repository or runtime authority API found | Not durably resolvable; hard stop |

The `semantic_policies` and role-profile semantic-policy mapping tables are separate policy/configuration concepts; they are not 3D-2 capability definition/pack authority or 3D-3 governed mapping activation records.

## Stable reference contract findings

- `candidate_ref` can name a persisted candidate UUID, but authorization and organization checks must happen before profile/gap resolution.
- `role_profile_ref` can only be unambiguous as the exact `(id, version)` pair; repository methods that return active/latest are not acceptable fallback for this contract.
- `learning_need_ref` is not currently independently resolvable. Its deterministic ID is a projection identity, not a durable record.
- A target projection also requires the exact gap portfolio/target lineage, explicit required facets/source pins, active release context, and matching current governed mappings. There is no stable-ref service that assembles these safely.
- `learning_path_ref` can identify a persisted path ID/version, but path-step identity is nested and no path-to-need recommendation binding exists. Do not require these refs until an existing domain contract makes them authoritative.
- No labels, role names, job titles, course titles, or implicit latest lookups can substitute for these identities.

## Course discovery and provider readiness

There is no durable catalog query for ACTIVE `CourseCapabilityProfile` records. `MockExternalProvider` is fixture-backed. SkillsCommons and Open edX adapters fetch/normalize provider facts, but fetched `ExternalCourse` objects are not durable governed candidates. Semantic enrichment creates draft profiles; it does not create mapping authority or populate an ACTIVE profile store. Therefore discovery is `NOT_AVAILABLE` for production recommendation orchestration.

The existing provider-neutral contract remains correct: both internal and external courses must pass through the same persisted `CourseCapabilityProfile` → 3D-5 → 01B path. SkillsCommons provider fetch and normalization may be available, but semantic profile population, durable storage and current governed mappings are not. Open edX has the same persisted semantic/governance gap. Do not claim recommendation-candidate readiness from provider fetch success.

## Existing 01C API and chosen option

`POST /api/v1/course-recommendations` accepts `request_key`, a full `GovernedRecommendationTargetProjection`, a tuple of full `GovernedCourseProjectionResult` values, and `max_results`. It requires the integration bearer plus signed actor context. It is an `INTERNAL_EXECUTION_API`, not a stable-ref application orchestration API. It returns the persisted execution; same actor/org/key and identical effective input replays, while changed effective input conflicts. GET reads only the stored snapshot.

**Chosen contract: Option C — blocked.** Do not add or extend a route. The future preferred request should use the minimum authoritative refs (likely candidate plus exact LearningNeed identity once persisted, with only necessary exact target/path context), but the exact schema cannot be frozen until source persistence and resolution contracts are available. Do not accept client-created governed projections as a workaround.

## Authorization, idempotency, history

The current execution API's integration bearer, signed actor, organization and execution-record access controls are reusable unchanged. A future orchestration API must enforce candidate ownership/organization before loading sensitive profile data. 01C idempotency and historical snapshot GET are reusable unchanged; orchestration must resolve current authority only for new executions and must not repin on replay or GET.

## Blockers and next milestone

Actual blockers are (1) no durable 3D-2/3D-3 governance authority, (2) no durable LearningNeed identity, (3) no durable course semantic profile/catalog source, and (4) no application adapter that resolves exact target inputs and assembles 3D-4/3D-5 inputs. The primary blocker is governance authority because production projections cannot safely be built without it.

Recommended next milestone (exactly one): **CAPABILITY-GOVERNANCE-PERSISTENCE**. Establish durable, versioned storage and exact current/historical lookup for definitions, pack releases, mapping proposals/reviews/activation and source pins, preserving existing 3D contracts. Re-audit after that milestone; do not implement orchestration as part of this audit.

## Verification and changes

Read-only source inspection and runtime table/count queries only. No application, API, 3D, 01B, LMS or database changes. No regression suite was run because the decision gate stopped implementation; the checked-out runtime image/schema is also behind current source. `git diff --check` was clean before the audit artifacts. No commit or push was performed.
