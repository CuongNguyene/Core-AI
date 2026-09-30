# Current-Role and Future-Role Capability Gap Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, auditable capability-analysis portfolio with separate current-role and optional future-role gap tracks from CandidateProfile evidence and role target profiles.

**Architecture:** `app.capability_analysis` is a pure-rule and application-service module above Evidence Graph/CandidateProfile and `RoleCompetencyProfile`. It snapshots managed inputs, preserves evidence context and target-local priority, then persists two independent target analyses plus optional overlap links. Existing matching remains active-only; only the new target resolver permits provisional profiles under explicit current/future policies.

**Tech Stack:** Python 3.12+, Pydantic v2, SQLAlchemy 2.x async, Alembic, FastAPI, pytest/pytest-asyncio, Ruff and mypy.

## Global Constraints

- Do not change Evidence Graph/CandidateProfile extraction runtime or mutate extraction evidence.
- Do not create an assessed/verified competency, assessment decision, learning objective, learning path, LMS state or credential.
- Read managed IDs only; reject inline CV, CandidateProfile, evidence, JD and role-profile payloads.
- Every CV-derived result has independent `verification_status=provisional`; `not_found_in_evidence` never means no capability.
- Current and future requirements/gaps retain independent target ID/type, rationale and preliminary priority; never create a combined readiness score or merged gap.
- Store and audit only IDs, versions, safe status/reason/warning codes and correlation metadata; never raw documents, excerpts, CandidateProfile JSON or PII.
- `ACTIVE` target profiles are official; `PROVISIONAL` is current fallback or future preview only; `DRAFT`/`RETIRED` fail closed. Existing preliminary matching remains `ACTIVE` only.
- Priority is preliminary and records absent business-impact, risk, frequency, deadline and manager-confirmation inputs rather than inventing values.

## File structure

- `backend/app/capability_analysis/schemas.py`: immutable API/domain models and lifecycle enums.
- `backend/app/capability_analysis/rules.py`: pure CandidateProfile-to-capability, target assessment, priority and overlap functions.
- `backend/app/capability_analysis/errors.py`: typed eligibility/access errors.
- `backend/app/capability_analysis/models.py`: SQLAlchemy portfolio and append-only audit mappings.
- `backend/app/capability_analysis/repository.py`: protocol, in-memory and SQLAlchemy immutable persistence adapters.
- `backend/app/capability_analysis/service.py`: guarded orchestration of input resolution, two tracks and persistence.
- `backend/app/capability_analysis/api.py`: ID-only FastAPI endpoints and safe error mapping.
- `backend/app/matching/schemas.py`, `repository.py`, `models.py`: add `PROVISIONAL` target profile lifecycle without weakening preliminary matching.
- `backend/alembic/versions/20260806_15_capability_gap_portfolio.py`: status/persistence migration.
- `backend/app/main.py`: install runtime repository/service and router.

---

### Task 1: Define target lifecycle and capability-analysis contracts

**Files:**
- Create: `backend/app/capability_analysis/__init__.py`
- Create: `backend/app/capability_analysis/schemas.py`
- Modify: `backend/app/matching/schemas.py`
- Test: `backend/tests/test_capability_analysis_schemas.py`
- Test: `backend/tests/test_matching_schemas.py`

**Interfaces:**
- Produces `CapabilityEvidenceStatus`, `VerificationStatus`, `TargetType`, `TargetUsageMode`, `PreliminaryPriority`, `ProvisionalCapability`, `RequirementAssessment`, `TargetGap`, `TargetGapAnalysis`, `GapOverlapLink`, `CombinedGapPortfolio` and `CreateCapabilityGapAnalysisRequest`.
- Extends `RoleProfileStatus` with `PROVISIONAL` while `RoleCompetencyProfile` preserves stable ID/version/source-JD fields.

- [ ] **Step 1: Write failing schema tests**

