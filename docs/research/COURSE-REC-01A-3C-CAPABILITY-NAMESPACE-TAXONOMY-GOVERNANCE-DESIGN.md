# COURSE-REC-01A.3C — CAPABILITY NAMESPACE & TAXONOMY GOVERNANCE DESIGN

## Status

COMPLETE

This is a concrete architecture recommendation, not an implemented or activated taxonomy. All proposed contracts/rules below are design decisions for a later bounded implementation. Existing behavior is explicitly distinguished from proposed behavior. No namespace, capability ID, permission assignment or mapping was created.

## 1. Repository

Core-AI path: /Users/mac/Developers/work/LMS/Core-AI
Branch: feat/deterministic-ai-course-planning-workspace
HEAD: a078526ab7ea38327fdeece142aba325f3de3352
Working tree: dirty before this milestone.
Pre-existing changes: three tracked config/settings changes plus untracked COURSE-REC code/tests/scripts/docs/evidence, graphify-out and earlier integration verification artifacts. Exact inventory/checksums are in preflight.json.

LMS path: /Users/mac/Developers/work/LMS/lms
Branch: feat/learning-operations-phase-1
HEAD: 129fde12a3856eb07a8690ab0ebac528b2f26e61
Working tree: clean.

Production code changed: NO.

Backend app/, tests/ and scripts/ references below are relative to services/pai-backend/backend/. Prior 01A, 01A.3, 01A.3B and 01B documentation/evidence were inspected along with actual contracts, projection code, policy service/API, normalization code and focused test sources. Historical test results are evidence of earlier milestones, not a new execution claim.

## 2. Current Problem

Current taxonomy: professional_capability_core@0.1.
Original purpose: bounded CV capability selection/evaluation, subsequently reused by CV bounded/discovery pipelines.
Current course use: experiment-local restriction in semantic_enrichment.py; the general CourseCapabilityProfile contract remains opaque-reference based.
Primary semantic risk: treating requirement identity, source topic/outcome and canonical developed capability as interchangeable.

01A.3B found a supported project-management mapping, an ambiguous physical-therapy leadership claim, nine clear zero-coverage source semantics without an equivalent taxonomy entry, and no formal hierarchy. Coverage absence does not authorize capability creation.

Existing role DomainKnowledgePack objects supply normalization/hints, not a canonical course capability taxonomy.

## 3. Semantic Entity Definitions

| Entity | Meaning | Identity owner | Current namespace | Notes |
|---|---|---|---|---|
| Candidate capability | Evidence-supported provisional capability/skill observation | Candidate/extraction source | Entity labels/IDs, optional extraction mapping | Not assessed/verified automatically |
| Role requirement | Authored behavior, context, level and constraints | Role-profile author | requirement.id within profile/version | Business requirement, not canonical concept ID |
| Gap capability/requirement | Requirement-scoped assessment/evidence gap | Capability analysis | requirement_id, gap.id, analysis version | Missing evidence is not absence of capability |
| LearningNeed competency | Requirement-backed learning target | Need projection | competency.id=requirement.id | Preserve source linkage |
| LearningPath target | Objective tied to need/gap/role | Learning service | Need competency; legacy gap_id | Path lifecycle separate |
| Course capability | Evidence-supported development/coverage | Core-AI semantic catalog | Opaque capability_ref | Not completion-based verification |
| Course learning outcome | Intended observable source learning result | Course author; preserved by Core-AI | No distinct catalog model today | May remain unmapped |
| Provider subject/topic | Provider content/classification label | Provider | Metadata locators | Not developed capability by default |
| Occupation metadata | Occupational context/classification | Provider/standard owner | taaccct.occupation | Does not prove course outcome |
| Domain taxonomy entry | Bounded definition of semantic concept | Current owner undeclared; proposed namespace owner | Current extraction IDs | Future governed lifecycle distinct |

Lifecycle owners: candidate evidence/assessment services, role governance, analysis, learning-need source/eligibility, learning-path review, course semantic-profile review, provider/source releases, and future definition-pack governance respectively.

