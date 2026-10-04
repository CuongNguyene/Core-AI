# COURSE-REC-01A.3D-3A Outcome & Mapping Evidence Contracts Implementation Plan

> **For agentic workers:** Execute natively in this Codex session, task by task, with TDD. Do not commit; that constraint is explicit in the source task.

**Goal:** Add pure, deterministic source-outcome, semantic-evidence, mapping-proposal/review, and unmapped-semantic contracts without granting canonical authority.

**Architecture:** Add focused `outcomes.py`, `evidence.py`, and `mapping.py` modules under `app.capability_governance`. Reuse only 3D-1 identity value objects; do not import or modify 3D-2 definition/pack/resolution modules. Keep source evidence and review records independent of capability activation, persistence, APIs, profile projection, and recommendation use.

**Tech Stack:** Python 3.13+, Pydantic v2, StrEnum, pytest, Ruff, mypy.

**Spec:** `/Users/mac/.codex/attachments/836d6462-28ae-4a77-8f83-54a549ae7ece/Pasted text.txt`

## Global Constraints

- Preserve 3D-1 `CanonicalCapabilityRef`, `SourceSemanticRef`, and `CapabilityIdentityPair` contracts unchanged.
- Support only EXACT mapping over a bounded capability facet.
- Require source identity, evidence, and proposer on every mapping proposal.
- A review decision never activates a mapping or proves target authority.
- Keep unmapped semantics valid without inventing canonical identities.
- Do not modify 3D-2, CourseCapabilityProfile, RoleRequirement, LearningNeed, recommendation, persistence, API, migrations, or LMS.
- Do not call a model, use embeddings/fuzzy matching, create production mappings, stage, commit, or push.

## Review Focus

- A course title/topic can be mistaken for an intended learning outcome: contract has no auto-conversion/classifier and negative tests represent topics without constructing outcomes.
- Review approval can be mistaken for canonical authority: proposal/review models contain no ACTIVE state or eligibility resolver.
- Existing DSpace enrichment contracts can be mistaken for the general contract: keep them unchanged and test a syntactically valid target that is absent from current taxonomy as a valid proposal.
- Duplicate evidence ordering can make equivalent proposals serialize differently: canonicalize evidence order and reject duplicate evidence identities deterministically.
- A direct course capability claim can be forced into a fabricated outcome: use `SourceSemanticKind.COURSE_DIRECT_CLAIM` and `DIRECT_CAPABILITY_CLAIM` scope.

## Existing-Contract Decisions

- Reuse 3D-1 source and canonical identity types, including the existing `SourceSemanticKind` enum (`COURSE_LEARNING_OUTCOME`, `COURSE_DIRECT_CLAIM`, `ROLE_REQUIREMENT`). No identity contract or enum change is needed. `CapabilityIdentityPair` is not needed because proposal fields must additionally retain scope, evidence, proposer, and method.
- No existing source-owned course outcome model was found. `LearningOutcomeAssertion` represents a learner's assessment result, not a course's intended outcome.
- Preserve existing evidence primitives and semantics: `SourceLocator`, `EvidenceItem`, `SemanticSourceLocator`, `CourseProvenance`, and DSpace-specific `CourseSemanticEvidence` remain untouched. They are extraction-, assessment-, or provider-specific and do not provide the required generic source-ref + evidence-kind + bounded-excerpt mapping contract.
- Bound user text fields consistently: outcome statement 4,000 characters (same ceiling as existing capability definitions), excerpt 500 (existing extraction and SkillsCommons semantic evidence ceiling), exact locator 2,048 (opaque locator allowance), and actor/proposal/review refs 256 (existing governance-ref convention). Optional rationale is at most 1,000. Document these limits in the research report.
- Do not edit `app.capability_governance/__init__.py`; it is part of the pre-existing 3D-2 package boundary. Tests and consumers import the new submodules directly.

## File Map

- Create `services/pai-backend/backend/app/capability_governance/outcomes.py`: immutable source-owned CourseLearningOutcome.
- Create `services/pai-backend/backend/app/capability_governance/evidence.py`: bounded SemanticEvidence and EvidenceKind.
- Create `services/pai-backend/backend/app/capability_governance/mapping.py`: EXACT proposal/scope/method, review decision, and UnmappedSemantic contracts.
- Create `services/pai-backend/backend/tests/test_capability_outcome_mapping_contracts.py`: focused behavior tests for all three modules and cross-boundary negative cases.
- Create `docs/research/COURSE-REC-01A-3D-3A-OUTCOME-MAPPING-EVIDENCE-CONTRACTS.md` and `test/results/course-rec-01a-3d-3a/*.json` evidence listed by the spec.
- Do not modify any existing production or test file, including any 3D-2 file.

---

### Task 1: Course Outcome and Source Evidence Values

**Files:** Create `outcomes.py`, `evidence.py`; test in `test_capability_outcome_mapping_contracts.py`.

**Interfaces:** `CourseLearningOutcome(outcome_ref: SourceSemanticRef, course_ref: str, statement: str, source_locator: str)`; `SemanticEvidence(source_ref: SourceSemanticRef, source_locator: str, evidence_text: str, evidence_kind: SemanticEvidenceKind)`. Source version stays in `SourceSemanticRef`; source locator is opaque/bounded; evidence excerpts use the repository's existing 500-character bound.