```python
def test_provisional_capability_requires_source_context_and_provisional_verification() -> None:
    capability = ProvisionalCapability(
        capability_id="python", status=CapabilityEvidenceStatus.SUPPORTED,
        verification_status=VerificationStatus.PROVISIONAL,
        observations=[observation_with_environment_and_context()],
    )
    assert capability.observations[0].environment == "production"

def test_gap_is_target_aware_and_priority_records_missing_inputs() -> None:
    gap = target_gap(target_type=TargetType.CURRENT_ROLE)
    assert gap.target_id == "role-current"
    assert gap.missing_priority_inputs == ["business_impact", "risk", "frequency", "deadline", "manager_confirmation"]
```

- [ ] **Step 2: Run the schema tests to verify RED**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_schemas.py tests/test_matching_schemas.py -q`

Expected: FAIL because `app.capability_analysis` and `RoleProfileStatus.PROVISIONAL` do not exist.

- [ ] **Step 3: Add minimal strict Pydantic contracts**

```python
class TargetType(StrEnum):
    CURRENT_ROLE = "current_role"
    FUTURE_ROLE = "future_role"

class VerificationStatus(StrEnum):
    PROVISIONAL = "provisional"

class RoleProfileStatus(StrEnum):
    DRAFT = "draft"
    PROVISIONAL = "provisional"
    ACTIVE = "active"
    RETIRED = "retired"
```

Make `RequirementAssessment` and `TargetGap` require `target_id`, `target_type`, `requirement_id`, `matched_evidence_refs`, `missing_signals`, `rationale`, `preliminary_priority`, and `missing_priority_inputs`. Make `CombinedGapPortfolio` expose `current_role`, optional `future_role`, and `overlap_links`, without readiness-score fields.

- [ ] **Step 4: Run the schema tests to verify GREEN**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_schemas.py tests/test_matching_schemas.py -q`

Expected: PASS; invalid inline payloads, non-provisional verification values and missing target metadata are rejected.

- [ ] **Step 5: Commit the contracts**

```bash
git add backend/app/capability_analysis backend/app/matching/schemas.py backend/tests/test_capability_analysis_schemas.py backend/tests/test_matching_schemas.py
git commit -m "feat: define capability gap analysis contracts"
```

### Task 2: Implement deterministic profile, target-track and overlap rules

**Files:**
- Create: `backend/app/capability_analysis/rules.py`
- Test: `backend/tests/test_capability_analysis_rules.py`

**Interfaces:**
- Consumes `CandidateProfile`, `RoleCompetencyProfile`, and Task 1 schemas.
- Produces `build_provisional_capability_profile(profile: ExtractionProfile) -> ProvisionalCurrentCapabilityProfile` and `evaluate_target(capability_profile, target, target_type, usage_mode) -> TargetGapAnalysis`.

- [ ] **Step 1: Write failing pure-rule tests**

```python
def test_graph_evidence_keeps_environment_participation_context_and_confidence() -> None:
    profile = accepted_graph_cv_with_production_python_evidence()
    current = build_provisional_capability_profile(profile)
    observation = current.capabilities[0].observations[0]
    assert (observation.environment, observation.participation, observation.confidence) == ("production", "implemented", 0.91)

def test_same_requirement_has_independent_current_and_future_gaps() -> None:
    current = evaluate_target(profile(), current_target(), TargetType.CURRENT_ROLE, TargetUsageMode.OFFICIAL)
    future = evaluate_target(profile(), future_target(), TargetType.FUTURE_ROLE, TargetUsageMode.OFFICIAL)
    assert current.gaps[0].id != future.gaps[0].id
    assert current.gaps[0].target_type is TargetType.CURRENT_ROLE
    assert future.gaps[0].target_type is TargetType.FUTURE_ROLE
```

Cover every evidence status; `not_found_in_evidence` has empty evidence refs and a non-assertive missing signal. Cover low-confidence/partial, conflicting graph evidence, unknown priority inputs, preview warning, and an overlap link that references but does not merge two gap IDs.