Evidence: app/extraction/profile.py, app/matching/schemas.py, app/capability_analysis/schemas.py, app/learning_need_profile/schemas.py, app/learning/schemas.py and app/course_catalog/schemas.py.

## 4. Current Identity Flow

| Edge | Current identity behavior | Source |
|---|---|---|
| Role -> Gap | requirement.id preserved as requirement_id | capability_analysis/schemas.py:238 |
| Role/Gap -> Need | competency.id=requirement.id; source gaps retained | learning_need_profile/projection.py and mapper.py |
| Need -> Path objective | competency_id copied from need | learning/mapper.py:41 |
| Legacy verified gaps -> Path | gap_id used as competency_id | learning/service.py:440 |
| Need/Path -> RecommendationTarget | Canonical refs explicitly supplied by caller; adapter absent | course_recommendation/schemas.py:57 |
| CourseProfile -> NormalizedCandidate | capability_ref copied verbatim | course_catalog/schemas.py |
| Target + candidate -> Engine | Exact string intersection | course_recommendation/engine.py:123 |

Where canonical identity is missing: no governed automatic role/need/path-to-canonical target adapter; general course refs are opaque; extraction taxonomy identity is not a global contract.

Proposed identity flow:

~~~mermaid
flowchart LR
  R[Role requirement + source version] --> RM[Approved capability facet mapping]
  R --> G[Requirement-scoped gap]
  G --> N[LearningNeed preserves requirement identity]
  N --> L[LearningPath target preserves source lineage]
  RM --> T[Canonical target refs + pinned context]
  L --> T
  C[Course + source version] --> O[Source outcomes or direct claim evidence]
  O --> CM[Approved facet mapping + coverage scope]
  CM --> P[Reviewed course profile projection]
  P --> A[Target-specific eligibility adapter]
  T --> A
  K[Active core/domain capability releases] --> A
  A --> E[Unchanged exact-ref engine 01B]
~~~

The convergence is on approved capability facets, not on replacement of business IDs.

## 5. Existing Governance

Role-side governance: SemanticPolicy DRAFT -> ACTIVE -> DEPRECATED; exact policy/pack/version/checksum resolution; immutable active release; target-specific provenance; historical replay; explicit legacy mapping without backfill.

Course-side governance: CourseCapabilityProfile draft/active/deprecated and required coverage provenance. No definition-pack registry, namespace owner or cross-pipeline mapping approval exists.

Reusable mechanisms: exact references, immutable release checksums, explicit approval/lifecycle audit, dependency validation and historical reads.

Missing governance: capability definitions/owners, course-development evidence rules, canonical mapping authority and dual-identity adapters.

app/semantic_policy/api.py calls require_reviewer; app/extraction/auth.py requires the persisted REVIEWER role. This is evidence about current policy administration, not authority to activate a future taxonomy. Existing SME/ADMIN roles do not automatically imply taxonomy ownership.

ADR-0019/0020 and policy tests establish reusable patterns. Existing DomainKnowledgePack performs normalize_term, expand_aliases and source-grounded hints; it never decides assessment, gap, readiness or VERIFIED state.

## 6. Shared Capability Identity

Should role and course semantics converge to the same canonical capability identity: YES, only for reviewed equivalent capability facets.

Semantic desirability: align the same bounded concept while retaining requirement/outcome context.
Operational benefit: exact joins and consistent explanations.
Governance cost: owners, reviewers, definition releases and mapping approval.
Coverage risk: source semantics without an equivalent stay unmapped.
Migration risk: retain opaque legacy/source identities and use explicit additive adapters.

Source/business identities still preserved separately: YES.

A role requirement can include a capability plus level/context, credentials or non-learning conditions. Its whole object is never declared equivalent to a capability ID. Likewise a course outcome may contain multiple capability facets or none.

## 7. Course Learning Outcome Layer

Required: YES for outcome-derived enrichment; OPTIONAL structured outcome records for directly authored, evidence-backed capability claims with equivalent provenance.

