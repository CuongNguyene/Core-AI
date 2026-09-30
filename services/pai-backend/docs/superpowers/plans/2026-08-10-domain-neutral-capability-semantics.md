# Domain-neutral Capability Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace IT/AI-specific capability matching with a domain-neutral,
versioned semantic core and pluggable packs while preserving PREVIEW governance.

**Architecture:** `EvidenceIndex` remains the immutable source projection.
Typed adapters create domain-neutral requirement/evidence semantics; packs add
only source-grounded normalization hints; the core evaluates retrieval,
compatibility, eligibility, coverage, and assessment. Every persisted assessment
is derived from the same retrieval candidates that are exposed for diagnostics.

**Tech Stack:** Python 3.13, Pydantic, SQLAlchemy async, Alembic, pytest.

## Global Constraints

- PREVIEW only; do not add or invoke OFFICIAL analysis.
- Do not create VERIFIED capability, a final competency decision, readiness
  score, future-track score, learning objective, or learning path.
- Do not mutate accepted extraction profiles or historical portfolios.
- Unknown source semantics remain unknown; no LLM or world-knowledge inference.
- Retrieval and eligibility stay separate; missing evidence never proves absence.
- Pack selection is explicit, versioned, deterministic, and fail-closed.
- Existing portfolio API fields remain backward compatible.

---

### Task 1: Define semantic contracts and generic evidence/context invariants

**Files:**
- Create: `backend/app/capability_analysis/semantic_core/contracts.py`
- Create: `backend/app/capability_analysis/semantic_core/adapters.py`
- Create: `backend/tests/test_semantic_core_contracts.py`
- Modify: `backend/app/capability_analysis/evidence_index.py`

**Interfaces:**
- Produces `RequirementSemantics`, `EvidenceSemantics`, `SemanticConstraint`,
  and source-grounded adapters from `RoleRequirement`/EvidenceIndex evidence.
- Does not consume a domain pack or emit an assessment.

- [ ] Write RED tests proving mention is not demonstrated usage, project is not
  employment, education is not work, credential is not practice, one concept
  can keep multiple observations, and missing evidence is not absence.
- [ ] Run `UV_CACHE_DIR=/private/tmp/pai-uv-cache uv run pytest tests/test_semantic_core_contracts.py -q` and confirm RED.
- [ ] Implement immutable contracts and adapters that preserve locator,
  original evidence type, source kind, context, participation, confidence, and
  unresolved fields without parsing unapproved facts.
- [ ] Run the focused contracts suite and confirm GREEN.
- [ ] Commit only this task's contracts/tests.

### Task 2: Implement generic participation and constraint compatibility

**Files:**
- Create: `backend/app/capability_analysis/semantic_core/compatibility.py`
- Create: `backend/tests/test_semantic_core_compatibility.py`
- Modify: `backend/app/capability_analysis/schemas.py`

**Interfaces:**
- Consumes `RequirementSemantics` and `EvidenceSemantics`.
- Produces `EvidenceCompatibility` with `eligible`, directness, rank and reason
  codes; assessment status remains outside this task.

- [ ] Write RED tests: participated/assisted is not owned/led; adjacent context
  does not satisfy required context; retrieved candidates can all be ineligible;
  direct/indirect evidence uses only generic dimensions.
- [ ] Run the focused compatibility suite and confirm RED.
- [ ] Implement generic constraint matching for context, participation, source
  kind, credential/education expectation, and minimum evidence strength.
- [ ] Run focused tests and confirm GREEN.
- [ ] Commit only this task's implementation/tests.

### Task 3: Make assessment consume retrieval candidates with requirement-aware ranking

**Files:**
- Create: `backend/app/capability_analysis/semantic_core/retrieval.py`
- Modify: `backend/app/capability_analysis/rules.py`
- Modify: `backend/app/capability_analysis/retrieval.py`
- Modify: `backend/tests/test_capability_analysis_rules.py`
- Create: `backend/tests/test_semantic_core_assessment.py`

**Interfaces:**
- Produces candidate-derived retrieved/eligible counts, strongest compatible
  evidence, coverage and explicit mismatch status for `RequirementAssessment`.
- Retires duplicate assessment matching paths after compatibility parity tests.
- Before Task 5, uses only the generic identity lexical baseline:
  Unicode normalization, case-folding, whitespace collapse and token-safe exact
  phrase equality. It performs no aliases, morphology, synonym expansion, or
  domain parsing. Domain hints are injected by tests only until the registry is
  introduced.

- [ ] Write RED tests for demonstrated usage, degree, credential, and owned
  outcome requirements. Assert education/credential can be direct evidence for
  their matching expectation without becoming work evidence.
- [ ] Add the explicit regression `retrieved_candidate_count=2`,
  `eligible_candidate_count=0`, `context_mismatch`.
- [ ] Run focused core/rules tests and confirm RED.
- [ ] Implement the identity lexical baseline and one candidate flow from
  evidence semantics through retrieval, compatibility, coverage and assessment;
  retain legacy public fields as projections.
- [ ] Run focused suites and confirm GREEN.
- [ ] Commit only this task's implementation/tests.

### Task 4: Add labelled cross-domain expectation fixtures