- [ ] **Step 2: Run rule tests to verify RED**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_rules.py -q`

Expected: FAIL because rule functions are undefined.

- [ ] **Step 3: Write minimal deterministic rules**

```python
def evaluate_target(profile: ProvisionalCurrentCapabilityProfile, target: RoleCompetencyProfile, target_type: TargetType, usage_mode: TargetUsageMode) -> TargetGapAnalysis:
    assessments = [evaluate_requirement(profile, target, requirement, target_type) for requirement in target.requirements]
    return TargetGapAnalysis(target_id=target.id, target_type=target_type, usage_mode=usage_mode, assessments=assessments, gaps=gaps_from(assessments))
```

Use source-backed CandidateProfile evidence only. Preserve environment/context/participation and confidence in evidence refs. Produce target-local rationale and the fixed list of missing priority inputs where no managed priority metadata exists. Link gaps only when normalized prerequisite/requirement evidence keys agree.

- [ ] **Step 4: Run rule tests to verify GREEN**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_rules.py -q`

Expected: PASS; output is deterministic and contains neither a merged gap nor a combined score.

- [ ] **Step 5: Commit deterministic rules**

```bash
git add backend/app/capability_analysis/rules.py backend/tests/test_capability_analysis_rules.py
git commit -m "feat: evaluate separate current and future capability gaps"
```

### Task 3: Add target resolution, immutable repositories and migration

**Files:**
- Create: `backend/app/capability_analysis/errors.py`
- Create: `backend/app/capability_analysis/models.py`
- Create: `backend/app/capability_analysis/repository.py`
- Modify: `backend/app/matching/models.py`
- Modify: `backend/app/matching/repository.py`
- Create: `backend/alembic/versions/20260806_15_capability_gap_portfolio.py`
- Test: `backend/tests/test_capability_analysis_repository.py`
- Test: `backend/tests/test_capability_analysis_sql_repository.py`
- Test: `backend/tests/test_migration_config.py`

**Interfaces:**
- Extends role-profile repository with `get_preferred_target(profile_id: str) -> RoleCompetencyProfile | None`, returning active before provisional.
- Produces `CapabilityGapPortfolioRepository.create(portfolio)`, `get(portfolio_id)`, and `record_rejected_input(...)`.

- [ ] **Step 1: Write failing resolution/persistence tests**

```python
async def test_target_resolver_prefers_active_current_target_over_provisional() -> None:
    target = await roles.get_preferred_target("role-engineer")
    assert target is not None and target.status is RoleProfileStatus.ACTIVE

async def test_sql_portfolio_create_rolls_back_when_audit_write_fails() -> None:
    with pytest.raises(AuditPersistenceError):
        await repository.create(portfolio, fail_audit=True)
    assert await repository.get(portfolio.id) is None
```

Also cover one target type per portfolio, immutable version uniqueness, gap identity uniqueness, overlap source/target uniqueness, version snapshots and absence of evidence payload in audit metadata.

- [ ] **Step 2: Run repository tests to verify RED**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_repository.py tests/test_capability_analysis_sql_repository.py tests/test_migration_config.py -q`

Expected: FAIL because repositories/models/migration do not exist.

- [ ] **Step 3: Implement storage and migration minimally**

```python
class CapabilityGapPortfolioRepository(Protocol):
    async def create(self, portfolio: CombinedGapPortfolio) -> CombinedGapPortfolio: ...
    async def get(self, portfolio_id: str) -> CombinedGapPortfolio | None: ...
```

Add `provisional` support to stored role-profile status. Persist safe normalized assessment/gap metadata in child rows, source profile/target versions on the portfolio, and append audit inside the same `AsyncSession.begin()` transaction. Do not add any foreign key or write path to learning/competency tables.

- [ ] **Step 4: Run repository tests to verify GREEN**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_repository.py tests/test_capability_analysis_sql_repository.py tests/test_migration_config.py -q`

Expected: PASS and Alembic reports one linear head.

- [ ] **Step 5: Commit persistence**