Reason: distinguish actual source outcomes/behaviors from topic labels and professional capability definitions.

Relationship to CourseCapabilityProfile: source outcome evidence -> reviewed facet mapping -> approved coverage claim -> profile projection.

Many outcomes can support one capability; one outcome can support multiple capabilities only through separately evidenced/reviewed facets. An outcome may remain unmapped. No synthetic learning outcome must be fabricated merely to satisfy this architecture.

V1 captures only declared source outcomes, evidence locators, source versions, behaviors/context and review state. It does not require lesson content, assessments or a full instructional ontology.

## 8. Architecture Option A

SINGLE SHARED CANONICAL NAMESPACE

Assessment: useful resolved concept identity, insufficient as direct replacement for all source semantics.
Benefits: simple exact joins and common definitions.
Risks: semantic forcing, centralized dumping ground and lost business context.
Migration: high if source IDs replaced; safer with adapters.
Recommendation impact: 01B_INPUT_ADAPTER_CHANGE.
Decision: PARTIAL.

Not selected alone because current identities have different meanings, not merely different spellings.

## 9. Architecture Option B

COURSE OUTCOMES -> GOVERNED CAPABILITY MAPPING

Assessment: solves source evidence/traceability but leaves target namespace ownership and domain extension unresolved.
Benefits: many-to-many mapping and retained unmapped outcomes.
Risks: review cost, mapping proliferation and ungoverned target vocabulary.
Migration: additive outcomes/mapping provenance.
Recommendation impact: 01B_INPUT_ADAPTER_CHANGE.
Decision: PARTIAL.

## 10. Architecture Option C

SHARED CORE + DOMAIN CAPABILITY PACKS

Assessment: solves owned extension and immutable definitions but does not establish what a course develops.
Benefits: explicit domain owner, release/version/dependency governance.
Risks: fragmentation, duplicate capabilities, normalization-pack confusion and topic promotion.
Migration: explicit release bindings; no automatic import of extraction entries.
Recommendation impact: 01B_INPUT_ADAPTER_CHANGE.
Decision: PARTIAL.

## 11. Hybrid Architecture

OUTCOMES + DOMAIN PACKS

Assessment: addresses both source-semantic validity and governed canonical identity.
Benefits: source lineage, approved domain extension, unmapped retention and pure exact-ref engine.
Risks: extra approval/provenance layer and target-specific scope validation.
Migration: MEDIUM; additive sidecars/projections, historical artifacts retained.
Recommendation impact: 01B_INPUT_ADAPTER_CHANGE.
Decision: ACCEPT.

Qualitative comparison, not a measured benchmark:

| Criterion | A | B | C | Hybrid |
|---|---|---|---|---|
| Semantic correctness | MODERATE | STRONG | MODERATE | STRONG |
| Traceability | WEAK | STRONG | MODERATE | STRONG |
| Governance | MODERATE | MODERATE | STRONG | STRONG |
| Domain extensibility | MODERATE | MODERATE | STRONG | STRONG |
| Course coverage | WEAK | STRONG | MODERATE | STRONG |
| Role alignment | MODERATE | STRONG | STRONG | STRONG |
| Implementation simplicity | STRONG | MODERATE | MODERATE | WEAK |
| Migration simplicity | WEAK | MODERATE | MODERATE | MODERATE |
| Recommendation compatibility | STRONG | STRONG | STRONG | STRONG |
| Explainability | MODERATE | STRONG | MODERATE | STRONG |
| Resistance to forcing | WEAK | STRONG | MODERATE | STRONG |

No numeric weights or promised semantic coverage increase.

## 12. Chosen Architecture

Decision: OPTION_D_HYBRID_OUTCOMES_PLUS_DOMAIN_PACKS.

Reason: repository evidence requires preserving requirement/outcome identity, development evidence and exact canonical matching; owned capability packs provide domain extension without treating the bounded CV taxonomy as universal.

