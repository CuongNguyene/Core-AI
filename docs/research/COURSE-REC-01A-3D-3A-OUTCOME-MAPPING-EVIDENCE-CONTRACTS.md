# COURSE-REC-01A.3D-3A — OUTCOME & MAPPING EVIDENCE CONTRACTS

## Status

COMPLETE — bounded source-side semantic contracts implemented. No canonical authority, mapping activation, profile projection, persistence, API, migration, LMS change, commit, or push.

## 1. Repository

Core-AI path: `/Users/mac/Developers/work/LMS/Core-AI`
Branch: `feat/deterministic-ai-course-planning-workspace`
HEAD: `a078526ab7ea38327fdeece142aba325f3de3352`
Working tree: dirty before and after this slice.
Pre-existing changes: config/settings edits and untracked COURSE-REC-01A/01B, 3D-1/3D-2, graphify, integration and earlier evidence artifacts; preserved.
Concurrent 3D-2 changes detected: YES — its definition/pack/resolution files and tests were already present and were not edited.

LMS path: `/Users/mac/Developers/work/LMS/lms`
Branch: `feat/learning-operations-phase-1`
HEAD: `289174af73ad648a2e42c7d55a2273d815790235`
Working tree: clean, unchanged.

## 2. 3D-1 Dependency

CanonicalCapabilityRef reused: YES
SourceSemanticRef reused: YES
CapabilityIdentityPair reused: NOT_NEEDED — proposal must preserve scope/evidence/method/reviewer data in addition to the identity pair.
3D-1 modified: NO

The current identity module defines SourceSemanticKind, including COURSE_LEARNING_OUTCOME, COURSE_DIRECT_CLAIM, ROLE_REQUIREMENT and LEARNING_NEED_COMPETENCY. Those existing enum values are reused; no enum or identity change was needed.

## 3. Module Placement

Package: `app.capability_governance`
Files: `outcomes.py`, `evidence.py`, `mapping.py`; dedicated tests in `test_capability_outcome_mapping_contracts.py`.
Domain-neutral mapping contracts: YES
Circular dependency: NO

New modules import only the 3D-1 identity types and the sibling SemanticEvidence value. They do not reference capability definitions, packs, lifecycle, resolution, or taxonomy registries. The existing package initializer eagerly exports 3D-2 symbols; normal Python submodule import executes that initializer. It was left unchanged under the ownership boundary; no 3D-2 symbol is consumed by the new contracts.

## 4. CourseLearningOutcome

Type/class: `CourseLearningOutcome`
Identity type: `SourceSemanticRef` with `COURSE_LEARNING_OUTCOME` kind
Fields: outcome_ref, course_ref, statement, source_locator. Source version remains in outcome_ref. Bounds: course_ref 512, statement 4,000, locator 2,048 characters.
Course identity separate: YES
Canonical capability separate: YES
Topic auto-promoted to outcome: NO

The model requires an explicitly supplied outcome identity, course identity, statement and locator. It contains no provider topic/title conversion or classification function. `LearningOutcomeAssertion` elsewhere represents learner assessment results, not course-authored intended outcomes, so it is not a conflicting contract.

## 5. Semantic Evidence

Type/class: `SemanticEvidence`
Fields: source_ref, source_locator, evidence_text, evidence_kind.
Source ref required: YES
Source locator required: YES
Evidence text required: YES
Bounded: YES — excerpt maximum 500 characters, matching existing extraction and SkillsCommons evidence conventions; locator maximum 2,048.

Evidence kinds are descriptive source forms, not truth/strength judgments. No full course file, package, HTML blob, or hidden reasoning is stored.

## 6. Mapping Proposal

Type/class: `CapabilityMappingProposal`
Source ref: required `SourceSemanticRef`
Target type: `CanonicalCapabilityRef`
Mapping type: `MappingType.EXACT` only
Supported mapping types: EXACT
Evidence required: YES, immutable nonempty tuple
Proposer required: YES
Proposal implies authority: NO

