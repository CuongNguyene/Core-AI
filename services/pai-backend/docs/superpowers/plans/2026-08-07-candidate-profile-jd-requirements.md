# CandidateProfile Semantics and JD Requirement Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task.

**Goal:** Preserve CV evidence semantics and make versioned JD requirements the safe input to role-profile authoring.

**Architecture:** Add deterministic CV mapping in the extraction boundary and a versioned JD adapter that normalizes v2 and accepted legacy profiles into authoring requirements. Keep persistence, review, and approval state machines unchanged except for source metadata and findings.

**Tech Stack:** Python 3.13, Pydantic v2, SQLAlchemy 2, pytest.

## Global Constraints

- Accepted legacy JD profiles may be adapted, but drafts are marked `legacy` and start `DRAFT`.
- Do not infer missing modality, target level, observable behavior, constraints, priority, or logical semantics.
- Blocking compatibility findings prevent `PROVISIONAL` and `ACTIVE`.
- Do not change parser, orchestration, locator, review workflow, Evidence Graph persistence, or capability-analysis decisions.

### Task 1: CandidateProfile semantic builder

**Files:**
- Create or modify `backend/app/extraction/profile_builder.py`.
- Modify `backend/app/extraction/profile.py` and `backend/app/extraction/evidence.py` only for backward-compatible fields.
- Modify `backend/app/extraction/graph_merge.py` to delegate legacy construction.
- Test `backend/tests/test_candidate_profile_builder.py`.

- [ ] Add failing tests for evidence-context mapping, project/publication routing, multi-context skill merging, unknown claims, and conservative normalization.
- [ ] Run focused tests and confirm failures are caused by missing semantic behavior.
- [ ] Implement deterministic mapping and claim routing with source locator, excerpt, confidence, original evidence type, and derived context.
- [ ] Preserve legacy profile parsing and existing relation-merge behavior.
- [ ] Run focused CV tests and existing graph/capability tests.

### Task 2: JD requirement v2 contract and prompt

**Files:**
- Modify `backend/app/extraction/schemas.py`.
- Modify `backend/app/extraction/prompts.py`.
- Test `backend/tests/test_jd_requirement_contracts.py` and existing contract tests.

- [ ] Add failing schema tests for atomic requirements, optional unknown semantic fields, provenance enum, findings, and evidence boundaries.
- [ ] Add failing registry/prompt assertions proving the requirement contract is not `JDExtractionOutput`.
- [ ] Implement `JDRequirementExtractionOutputV2`, schema version, prompt contract, and registry wiring.
- [ ] Keep old `JDExtractionOutput` readable for historical profiles.

### Task 3: Versioned JD compatibility adapter

**Files:**
- Create `backend/app/role_profile_authoring/source_adapter.py`.
- Modify `backend/app/role_profile_authoring/schemas.py` for source metadata/findings if needed.
- Test `backend/tests/test_role_profile_source_adapter.py`.

- [ ] Add failing tests for v2 happy path, accepted legacy happy path, missing locator/provenance blocking, and no semantic inference.
- [ ] Implement `adapt_jd_profile(source)` returning normalized requirements, source schema/version, and findings.
- [ ] Reject non-accepted/superseded sources through the existing repository guard.
- [ ] Ensure legacy outputs always yield `DRAFT` source metadata and safe findings.

### Task 4: RoleProfileDraft integration

**Files:**
- Modify `backend/app/role_profile_authoring/repository.py`.
- Modify `backend/app/role_profile_authoring/quality_gate.py` if findings need merging.
- Modify `backend/tests/test_role_profile_authoring_repository.py`.

- [ ] Add failing tests asserting draft source metadata, legacy findings, blocked approval, and reviewer-enriched approval.
- [ ] Replace direct `JDExtractionOutput` bucket mapping with the adapter.
- [ ] Preserve current lifecycle and active/provisional gate rules.
- [ ] Keep audit safe: IDs, versions, schema identifiers, finding codes only.

### Task 5: Regression verification

**Files:** no new production files.

- [ ] Run all focused extraction and authoring tests.
- [ ] Run `ruff check`, `mypy` for touched modules, and the full `pytest` suite from `backend`.
- [ ] Inspect diff for forbidden raw data or lifecycle changes.