Why alternatives alone were not selected: A collapses source semantics; B lacks namespace/domain governance; C lacks source development evidence. The hybrid implements only minimal contracts/adapters in stages, not a complete ontology.

## 13. Canonical Capability Identity

Identity format: capability:<namespace_key>:<semantic_key>.
This is grammar only; no real namespace or capability ID is allocated.

Each key starts with a lowercase ASCII letter and contains lowercase ASCII letters/digits/underscore. Colon separates fields; @ is not part of the ID.

Global uniqueness: unique namespace/semantic key plus one approved owner per namespace. Review semantic duplication across different namespaces too.
Labels separate from identity: YES.
Version embedded in identity: NO.

Rename behavior: label/editorial change preserves ID; ID key remains immutable.
Deprecation behavior: tombstone retained; no new binding to a deprecated definition/release.
Replacement behavior: explicit replacement relation and reviewed mappings; no automatic redirect/equality.

Owner transfer changes audited owner metadata, not namespace/identity. A pack reusing another domain's definition references the original ID under an exact dependency; it does not mint a duplicate.

## 14. Domain Pack Design

Required: YES, capability definition packs.
Pack identity: independent stable pack ID; canonical namespace owner remains explicit.
Versioning: immutable exact release version/checksum.
Lifecycle: DRAFT -> ACTIVE -> DEPRECATED; same deprecated release cannot reactivate.
Owner: named namespace/domain capability owner, independent reviewer and explicit release approver.
Dependencies: exact acyclic release dependencies; one defining owner per capability.
Collision handling: syntactic uniqueness plus semantic overlap/duplication review.

Pack release contains: identity/version, owner, domain scope, definitions/revisions/digests, included/excluded semantics, evidence expectations, aliases/languages, dependencies, checksum and approval refs.

CapabilityPack, existing DomainKnowledgePack and SemanticPolicy are linked but distinct:

- CapabilityPack owns canonical definitions.
- DomainKnowledgePack continues to provide normalization/hints.
- SemanticPolicy governs interpretation/resolution.

Current SemanticPolicy has a single normalization-pack binding. Proposed SemanticResolutionContext separately pins that unchanged policy binding, mapping policy and capability-pack releases. This design does not assume current schema already supports capability packs or silently generalize its cardinality.

## 15. Mapping Contract

Source namespaces: role requirement facet, course outcome facet, candidate evidence-backed concept, provider/external taxonomy or occupation-standard concept.
Target: canonical capability ref plus exact definition/pack release.

Mapping object: mapping ID/version; source namespace/ref/version/kind/checksum; source locators/evidence; target ref/definition revision/pack version/checksum; type; source/target scope; provenance; mapping-policy version; reviewer/time/rationale; review state; lifecycle; superseded mapping ref.

Mapping types: EXACT only in V1.
Evidence required: YES.
Provenance required: YES.
Human approval required: YES.
AI can author authoritative mapping: NO.

EXACT means reviewed equivalence of a source capability facet/concept to a target definition. It does not mean an entire requirement/outcome equals that definition, and it does not convert related topics into capabilities.

BROADER_THAN, NARROWER_THAN and RELATED_TO are deferred and never emit recommendation equality. Aliases are approved same-concept labels only, language/context/release scoped.

A separate coverage claim must establish course development/coverage behavior and context. EXACT concept mapping alone is insufficient for course eligibility. Narrow coverage cannot silently satisfy a broader role target.

Approval model: PROPOSED -> REVIEWED -> APPROVED or REJECTED. APPROVED is a semantic review decision; ACTIVE is a separate lifecycle activation after dependency validation. AI confidence/code enum labels cannot activate. Human-approved reusable rules may propose exact mappings, but instantiated evidence and approval remain required.

Source edits invalidate live bindings until a new version is reviewed. Historical mappings remain readable.

## 16. Capability Lifecycle

States: DRAFT, ACTIVE, DEPRECATED.

DRAFT usage: experimental/draft artifacts only; never eligible recommendation input.
ACTIVE usage: approved bounded definition under an active exact pack/policy context; not a verified learner state.
DEPRECATED usage: historical reads/replay only; no new recommendations or bindings.