**Files:**
- Create: `backend/tests/fixtures/semantic_expectations/ai_engineer.json`
- Create: `backend/tests/fixtures/semantic_expectations/sales_executive.json`
- Create: `backend/tests/fixtures/semantic_expectations/accountant.json`
- Create: `backend/tests/fixtures/semantic_expectations/hr_recruiter.json`
- Create: `backend/tests/test_semantic_cross_domain_fixtures.py`

**Interfaces:**
- Each fixture supplies deterministic requirements, source-backed observations,
  expected retrieved/eligible/status/context/participation results, and no raw
  CV/JD.
- Each fixture injects a narrow test-only `FixtureSemanticHints` adapter (or
  test-only pack stub) through the future pack protocol boundary. It maps only
  phrases declared in that fixture; core modules import neither fixture names
  nor Sales/Accounting/HR vocabulary.

- [ ] Write RED fixture tests for all four domains using local fixture hint
  adapters, plus metrics for expected-positive retrieval, expected-negative
  precision, context, eligibility and participation boundaries.
- [ ] Run the fixture suite and confirm RED.
- [ ] Implement only generic core behavior needed to satisfy the labelled
  expectations; do not add domain names or fixture vocabulary to core modules.
- [ ] Run fixture and prior focused suites and confirm GREEN.
- [ ] Commit only fixture/core changes needed by this task.

### Task 5: Introduce registry and migrate IT/AI vocabulary into `it_ai@1`

**Files:**
- Create: `backend/app/capability_analysis/domain_packs/contracts.py`
- Create: `backend/app/capability_analysis/domain_packs/registry.py`
- Create: `backend/app/capability_analysis/domain_packs/it_ai.py`
- Modify: `backend/app/capability_analysis/retrieval.py`
- Modify: `backend/app/capability_analysis/rules.py`
- Create: `backend/tests/test_domain_pack_registry.py`
- Modify: `backend/tests/test_capability_semantic_retrieval.py`
- Modify: `backend/tests/test_capability_evidence_index.py`

**Interfaces:**
- `DomainKnowledgePack(pack_id, version)` provides normalization and semantic
  hints; the registry resolves exact ordered references or raises a safe
  configuration error.
- `it_ai@1` contains only aliases/morphology that existed before this task.

- [ ] Write RED tests for exact version resolution, unavailable pack rejection,
  and proof that aliases resolve through `it_ai@1`, not a core constant.
- [ ] Run registry and existing AI retrieval tests and confirm RED.
- [ ] Implement the registry and move existing IT/AI aliases, Docker-specific
  vocabulary and model morphology into the pack. Express production as a
  generic required context constraint.
- [ ] Run Python/Kafka/Docker/production/MLOps regressions and confirm GREEN.
- [ ] Commit only pack migration/tests.

### Task 6: Persist semantic policy provenance and verify compatibility shields

**Files:**
- Modify: `backend/app/matching/schemas.py`
- Modify: `backend/app/matching/models.py`
- Modify: `backend/app/matching/repository.py`
- Modify: `backend/app/capability_analysis/schemas.py`
- Modify: `backend/app/capability_analysis/models.py`
- Modify: `backend/app/capability_analysis/repository.py`
- Create: `backend/alembic/versions/20260810_22_semantic_policy_snapshot.py` only if a queryable column is required
- Modify: `backend/tests/test_matching_sql_repository.py`
- Modify: `backend/tests/test_capability_analysis_sql_repository.py`
- Modify: `backend/tests/test_capability_analysis_service.py`

**Interfaces:**
- Newly approved role profiles hold immutable pack references/core policy; new
  portfolios copy them as `semantic_policy` provenance with
  `selection_source=profile_metadata`.
- Create an immutable `role_profile_semantic_policy_mappings` persistence path
  for exact legacy `(role_profile_id, role_profile_version)` entries. It records
  `selection_source=legacy_profile_version_mapping`; absent metadata and absent
  exact mapping cause a safe `semantic_policy_not_configured` failure.
- Historic roles/portfolios deserialize unchanged and are never updated in
  place.

- [ ] Write RED round-trip tests for profile-metadata selection, exact legacy
  mapping selection, missing mapping fail-closed behavior, semantic policy
  provenance, deterministic reruns with identical inputs and pack refs, old
  portfolio deserialization, unavailable-pack safe failure, and no accepted-
  profile mutation.
- [ ] Run repository/service focused suites and confirm RED.
- [ ] Implement additive persistence/defaults and the
  `20260810_22_semantic_policy_snapshot.py` migration for profile metadata and
  the exact legacy policy-mapping store.
- [ ] Run all focused capability, matching and cross-domain suites; then run
  `UV_CACHE_DIR=/private/tmp/pai-uv-cache uv run pytest -q`, `uv run ruff check app tests`, and `git diff --check`.
- [ ] Commit only verified task files.

## Self-review

- TDD order matches the required sequence: generic invariants, participation,
  requirement-aware compatibility, cross-domain fixtures, pack interface/IT
  migration, existing regression/persistence shield.
- The plan makes candidate retrieval the sole assessment input and preserves
  retrieved versus eligible counts.
- The only initial domain pack is a migration of current IT/AI behavior; no
  recall expansion is an acceptance criterion.
- API/lifecycle compatibility, immutability, and PREVIEW-only governance are
  explicit in every relevant task.