```bash
git add backend/app/capability_analysis backend/app/matching/models.py backend/app/matching/repository.py backend/alembic/versions/20260806_15_capability_gap_portfolio.py backend/tests/test_capability_analysis_repository.py backend/tests/test_capability_analysis_sql_repository.py backend/tests/test_migration_config.py
git commit -m "feat: persist capability gap portfolios"
```

### Task 4: Implement guarded capability-analysis service

**Files:**
- Create: `backend/app/capability_analysis/service.py`
- Test: `backend/tests/test_capability_analysis_service.py`

**Interfaces:**
- Produces `CapabilityGapAnalysisService.create(request: CreateCapabilityGapAnalysisRequest, actor: ActorContext) -> CombinedGapPortfolio` and `get(portfolio_id: str, actor: ActorContext) -> CombinedGapPortfolio`.
- Consumes Task 2 rules, accepted extraction repository, Task 3 target resolver and portfolio repository.

- [ ] **Step 1: Write failing service tests**

```python
async def test_current_provisional_target_is_allowed_with_warning() -> None:
    portfolio = await service.create(request(current_target="jd-derived-profile"), learner_actor)
    assert portfolio.current_role.usage_mode is TargetUsageMode.PROVISIONAL

async def test_future_draft_target_is_rejected_without_persisting_portfolio() -> None:
    with pytest.raises(FutureTargetNotUsableError):
        await service.create(request(future_target="draft-role"), learner_actor)
    assert repository.portfolios == {}
```

Cover accepted/non-superseded CV CandidateProfile guard, CV owner/org guard, missing current target, active-current preference, provisional-future preview warning, retired-future rejection, separate gaps and no writes to extraction/competency/learning fixtures.

- [ ] **Step 2: Run service tests to verify RED**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_service.py -q`

Expected: FAIL because `CapabilityGapAnalysisService` is undefined.

- [ ] **Step 3: Implement service guard and orchestration**

```python
async def create(self, request: CreateCapabilityGapAnalysisRequest, actor: ActorContext) -> CombinedGapPortfolio:
    cv = await self._accepted_owned_candidate_profile(request.cv_profile_id, actor)
    current = await self._resolve_current_target(request.current_target_profile_id)
    future = await self._resolve_future_target(request.future_target_profile_id)
    profile = build_provisional_capability_profile(cv)
    return await self._portfolios.create(build_portfolio(profile, current, future, actor, request.correlation_id))
```

Require the current target's accepted JD source/version; resolve active before provisional. Keep future provisional in preview mode only. Catch typed eligibility errors only to append a safe rejection audit. Do not call matching, learning or competency mutation APIs.

- [ ] **Step 4: Run service tests to verify GREEN**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_service.py -q`

Expected: PASS; failed guards are fail-closed and successful portfolios retain separated tracks.

- [ ] **Step 5: Commit service**

```bash
git add backend/app/capability_analysis/service.py backend/app/capability_analysis/errors.py backend/tests/test_capability_analysis_service.py
git commit -m "feat: create guarded capability gap analyses"
```

### Task 5: Expose ID-only API, wire runtime and verify the contract

**Files:**
- Create: `backend/app/capability_analysis/api.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_capability_analysis_api.py`
- Test: `backend/tests/test_capability_analysis_openapi.py`
- Create: `backend/tests/golden/capability_gap_portfolio.json`
- Create: `backend/tests/test_capability_analysis_golden.py`
- Modify: `docs/architecture/system-context.md`

**Interfaces:**
- `POST /capability-gap-portfolios` accepts `cv_profile_id`, `current_target_profile_id`, optional `future_target_profile_id`, and `correlation_id`.
- `GET /capability-gap-portfolios/{portfolio_id}` returns only the owner/authorized reviewer-safe immutable portfolio.

- [ ] **Step 1: Write failing API/OpenAPI/golden tests**