Activation authority: proposed named namespace/domain owner plus independent semantic reviewer; explicit release approver records the validated event. Actual authority assignments are required before production activation and are not assigned by this design.

RETIRED is deferred; DEPRECATED plus a permanent tombstone covers minimal V1. Active definitions/releases are immutable. Same identity may persist through editorial revisions; changed operational meaning requires a new identity.

## 17. Role Identity Model

RoleRequirement keeps business/source identity: YES.
Canonical capability ref: optional reviewed facet binding in an additive sidecar, scoped to role profile/version and requirement.

Relationship: one requirement may reference multiple capability facets while retaining behavior, level, context, modality and logical constraints. Credential/non-learning conditions do not become capability refs merely to make recommendations possible.

Never equate requirement.id with capability_ref.

## 18. LearningNeed Identity Model

Requirement identity retained: YES.
Canonical capability identity retained: YES, separately when an approved binding exists.

Relationship: retain current competency.id semantics and source requirement/gap/analysis provenance; attach canonical facet bindings in a separate projection/context.

Learning eligibility remains authoritative. Unsupported, verification-only or non-learning needs cannot become learning targets simply because a capability mapping exists. No mutation to learner assessed/verified state follows mapping or course completion.

## 19. Course Identity Model

Course source identity: provider namespace + stable UUID, or frappe_lms source document ref.
Learning outcome identity: course-scoped source outcome ref/version/checksum; distinct from capability ID.
Canonical capability identity: approved source-facet mapping under an exact definition release.

CourseCapabilityProfile role: governed projection/export of approved evidence-backed coverage claims. Evidence and mapping/claim approval records own binding truth; profile ACTIVE remains a separate release gate.

Directly authored evidence-backed capability claims can use the same mapping/coverage provenance without fabricated outcomes. Current CourseCapabilityProfile shape is preserved; future exact pack/mapping/coverage pins initially belong in sidecar resolution/projection contracts. Any later public schema change needs its own authorized ADR/version.

## 20. Unmapped Semantics

Behavior when clear source semantics have no canonical capability: UNMAPPED_SEMANTIC with source evidence retained.
Forced nearest match: NO.
Stored as unmapped: YES, conceptually in future source-evidence records.
Governance action: record gap/proposal evidence, not automatic taxonomy expansion.
Recommendation eligible: NO for the unmapped semantic.

A partially mapped course may expose only approved scoped claims. A completely unmapped course stays ExternalCourse/evidence with no fabricated non-empty profile. No unknown is converted to level zero or absence of ability.

## 21. New Capability Proposal Policy

Who can propose: named domain/source stewards, reviewers or owners; AI can produce untrusted draft proposals only.

Evidence threshold: documented business need plus at least two independently authored requirements/outcomes across sources, or an authoritative standard plus independent internal use. Include scope, exclusions, evidence expectations and duplication/collision review. This is a proposed V1 gate, not a claim that existing artifacts meet it.

Who approves: namespace/domain owner and independent semantic reviewer before immutable release.
Single course sufficient: NO.

Workflow: observed unmapped semantic -> evidence-backed proposal -> domain review -> collision check -> definition/exclusions -> approval -> pack release -> mapping activation.

No new capability proposed or created in this milestone.

## 22. Recommendation Engine Impact

01B classification: 01B_INPUT_ADAPTER_CHANGE.
Reason: future upstream adapters resolve governance and scope, then supply compatible exact refs to the existing pure engine.
Exact match retained: YES.
Engine changes required now: NO.

Adapter gate: trusted source/version -> explicit target facets -> active approved mappings/definitions/packs -> source freshness -> target-compatible coverage/context -> exact refs -> unchanged engine.

V1 pins one identical definition/pack release per participating capability across target/candidates. Cross-release mismatch fails closed until an explicit compatibility/adaptation decision exists; never lookup latest.

