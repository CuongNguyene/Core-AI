# JD-to-Role-Profile Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reviewer-controlled JD extraction to `PROVISIONAL`/`ACTIVE` role-profile workflow with a deterministic quality gate.

**Architecture:** Add a draft schema/repository/service bounded around the existing accepted extraction and role-profile repositories. Persist immutable draft versions and approval audit records, then materialize the existing `RoleCompetencyProfileRecord` only after reviewer approval. Keep matching/capability APIs unchanged.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy async, Alembic, pytest.

## Global Constraints

- Only accepted, non-superseded JD extraction profiles are valid sources.
- Draft creation, authoring, validation and approval require `Role.REVIEWER`.
- `ACTIVE` requires reviewer approval and a passing quality gate; failing gates may produce only `PROVISIONAL`.
- Every mutation uses `expected_version`; stale writes fail closed.
- No raw JD, source excerpt, prompt, model output or arbitrary schema is accepted or persisted by the workflow.
- Drafts are not eligible targets for matching or capability analysis.

---

### Task 1: Draft domain, quality gate and migration

**Files:**
- Create: `backend/app/role_profile_authoring/schemas.py`
- Create: `backend/app/role_profile_authoring/models.py`
- Create: `backend/app/role_profile_authoring/quality_gate.py`
- Create: `backend/alembic/versions/20260806_18_role_profile_authoring.py`
- Test: `backend/tests/test_role_profile_authoring_quality_gate.py`

**Interfaces:**
- `RoleProfileDraft`, `RoleProfileDraftStatus`, `RoleProfileDraftRequirementSet`.
- `validate_role_profile_requirements(requirements) -> QualityGateResult`.
- SQL tables store draft versions, current version/status, source JD ID/version, requirements and safe findings.

- [ ] **Step 1: Write failing quality-gate tests**

```python
def test_gate_rejects_duplicate_ids_and_empty_terms() -> None:
    result = validate_role_profile_requirements([requirement("same", []), requirement("same", ["python"])])
    assert result.passed is False
    assert {item.code for item in result.findings} == {"duplicate_requirement_id", "empty_evidence_terms"}

def test_gate_accepts_complete_structured_requirements() -> None:
    result = validate_role_profile_requirements([requirement("python", ["python"])])
    assert result.passed is True
    assert result.findings == []
```

- [ ] **Step 2: Run RED**

Run: `cd backend && UV_CACHE_DIR=/tmp/pai-uv-cache uv run --extra dev pytest tests/test_role_profile_authoring_quality_gate.py -q`

Expected: FAIL because the authoring package and gate do not exist.

- [ ] **Step 3: Implement schemas, gate and migration**

Use strict Pydantic models and codes `source_profile_ineligible`,
`no_requirements`, `invalid_requirement_id`, `duplicate_requirement_id`,
`empty_evidence_terms`, `invalid_threshold`, `empty_recommendation` and
`empty_rubric_version`. The migration creates draft/version/audit tables with
indexes and foreign keys to extraction profiles and leaves role profile tables
unchanged.

- [ ] **Step 4: Run GREEN and migration checks**

Run the focused test and `UV_CACHE_DIR=/tmp/pai-uv-cache uv run alembic heads`.
Expected: tests pass and exactly one head is shown.

### Task 2: SQL repository and materialization

**Files:**
- Create: `backend/app/role_profile_authoring/repository.py`
- Modify: `backend/app/matching/repository.py`
- Test: `backend/tests/test_role_profile_authoring_repository.py`

**Interfaces:**
- `RoleProfileDraftRepository.create_from_jd(...)`.
- `RoleProfileDraftRepository.author(...)`, `.validate(...)`, `.approve(...)`, `.get(...)`.
- Materialization uses `SqlAlchemyRoleProfileRepository.save()` with the approved status and immutable version.

- [ ] **Step 1: Write failing repository lifecycle tests**