```python
async def test_api_accepts_references_not_inline_candidate_profile() -> None:
    response = await client.post("/capability-gap-portfolios", headers=learner_headers, json=valid_ids())
    assert response.status_code == 201
    assert "combined_readiness_score" not in response.json()
    assert response.json()["current_role"]["gaps"][0]["target_type"] == "current_role"

def test_openapi_request_has_no_candidate_profile_or_role_payload() -> None:
    schema = openapi()["components"]["schemas"]["CreateCapabilityGapAnalysisRequest"]
    assert set(schema["properties"]) == {"cv_profile_id", "current_target_profile_id", "future_target_profile_id", "correlation_id"}
```

Cover owner/access denial, provisional future warning, draft/retired safe error codes, no raw evidence in audit/API-safe summary, and byte-equivalent normalized output for identical fixture inputs.

- [ ] **Step 2: Run API tests to verify RED**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_api.py tests/test_capability_analysis_openapi.py tests/test_capability_analysis_golden.py -q`

Expected: FAIL because router/runtime wiring is absent.

- [ ] **Step 3: Add a thin API and runtime wiring**

```python
@router.post("/capability-gap-portfolios", response_model=CombinedGapPortfolio, status_code=201)
async def create_portfolio(body: CreateCapabilityGapAnalysisRequest, request: Request, actor: DevelopmentActor = Depends(get_development_actor)) -> CombinedGapPortfolio:
    return await _service(request).create(body, actor)
```

Map typed service failures to ADR-0003 safe envelopes; do not accept role, organization or actor values in the body. Register SQLAlchemy adapters in `create_app()` and use in-memory adapters only in tests. Update the system context diagram/text to show this module after CandidateProfile and before any future learning-object consumer.

- [ ] **Step 4: Run API, golden and full quality verification**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_api.py tests/test_capability_analysis_openapi.py tests/test_capability_analysis_golden.py -q && uv run --extra dev ruff format --check . && uv run --extra dev ruff check . && uv run --extra dev mypy app && uv run --extra dev pytest -q && uv run --extra dev alembic heads`

Expected: all commands exit 0, golden output is stable, and Alembic reports exactly one head.

- [ ] **Step 5: Commit API and verification artifacts**

```bash
git add backend/app/capability_analysis/api.py backend/app/main.py backend/tests/test_capability_analysis_api.py backend/tests/test_capability_analysis_openapi.py backend/tests/golden/capability_gap_portfolio.json backend/tests/test_capability_analysis_golden.py docs/architecture/system-context.md
git commit -m "feat: expose capability gap portfolio API"
```

### Task 6: Terra boundary review and Luna correction loop

**Files:**
- Review: `git diff pr-010a-delivery-layout...HEAD`
- Review: all Task 1–5 changed files

**Interfaces:**
- Terra reviews only after fresh Task 5 verification output is available.
- Luna receives concrete file/test/behavior corrections, implements them through a new RED/GREEN cycle, and returns fresh verification evidence.

- [ ] **Step 1: Terra run the boundary checklist**

```text
[ ] Evidence Graph/CandidateProfile runtime is unchanged.
[ ] No capability result is verified/assessed.
[ ] No learning/credential write path exists.
[ ] Current/future gaps and priorities remain distinct.
[ ] Provisional future is preview-only; draft/retired fail closed.
[ ] API is ID-only; audit contains no raw/PII payload.
[ ] No combined readiness score or merged gap exists.
```

- [ ] **Step 2: Terra verify the complete diff and test evidence**

Run: `git diff --check pr-010a-delivery-layout...HEAD && cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check . && uv run --extra dev mypy app`

Expected: no whitespace errors and all checks exit 0.

- [ ] **Step 3: Luna make each concrete correction test-first**

For every identified defect, add a focused failing test naming the prohibited behavior, run it to observe the expected failure, minimally correct the named source file, then rerun the focused test and the full quality command from Step 2.

- [ ] **Step 4: Terra re-run the boundary checklist after correction**

Run: `git diff --check pr-010a-delivery-layout...HEAD && cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check . && uv run --extra dev mypy app`

Expected: all checks exit 0 and every checklist item remains true.

- [ ] **Step 5: Commit correction(s) only when needed**

```bash
git add <reviewed-source-and-test-files>
git commit -m "fix: preserve capability gap boundaries"
```