01B FULL_COVERAGE means all supplied target refs matched, not all behaviors covered or competence verified. Because engine inputs lack behavioral/AND-OR scope, upstream adapters must prefilter insufficient coverage and preserve constraint decisions in provenance. Unrepresentable alternatives or unresolved mandatory scope fail closed before 01B; they must not be flattened into a simpler target.

## 23. COURSE-REC-01C Constraints

Can 01C proceed: YES_WITH_CONSTRAINTS.

Safe to persist now: exact request/result, algorithm/version, course/profile refs/versions, decision details, warnings/exclusions and need/path/gap/requirement trace refs. Preserve caller-supplied resolution provenance when available; mark legacy ungoverned context explicitly.

Must not freeze yet: universal extraction-taxonomy authority, requirement-ID equality, experimental DRAFT approval, latest-release defaults or inferred namespace mappings.

Future historical provenance pins source/profile/outcome version/checksum, capability ref, definition revision/digest, pack release/checksum, mapping/policy version, applicable role policy, algorithm, resolution context and lifecycle eligibility events/time. Exact retained immutable records avoid duplicating an entire taxonomy snapshot.

No raw CV/JD text, secret or model prompt enters recommendation audit. Replaying a past result does not authorize a fresh recommendation under deprecated dependencies.

## 24. SkillsCommons Enrichment Path

Future flow:

ExternalCourse -> declared outcome/direct evidence -> reviewed capability facets -> approved EXACT mappings -> reviewed coverage scope -> active definition/pack -> approved profile projection -> target-specific adapter -> 01B.

Package parsing required immediately: NO.

When package inspection becomes justified: after approved vocabulary/mapping rules exist, selected unresolved outcomes need evidence that metadata lacks. Do not parse a package merely because a canonical concept is absent.

Project-management evidence can be re-bound under future approved governance; the physical-therapy leadership claim remains ambiguous and unapproved until adequate evidence/review. Neither existing DRAFT is auto-activated.

## 25. Migration Impact

Current professional_capability_core@0.1: KEEP_AS_IS for CV extraction; no automatic canonical-core promotion.
Two existing SkillsCommons DRAFT profiles: EXPERIMENT_ONLY; preserve original evidence/status. Future approved projections use new versions/refs.
Role requirement IDs: KEEP_AS_IS; ADAPT through additive facet bindings.
LearningNeed identities: KEEP_AS_IS; ADAPT separate canonical refs.
Candidate evidence/verification: KEEP_AS_IS.
01B fixtures/results: KEEP_AS_IS; future adapter fixtures added separately.
Existing normalization packs: KEEP_AS_IS; no conversion to CapabilityPack.

Migration class: MEDIUM.

No migration executed. Future compatibility manifests use exact legacy source namespace/ref/version; prefix stripping, label normalization and implicit aliases cannot serve as migration. First produce read-only impact/dry-run evidence, then opt-in new projections; no historical backfill or audit rewrite.

## 26. Backward Compatibility

Contracts preserved: 01B exact equality/determinism; CourseCapabilityProfile lifecycle/shape; role/need source provenance; provider UUID/course refs; extraction normalization; learner verification boundary; historical result reads.

Contracts requiring adapter: role/need/path target facets; course coverage projection; canonical resolution/provenance.

Contracts requiring redesign: none in the pure engine now. A new sidecar governance contract is proposed; future changes to existing public schemas or SemanticPolicy composition require an explicit later ADR.

Existing catalog/recommendation opaque fixture refs remain valid for pure unit tests, but do not become production governance entries.

## 27. Deferred Features

Hierarchy/subsumption; broader/narrower/related inference; external standard integration; fuzzy/embedding similarity; ontology reasoning; AI automatic mapping/activation; automatic capability creation; package parsing and outcome generation; RETIRED lifecycle; full taxonomy snapshots.

No external framework was researched or integrated. Future standards remain separately versioned source namespaces with governed crosswalks, not canonical IDs by default.

