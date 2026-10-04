# COURSE-REC-01A.3D-6 — Compatibility, Migration & End-to-End Dry Run

## Result and scope

The domain-only integration dry run passes. It exercises the actual 3D-4 target
adapter, actual 3D-5 course projection, and the unchanged COURSE-REC-01B engine
using deterministic synthetic governed artifacts. No production code,
repository data, database, migration, API, or LMS state was changed. No commit
or push was made.

The migration inventory covers repository-visible schemas, fixtures, and
evidence. It is not a live database/customer-data inventory. All unknown runtime
records remain outside the dry run and require a separately authorized,
read-only source inventory before any future migration design.

## Contracts inspected

- 3D-1 `CanonicalCapabilityRef` is a version-independent canonical string;
  `SourceSemanticRef` retains namespace, entity kind, source ID, and optional
  source version.
- 3D-2 resolves a canonical identity to an exact `CapabilityDefinitionPin`
  under an ACTIVE release. Historical resolution requires the exact release
  identity and checksum and does not redirect to a replacement.
- 3D-3A supplies immutable semantic evidence and proposal/review contracts.
- 3D-3B activates exact mappings against source and definition pins. Current-use
  resolution rejects stale source pins, deprecated mappings, inactive target
  definitions/releases, and inactive dependency closure. Historical mapping
  replay is a separate resolver mode.
- 3D-4 `project_governed_recommendation_target(...)` validates RoleRequirement,
  gap, LearningNeed lineage and current mapping authority. It returns the
  existing `RecommendationTarget` plus a governance sidecar. `target_ref` is
  `LearningNeed.target_reference`; `source_learning_need_ref` is
  `LearningNeedProfile.id`.
- 3D-5 `project_governed_course_capabilities(...)` consumes outcomes/direct
  claims and current governed mappings. It preserves the course profile
  lifecycle and returns the existing normalized candidate only for a matching
  ACTIVE profile; governance pins remain in the projection sidecar.
- 3D-5A replaced the ambiguous direct-claim delimiter identity with the
  structured SHA-256 ID `dc1_<64 hex>`. The original 3D-6 delimiter blocker is
  therefore superseded; exact course ownership and recomputed source identity
  are now checked from structured claim fields.
- 01B still accepts `RecommendationTarget` and
  `CourseRecommendationCandidate` without governance-specific fields. It uses
  exact string intersection, ACTIVE-profile eligibility, existing level and
  prerequisite policies, deterministic ordering, and its existing
  `NO_SUITABLE_COURSE` result.

## End-to-end proof

The happy path builds a synthetic ACTIVE `test_core_pack@1.0`, approved exact
source mappings, and an exact common definition pin. 3D-4 projects
`role_profile:req-1` through the LearningNeed/gap lineage to
`capability:test_core:communication`. 3D-5 projects the external
`skillscommons:course-e2e` learning outcome to the same canonical reference and
returns its existing `NormalizedCourseCandidate`. The dry-run verifies exact
`CapabilityDefinitionPin` equality before sending these outputs to 01B.

01B selects `skillscommons:course-e2e` at rank 1 with `FULL_COVERAGE`. Its trace
retains target `role-1@2`, LearningNeed `need-record-1`, gap `gap-1`, requirement
`req-1`, path `path:1`, and step `step:2`. Target-side and course-side mapping
fingerprints, source refs, source evidence pins, mapping IDs, and definition
pins remain in the adapter sidecars. Governance data is not added to the 01B
ranking schema.

Pin equality is the dry-run join gate. If two sides resolve the same canonical
ref under different exact definition pins, the harness rejects the join. It
does not infer compatibility from version ordering or select “latest”. The
happy-path mappings share one release checksum, so the exact pin matches.

## Additional integration cases

- Two target capabilities joined to a full internal candidate and a partial
  external candidate; full coverage ranks first and candidate-order reversal
  leaves the serialized result unchanged.
- An exact no-intersection candidate returns `NO_SUITABLE_COURSE`; there is no
  forced fallback.
- A stale target mapping is rejected before a target can reach 01B. A changed
  course outcome evidence pin is rejected before course coverage can reach
  01B.
- A valid DRAFT profile remains DRAFT through 3D-5 and is rejected by 01B's
  ACTIVE-only gate.
- Deprecated course mapping resolves only through the explicit historical
  resolver with exact source and target pins; current course projection rejects
  it.
- Internal Frappe-LMS-style and external SkillsCommons-style courses use the
  same semantic projection and 01B decision behavior. Four synthetic domain
  namespaces (software/AI, sales, finance/accounting, HR/communication) also
  join without engine branches.
- Different exact definition releases for the same canonical ref are rejected
  by the test-only join gate. No production compatibility wrapper was needed.