Proposal ID and proposer ref are bounded to 256 characters; optional rationale is bounded to 1,000. Target validation is syntax-only. Proposal fingerprint is deterministic SHA-256 over every serialized proposal field, including canonicalized evidence and optional rationale.

## 7. EXACT Semantics

Definition: reviewed equivalence of the source semantic facet to the canonical capability concept within the proposal's declared scope. It is not equality of the entire source object and the target capability.
Applies to bounded capability facet: YES
Entire source aggregate collapsed: NO

## 8. Mapping Scope

Type/field: `MappingScope` / `mapping_scope`
Supported V1 scopes: CAPABILITY_FACET, OUTCOME_CAPABILITY_FACET, DIRECT_CAPABILITY_CLAIM
Purpose: state which bounded facet an EXACT proposal covers; preserve outcome/requirement/direct-claim context.

## 9. Proposal Method

Supported methods: MANUAL, GOVERNED_RULE, AI_ASSISTED
AI authoritative: NO
Confidence affects authority: NO — confidence is intentionally omitted.

AI_ASSISTED is only method provenance on a proposal; it performs no model call and confers no review or authority.

## 10. Review Contract

Type/class: `CapabilityMappingReview`
Decisions: APPROVE, REJECT, UNCERTAIN
Reviewer required: YES
Independent from proposer: YES, checked by `validate_mapping_review_for_proposal`
APPROVE creates active mapping: NO

Review pins both proposal_id and proposal_fingerprint. The validator rejects ID mismatch, content fingerprint mismatch, and reviewer/proposer identity equality. Fingerprinting is an integrity pin, not a signature or proof of reviewer authentication.

## 11. Unmapped Semantic

Type/class: `UnmappedSemantic`
Valid without canonical ref: YES
Reasons: NO_CANONICAL_MATCH, INSUFFICIENT_EVIDENCE, MAPPING_REJECTED, DEFERRED_GOVERNANCE
Forced nearest match: NO
Automatic capability creation: NO

Reasons are caller-supplied records, not computed conclusions. In particular, this module does not decide that no canonical match exists.

## 12. Authority Boundary

Syntactically valid target required: YES
Registered target required in 3D-3A: NO
ACTIVE pack required in 3D-3A: NO
ACTIVE capability required in 3D-3A: NO
Future authority integration: 3D-3B

The synthetic ref `capability:test_unregistered:synthetic_capability` is accepted as a proposal target in unit tests without consulting any registry. It is not an authoritative binding.

## 13. Direct Claim Compatibility

Fake outcome required for direct claim: NO
Direct evidence-backed path representable: YES — `COURSE_DIRECT_CLAIM` source ref plus DIRECT_CAPABILITY_CLAIM scope and evidence.
Projection implemented: NO

## 14. Role / LearningNeed Compatibility

Role requirement identity preserved: YES — source ref retains requirement ID/version.
LearningNeed identity preserved: YES — source ref remains distinct and requirement-backed.
Adapters implemented: NO

## 15. Course Compatibility

CourseCapabilityProfile changed: NO
Outcome-to-profile projection implemented: NO
Future projection possible: YES — 3D-3B/3D-5 may consume reviewed source-side contracts and separately validate capability authority/scope.

## 16. Parallel 3D-2 Boundary

3D-2 production models imported: NO directly by 3D-3A source modules; the pre-existing package initializer transitively imports/exports them as a Python package side effect.
3D-2 files modified: NO
Capability authority implemented: NO
Pack lifecycle implemented: NO

The package initializer was not edited because it belongs to the existing 3D-2 package boundary. The transitive initializer behavior is recorded as a packaging limitation; no definition/pack/resolution symbol is referenced by 3D-3A.

## 17. Negative Semantic Cases