```python
async def test_repository_requires_accepted_source_and_expected_version(session_factory):
    repository = SqlAlchemyRoleProfileDraftRepository(session_factory)
    with pytest.raises(RoleProfileDraftSourceError):
        await repository.create_from_jd("pending-jd", REVIEWER_ID, "run-1")

async def test_repository_materializes_provisional_then_active_only_after_gate(session_factory):
    draft = await repository.create_from_jd("accepted-jd", REVIEWER_ID, "run-1")
    authored = await repository.author(draft.id, expected_version=draft.version, requirements=complete_requirements(), actor_id=REVIEWER_ID)
    validated = await repository.validate(draft.id, expected_version=authored.version, actor_id=REVIEWER_ID)
    approved = await repository.approve(draft.id, expected_version=validated.version, requested_status=RoleProfileStatus.ACTIVE, actor_id=REVIEWER_ID)
    assert approved.status is RoleProfileStatus.ACTIVE
```

- [ ] **Step 2: Run RED**

Run: `cd backend && UV_CACHE_DIR=/tmp/pai-uv-cache uv run --extra dev pytest tests/test_role_profile_authoring_repository.py -q`

Expected: FAIL because repository methods do not exist.

- [ ] **Step 3: Implement transactional lifecycle**

Check source profile state/version and supersession before creation. On author,
replace the full requirement set and increment the immutable draft version. On
validate, persist only safe finding codes. On approve, reject unvalidated
versions and reject `ACTIVE` when the gate is false; create the existing role
record with source JD version, rule/policy versions and requested status.
Append audit rows in the same transaction.

- [ ] **Step 4: Run GREEN repository tests**

Run the focused repository test file. Expected: PASS, including stale version,
source ineligible, duplicate approval and safe audit assertions.

### Task 3: Service and API workflow

**Files:**
- Create: `backend/app/role_profile_authoring/service.py`
- Create: `backend/app/role_profile_authoring/api.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_role_profile_authoring_api.py`

**Interfaces:**
- Routes: `POST/GET/PATCH /role-profile-drafts/{...}`, validate and approve routes described in the spec.
- `RoleProfileAuthoringService` maps actor, source eligibility, gate and repository conflicts to safe API errors.

- [ ] **Step 1: Write failing API tests**

Cover reviewer create/edit/validate/approve, learner `403`, pending JD `409`,
stale expected version `409`, failed gate forced to `PROVISIONAL`, and passing
gate active approval.

- [ ] **Step 2: Run RED**

Run: `cd backend && UV_CACHE_DIR=/tmp/pai-uv-cache uv run --extra dev pytest tests/test_role_profile_authoring_api.py -q`

Expected: FAIL because routes are not registered.

- [ ] **Step 3: Implement and wire API**

Use `get_development_actor`, `require_reviewer`, existing `APIError`, correlation
middleware and repository state. Strict request models accept only structured
fields and expected versions. Return no raw source payload.

- [ ] **Step 4: Run GREEN API tests**

Run focused API tests. Expected: PASS with safe error codes and role profile
materialization visible through `SqlAlchemyRoleProfileRepository`.

### Task 4: End-to-end regression and documentation

**Files:**
- Create: `docs/testing/jd-role-profile-authoring.md`
- Modify: `README.md`
- Test: `backend/tests/test_role_profile_authoring_workflow.py`

- [ ] **Step 1: Write failing workflow test**

Execute accepted JD profile -> create draft -> edit all requirement metadata ->
validate -> approve provisional, then repeat with complete input and approve
active. Assert draft cannot be passed to matching and output contains no raw JD.

- [ ] **Step 2: Run RED**

Run: `cd backend && UV_CACHE_DIR=/tmp/pai-uv-cache uv run --extra dev pytest tests/test_role_profile_authoring_workflow.py -q`

Expected: FAIL until all layers are wired.

- [ ] **Step 3: Implement docs and workflow fixture**

Document curl/API sequence, identity headers, expected statuses, gate finding
codes and the rule that JD extraction never creates an active profile.

- [ ] **Step 4: Run full verification**

```bash
cd backend
UV_CACHE_DIR=/tmp/pai-uv-cache uv run ruff format --check .
UV_CACHE_DIR=/tmp/pai-uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/pai-uv-cache uv run mypy app
UV_CACHE_DIR=/tmp/pai-uv-cache uv run --extra dev pytest -q
```

Expected: all commands exit `0`.