Separate 3D-4/3D-5 and 3D-2/3D-3B regression tests cover deprecated mappings,
inactive definitions/releases/dependencies, unresolved required facets,
unmapped outcomes, source freshness, historical replay, profile lifecycle,
and no automatic capability creation/remap.

## Compatibility and read-only migration classification

| Artifact | Current identity/status | Classification | Future action |
|---|---|---|---|
| `professional_capability_core@0.1` | Versioned extraction taxonomy; no pack lifecycle/owner/approval binding | KEEP_AS_IS | Retain for current CV extraction. Do not treat as universal course authority or import as a pack implicitly. |
| RoleRequirement | Business ID (fixture `req-1`), profile/version lineage | KEEP_AS_IS | Preserve IDs; attach separately reviewed canonical bindings through 3D-4 where available. |
| CapabilityGapProfile | Analysis/target/gap lineage (fixture `analysis-1` / `gap-1`) | KEEP_AS_IS | Preserve source lineage; never rewrite IDs to canonical refs. |
| LearningNeedProfile | Record ID `need-record-1`, competency/business ID `req-1` | KEEP_AS_IS | Preserve IDs and provenance; future mapping remains additive through the target adapter. |
| LearningPath target/step | Opaque trace refs (`path:1`, `step:2` in fixtures) | KEEP_AS_IS | Preserve trace identity; no capability inference. |
| Legacy opaque course capability refs | Example `project_management` in older draft/test artifacts | REMAP | Require a new exact approved mapping and profile review before current governed use; no label/key conversion. |
| Two SkillsCommons semantic profiles | DRAFT: `course-profile:skillscommons:6f6156c3-7b85-4ce0-85cc-1efbd439d144:semantic`; DRAFT: `course-profile:skillscommons:f64795cb-b561-4bb6-9748-9841d6e982dd:semantic` | EXPERIMENT_ONLY | Preserve unchanged; no activation, canonicalization, or migration. |
| Internal/external synthetic catalog fixtures | 24 internal profiles and 24 ExternalCourse objects generated by `course_catalog/fixtures.py` | EXPERIMENT_ONLY | Keep as contract fixtures; their example capability strings are not production authority. |
| SkillsCommons provider sample | Repository evidence: 80 raw search records; 30 exact online-course records processed; 27 strict candidates observed | KEEP_AS_IS | Provider facts remain provider-owned; no capability assignment is implied. |
| 01B target/request/result fixtures | Pure deterministic contracts, no persistence | KEEP_AS_IS | Preserve request/result/trace identities; do not interpret test refs as governance authority. |
| Historical governed mapping | Test-only immutable mapping with exact source/definition pins | KEEP_AS_IS | Replay only via historical resolver; never feed into current recommendation. |

Dry-run simulation does not emit canonical refs for unresolved labels or
taxonomy IDs. Repository-visible migration rows and blocking reasons are in
`migration-inventory.json`. No live DB enumeration was performed, so this
report does not claim that runtime stores contain no additional records.

## Direct claim identity audit

The originally reported `<course-id>#<claim-id>` collision was reproduced in
3D-5A and replaced before this rerun. Current source identity is a fixed-length
hash of canonical structured JSON `(course_ref, claim_id)`, namespace remains
provider/source-owned, and ownership checks use exact `claim.course_ref` plus
recomputed identity. Internal and external fixtures pass the same adapter.
Classification: `DIRECT_CLAIM_CONVENTION_SAFE` under the 3D-5A contract.

## COURSE-REC-01C readiness and next milestone

Decision: `READY_FOR_01C_WITH_CONSTRAINTS`. 01C may persist request/result,
algorithm ID/version, target/candidate refs, decision details, trace refs, and
the exact source/mapping/definition provenance needed to reproduce the domain
decision. Persist the pin/provenance sidecars explicitly if reproducibility
requires them; 01B itself does not carry those governance details.

01C must not assume latest pack/mapping, equate business IDs to canonical refs,
auto-migrate taxonomy keys, accept DRAFT mapping authority, or make
SkillsCommons experiment profiles eligible. Runtime inventory and persistent
governance stores remain prerequisites for production data migration, not for
this domain-only 01C boundary.

Recommended next primary milestone: `COURSE-REC-01C — Recommendation
Persistence + API`, because the pure domain flow is now integrated and the
next product dependency is durable, explainable recommendation requests and
results. No 01C implementation is included here.

## Verification

Focused 3D-1 through 3D-5, 3D-6 synthetic integration, catalog/providers,
Role/Gap/LearningNeed/LearningPath, and 01B regressions: 400 passed, 0 failed.
Ruff format/check, mypy across the governed adapter/catalog/recommendation
contracts, JSON validation, whitespace/secret scans, and `git diff --check`
passed. No live network was used.