## 28. Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| Semantic dumping ground | HIGH | Business need, bounded scope, owner and independent review |
| Duplicate capabilities across packs | HIGH | Namespace ownership and semantic collision review |
| Narrow outcome becomes broad capability claim | HIGH | Separate EXACT facet and coverage-scope gates |
| Opaque engine refs lose scope | HIGH | Upstream target-specific filtering; ref coverage never mastery |
| Pack fragmentation | MEDIUM | Stable IDs, exact pinned release per context |
| Stale mappings | HIGH | Source version/checksum and re-review |
| Mapping explosion | MEDIUM | Atomic facets and reviewed reusable rules |
| AI authority overreach | HIGH | Draft proposals and explicit human approval |
| Policy/normalization/definition packs conflated | HIGH | Separate contracts and explicit composition pins |
| Legacy breakage | HIGH | Sidecars/new versions, historical identities preserved |

## 29. Implementation Slices

| Slice | Purpose | Acceptance condition |
|---|---|---|
| 01A.3D-1 | Namespace + dual-identity contracts | Stable grammar; source IDs preserved; unknown/collision rejected; no catalog expansion |
| 01A.3D-2 | Capability/pack lifecycle | Immutable ACTIVE; exact dependencies; DRAFT ineligible; deprecated replay; owner/reviewer audit |
| 01A.3D-3 | Outcome/facet/mapping/coverage contracts | Approved EXACT only; topic/related/narrower proposals cannot emit eligible refs; unmapped retained |
| 01A.3D-4 | Role/Need/target adapter | Requirement/gap trace retained; constraints/eligibility preserved; missing mapping fails closed |
| 01A.3D-5 | Course projection/eligibility adapter | Active governed dependencies and scope-compatible evidence; engine/schema unchanged |
| 01A.3D-6 | Migration/compatibility | Dry-run evidence; explicit legacy mappings; no backfill/activation; historical replay retained |

These are bounded future slices, not executed plans or permission to implement. Actual owners/reviewers must be assigned before activation.

## 30. Evidence Created

DOCS: docs/research/COURSE-REC-01A-3C-CAPABILITY-NAMESPACE-TAXONOMY-GOVERNANCE-DESIGN.md
EVIDENCE: test/results/course-rec-01a-3c/

Includes preflight, entity definitions, identity flow, role/course governance, all four architecture options, qualitative comparison, namespace/lifecycle/mapping/versioning designs, migration/recommendation impact, slices, risks, decision, summary and validation.

Production code: NONE.
Tests changed: NONE.
LMS: NONE.

Validation covers JSON parsing/cross-artifact consistency, 32 report sections, existing-source path references, Git diff/status preservation and before/after byte checksums. Broad test/lint results are not newly claimed for documentation-only work. No documentation linter configured for this artifact was discovered.

Graphify queries served as read-only navigation. Truncated graph results were not architecture authority; actual source/tests/ADRs were inspected. Existing graph and prior evidence were not modified.

Brainstorming shaped the option comparison and concrete design. The explicit user scope permits this design artifact and forbids implementation/commit, so no implementation handoff or commit is performed.

## 31. Final Decision

Architecture selected: OPTION_D_HYBRID_OUTCOMES_PLUS_DOMAIN_PACKS.
Shared canonical identity: YES, approved concept facets only.
Domain packs: YES, distinct capability definition packs.
Course outcome layer: YES for outcome-derived claims, direct-claim compatibility retained.
Governed mappings: YES.
01B changes required now: NO.
01C may proceed: YES_WITH_CONSTRAINTS.
Ready for bounded implementation: YES, contracts first; production activation still requires real governance assignments and approved releases.

Overall decision: READY_FOR_CAPABILITY_GOVERNANCE_IMPLEMENTATION.

This is the recommended architecture from this design milestone; it is not a claim that production taxonomy governance is already implemented or approved.

## 32. Git Status

Core-AI: all pre-existing changes preserved; this milestone adds only the research design report and test/results/course-rec-01a-3c/.
LMS: clean, same branch/HEAD.

STOP.
No 01A.3D implementation, taxonomy/course-profile/engine changes, package parsing, commit or push.