Title → outcome blocked: PASS — no automatic conversion; a provenance-complete explicit record is required.
Subject → outcome blocked: PASS — no subject-to-outcome helper exists.
Outcome == capability blocked: PASS
Requirement == capability blocked: PASS
Review approval == authority blocked: PASS
Unknown canonical target authority not assumed: PASS
Nearest/fuzzy matching absent: PASS
Unmapped semantic accepted: PASS

## 18. Tests

3D-3A tests: `tests/test_capability_outcome_mapping_contracts.py` — 49 passed.
3D-1 regression: `tests/test_capability_identity_contracts.py` — included in combined run.
Catalog regression: fixture/schema/semantic-enrichment tests — included.
Recommendation regression: `tests/test_course_recommendation.py` — included.
Role/LearningNeed regression: role source adapter and LearningNeed/projection tests — included.
Total: 178 passed, 0 failed.

Combined command: `pytest tests/test_capability_outcome_mapping_contracts.py tests/test_capability_identity_contracts.py tests/test_course_catalog_fixtures.py tests/test_course_catalog_schemas.py tests/test_course_catalog_semantic_enrichment.py tests/test_course_recommendation.py tests/test_learning_need_profile.py tests/test_learning_need_projection_policy.py tests/test_role_profile_source_adapter.py tests/test_semantic_core_contracts.py -q`

## 19. Static Checks

Ruff format: PASS
Ruff: PASS
mypy: PASS — 3 changed source modules
JSON validation: PASS — 13 evidence files
Whitespace scan: PASS — changed source, tests, evidence; Markdown hard-break spacing allowed
git diff --check: PASS
Secret scan: PASS

## 20. Files Changed

DOMAIN: `app/capability_governance/{outcomes,evidence,mapping}.py`
TESTS: `tests/test_capability_outcome_mapping_contracts.py`
DOCS: this report; implementation plan `docs/superpowers/plans/2026-10-04-course-rec-01a-3d-3a-contracts.md`
EVIDENCE: `test/results/course-rec-01a-3d-3a/`

3D-2 FILES: NONE
COURSE PROFILE SCHEMA: NONE
ROLE/NEED SCHEMAS: NONE
PERSISTENCE: NONE
API: NONE
MIGRATIONS: NONE
LMS: NONE

## 21. Architecture Conformance

Matches 3C hybrid architecture: YES
Outcome layer supported: YES
Source identity preserved: YES
Canonical target separate: YES
Unmapped semantics preserved: YES
Governance authority deferred: YES

## 22. Known Limitations

- No taxonomy registry or 3D-2 authority resolution is consulted; 3D-3B must validate target registration/lifecycle and govern activation.
- No persistence, API, mapping lifecycle activation, course profile projection, role/need adapter, or recommendation integration is included.
- Source text truth, reviewer authentication, and provenance references are contract values; this layer does not authenticate actors or inspect the source document.
- The current eager `capability_governance.__init__` causes Python to load 3D-2 exports when importing a new submodule. It was not changed due 3D-2 ownership; 3D-3A code does not consume those exports.

## 23. 3D-3B Readiness

Outcome contract stable: YES
Evidence contract stable: YES
Mapping proposal stable: YES
Review contract stable: YES
Unmapped contract stable: YES
Ready to integrate with 3D-2 authority: YES — via a later explicit integration layer, not direct coupling here.
Actual blockers: none for source-side contracts; 3D-3B must handle exact proposal/review pins and the pre-existing package export boundary deliberately.

## 24. Final Decision

Outcome/evidence contracts usable: YES
Proposal/review boundary usable: YES
Authority boundary preserved: YES
Backward compatibility preserved: YES
Ready for 3D-3B after 3D-2: YES

Decision: **READY_FOR_3D_3B_INTEGRATION**

## 25. Git Status

Core-AI: existing worktree remains dirty with pre-existing changes and this slice's untracked modules/tests/docs/evidence. No files staged, committed, or pushed.
LMS: clean and unchanged.