- [ ] Write tests first: valid outcome and evidence; missing refs/course/statement/locator; whitespace and over-limit excerpt rejection; outcome/source/canonical identities remain distinct; same value serializes deterministically; topic text alone is not converted by any helper.
- [ ] Run `UV_CACHE_DIR=/tmp/uv-cache-course-rec-3d3a uv run --offline pytest tests/test_capability_outcome_mapping_contracts.py -q`; expected RED because the modules/types do not exist.
- [ ] Implement frozen, strict Pydantic contracts using existing `SourceSemanticRef`; add no parsing, classification, or generation helpers.
- [ ] Rerun the focused tests; expected PASS.

### Task 2: Exact Proposal, Scope, and Review Records

**Files:** Create/extend `mapping.py`; add tests to the focused test file.

**Interfaces:** `CapabilityMappingProposal(proposal_id, source_ref, target_capability_ref, mapping_type=EXACT, mapping_scope, evidence, proposal_method, proposer_ref, rationale=None)`; proposal exposes a deterministic SHA-256 fingerprint of every proposal field. `CapabilityMappingReview(proposal_id, proposal_fingerprint, reviewer_ref, decision, rationale)` pins the exact proposal. `validate_mapping_review_for_proposal(proposal, review)` checks matching ID/fingerprint and reviewer/proposer independence without duplicating proposer_ref in the review. Mapping decisions are APPROVE/REJECT/UNCERTAIN. Proposal evidence is nonempty, sorted by canonical JSON of the full semantic value, and exact duplicate values are rejected. No confidence field is introduced.

  - [ ] Write tests first: valid proposal for synthetic `capability:test_unregistered:synthetic_capability` without taxonomy lookup; missing source/target/evidence/proposer; invalid target syntax; non-EXACT mapping unavailable; the three bounded scopes; each proposal method including AI_ASSISTED as proposal-only; duplicate/order-varied evidence behavior; deterministic fingerprint changes when proposal content changes; each review decision; review ID/fingerprint mismatch; reviewer independence; review does not change proposal or add ACTIVE/authority state.
- [ ] Run the focused test file and confirm expected RED for missing contracts.
- [ ] Implement pure immutable values. Import only `CanonicalCapabilityRef`, `SourceSemanticRef`, and `SemanticEvidence`; do not import 3D-2 authority types or taxonomy registries.
- [ ] Rerun focused tests; expected PASS.

### Task 3: First-Class Unmapped Source Semantics and Compatibility Boundaries

**Files:** Extend `mapping.py`; add tests to the focused test file.

**Interface:** `UnmappedSemantic(source_ref, evidence, reason, provenance_ref=None)` with bounded reasons NO_CANONICAL_MATCH, INSUFFICIENT_EVIDENCE, MAPPING_REJECTED, and DEFERRED_GOVERNANCE. Its evidence is the same canonical immutable tuple contract used by proposals. It has no canonical target field and requires source identity plus evidence.

  - [ ] Write tests first: valid unmapped record without canonical ref; each allowed reason; invalid/nearest-match reason rejected; absent evidence/source rejected; canonicalized immutable evidence tuple and full-value duplicate rules; no capability or outcome is generated; direct source claim can be represented with `SourceSemanticKind.COURSE_DIRECT_CLAIM` + DIRECT_CAPABILITY_CLAIM without constructing CourseLearningOutcome; role requirement source identity remains separate; LearningNeed and course-profile contracts remain unchanged.
- [ ] Run the focused test file and confirm expected RED for the unmapped contract.
- [ ] Implement the minimal immutable record and bounded reason enum; no taxonomy lookup or promotion functions.
- [ ] Rerun focused tests; expected PASS.

### Task 4: Regression, Documentation, and Evidence

**Files:** Create the 3D-3A research report and JSON evidence directory only.

- [ ] Run focused test suite plus existing `test_capability_identity_contracts.py`, catalog fixtures/schemas/semantic enrichment, course recommendation, LearningNeed/projection, role source adapter, and semantic-core tests.
- [ ] Run Ruff format check, Ruff lint, mypy on changed modules, JSON parsing, secret scan, and `git diff --check`; separately inspect untracked new files for trailing whitespace.
- [ ] Write the requested report distinguishing source evidence from authority and documenting reuse/non-reuse decisions, direct-claim path, future role/course compatibility, and AI proposal-only boundary.
- [ ] Create the requested 13 JSON artifacts with synthetic test_core-style identities only; no production semantic mappings.
- [ ] Confirm only new 3D-3A production/tests/report/evidence files were added by this milestone; Core-AI pre-existing changes remain untouched; LMS remains clean; nothing staged/committed/pushed.

**Verification commands:** run from `services/pai-backend/backend` with `UV_CACHE_DIR=/tmp/uv-cache-course-rec-3d3a uv run --offline` for pytest/Ruff/mypy. Validate evidence JSON from repository root with `python3 -c "import json,pathlib; p=pathlib.Path('test/results/course-rec-01a-3d-3a'); [json.loads(f.read_text()) for f in p.glob('*.json')]; print('valid')"`.

**Expected handoff:** all scoped tests/static checks pass; exact task report format completed; status is COMPLETE only if every success criterion is evidenced. No commit or push.
