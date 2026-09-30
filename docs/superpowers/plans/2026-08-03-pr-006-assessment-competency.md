# PR-006 Assessment & Competency Decision Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build auditable assessment decisions and competency verification controlled by UUID development identity, RBAC and scoped delegation.

**Architecture:** Add a minimal `authorization` module that resolves a UUID header into one persisted active organization context. Assessment owns versioned templates, tasks, submissions and score proposals; competency owns state transitions and delegates authorization checks to a policy service. SQLAlchemy repositories append safe audit records in the same transaction as transitions.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x async, Alembic, PostgreSQL, pytest/pytest-asyncio, Ruff, mypy.

## Global Constraints

- Keep modular monolith; no general ABAC, OPA/Cedar, IAM/SSO, multi-org selector, credential issuance, proctoring or automatic verification.
- `X-PAI-Actor-ID` must be a persisted active UUID; never accept role/organization from request headers or map legacy string actor IDs.
- Every development user has exactly one active organization membership; unknown/disabled/multiple/inactive-org contexts fail closed.
- Basic roles are `ADMIN`, `SME`, `REVIEWER`, `LEARNER`; `competency.verify` requires active scoped delegation and is never implied by ADMIN/SME.
- Completion never changes competency state. AI scoring is an interface/mock only; future AI calls go through ModelGateway/PrivacyGateway and human review remains mandatory.
- Audit never stores raw submission content, CV/JD, prompts, model output, secrets or tokens. Decision/delegation state change and required audit event share one transaction.
- Use test-first development; update OpenAPI/docs/migration test and run Ruff, mypy, pytest, pre-commit before each final commit.

---

### Task 1: Add UUID subject store and migrate development actor boundary

**Files:**
- Create: `app/authorization/__init__.py`, `app/authorization/schemas.py`, `app/authorization/models.py`, `app/authorization/repository.py`, `app/authorization/fixtures.py`
- Modify: `app/extraction/auth.py`, `app/extraction/schemas.py`, `app/extraction/models.py`, `app/extraction/repository.py`, `app/matching/schemas.py`, `app/matching/models.py`, `app/matching/repository.py`, `app/main.py`
- Create: `alembic/versions/20260803_08_authorization_subject_store.py`
- Test: `tests/test_development_identity.py`, `tests/test_authorization_repository.py`, existing extraction/matching tests

**Interfaces:**

```python
class Role(StrEnum):
    ADMIN = "admin"
    SME = "sme"
    REVIEWER = "reviewer"
    LEARNER = "learner"


class ActorContext(BaseModel):
    actor_id: UUID
    organization_id: UUID
    roles: frozenset[Role]
    authentication_method: Literal["development_header"] = "development_header"


class DevelopmentIdentityAdapter:
    async def resolve(self, actor_id: UUID) -> ActorContext: ...
```

- [ ] **Step 1: Write failing identity tests**

```python
async def test_header_resolves_only_active_uuid_user_with_one_active_membership() -> None:
    response = await client.get("/health/live", headers={"X-PAI-Actor-ID": str(LEARNER_ID)})
    assert response.status_code == 200


async def test_unknown_disabled_invalid_or_ambiguous_identity_fails_closed() -> None:
    # malformed -> safe validation error; unknown -> 401; disabled/multiple/inactive org -> 403
    ...
```

- [ ] **Step 2: Run RED**

Run: `uv run --extra dev pytest tests/test_development_identity.py tests/test_authorization_repository.py -q`  
Expected: import/contract failures because no authorization subject store exists.

- [ ] **Step 3: Implement subject records, seed and UUID migration**

Create `users`, `organizations`, `organization_memberships`, `user_role_assignments` with active/time indexes. Seed fixed UUID fixtures for ORG-PAI, admin, SME, reviewer, learner and authorized-SME. Change actor/reviewer/audit persistence fields belonging to extraction/matching to UUID and update fixtures; migration must reject non-reset legacy data instead of deriving UUIDs.

- [ ] **Step 4: Implement adapter and replace header role trust**

Parse only UUID header, resolve user/membership/roles via repository, return `ActorContext`; remove `X-PAI-Actor-Role` use. Preserve ADR-0003 safe error envelope with 401 for unknown identity and 403 for disabled/ineligible context.

- [ ] **Step 5: Run GREEN and cross-slice tests**

Run: `uv run --extra dev pytest tests/test_development_identity.py tests/test_authorization_repository.py tests/test_extraction_api.py tests/test_matching_api.py -q`  
Expected: all pass using UUID seed IDs; no string actor fallback.

- [ ] **Step 6: Commit**

```bash
git add app/authorization app/extraction app/matching app/main.py alembic/versions/20260803_08_authorization_subject_store.py tests
git commit -m "feat: add UUID development identity subjects"
```

### Task 2: Persist role assignment and scoped delegation lifecycle

**Files:**
- Create: `app/authorization/delegation.py`, `app/authorization/errors.py`
- Modify: `app/authorization/models.py`, `app/authorization/repository.py`, `app/authorization/schemas.py`
- Create: `alembic/versions/20260803_09_scoped_delegations.py`
- Test: `tests/test_delegation_repository.py`, `tests/test_delegation_schemas.py`

**Interfaces:**

```python
class DelegationStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ScopedDelegation(BaseModel):
    id: UUID
    user_id: UUID
    permission: Literal["competency.verify"]
    organization_id: UUID
    competency_scope: frozenset[str]
    valid_from: datetime
    valid_until: datetime
    status: DelegationStatus
    version: int


class DelegationRepository(Protocol):
    async def transition(
        self,
        delegation_id: UUID,
        actor_id: UUID,
        expected_version: int,
        target: DelegationStatus,
        reason: str,
    ) -> ScopedDelegation: ...
```

- [ ] **Step 1: Write failing lifecycle tests**

```python
async def test_activate_uses_expected_version_and_appends_audit_atomically() -> None: ...
async def test_revoke_preserves_delegation_used_by_verification() -> None: ...
async def test_expired_suspended_and_revoked_delegation_is_not_active() -> None: ...
```

- [ ] **Step 2: Run RED**

Run: `uv run --extra dev pytest tests/test_delegation_schemas.py tests/test_delegation_repository.py -q`  
Expected: delegation module unavailable.

- [ ] **Step 3: Implement models/migration/repository**

Persist required delegation fields, active lookup index `(user_id, permission, organization_id, status)`, validity index and unique version semantics. Implement only DRAFT→ACTIVE, ACTIVE→SUSPENDED/REVOKED, SUSPENDED→ACTIVE/REVOKED and derived expiry read behavior; audit insert failure rolls back version/state.

- [ ] **Step 4: Run GREEN**

Run: `uv run --extra dev pytest tests/test_delegation_schemas.py tests/test_delegation_repository.py -q`  
Expected: all transitions, stale conflict and audit rollback pass.

- [ ] **Step 5: Commit**

```bash
git add app/authorization alembic/versions/20260803_09_scoped_delegations.py tests/test_delegation_schemas.py tests/test_delegation_repository.py
git commit -m "feat: persist scoped competency delegations"
```

### Task 3: Define assessment, rubric and competency decision contracts

**Files:**
- Create: `app/assessment/schemas.py`, `app/assessment/scorer.py`, `app/assessment/errors.py`
- Modify: `app/competency/schemas.py`
- Test: `tests/test_assessment_schemas.py`, `tests/test_competency_schemas.py`, `tests/test_scorer.py`

**Interfaces:**

```python
class AssessmentTaskType(StrEnum):
    QUIZ = "quiz"
    PRACTICAL = "practical"
    CASE = "case"


class RiskClassification(StrEnum):
    LOW_RISK = "low_risk"
    HIGH_RISK = "high_risk"


class CompetencyStatus(StrEnum):
    UNKNOWN = ...
    PENDING_VERIFICATION = ...
    RETURNED_FOR_REVIEW = ...


class AssessmentScorer(Protocol):
    async def score(self, submission: AssessmentSubmission, rubric: Rubric) -> ScoreProposal: ...
```

- [ ] **Step 1: Write failing schema/scorer tests**

```python
def test_template_requires_immutable_rubric_version_and_task_placeholder() -> None: ...
def test_completion_has_no_competency_transition_field() -> None: ...
async def test_mock_scorer_returns_proposal_never_a_decision() -> None: ...
```

- [ ] **Step 2: Run RED**

Run: `uv run --extra dev pytest tests/test_assessment_schemas.py tests/test_competency_schemas.py tests/test_scorer.py -q`  
Expected: missing contracts.

- [ ] **Step 3: Implement immutable Pydantic contracts**

Model template/rubric/task, submission reference/evidence IDs, score proposal and SME review separately. Expand competency state enum without retaining an evidence-state `VERIFIED` shortcut. Require rubric/policy versions, validity/reassessment policy and human review; mock scorer has no authorization/state mutation capability.

- [ ] **Step 4: Run GREEN**

Run: `uv run --extra dev pytest tests/test_assessment_schemas.py tests/test_competency_schemas.py tests/test_scorer.py -q`  
Expected: contracts validate only safe references and fixed lifecycle values.

- [ ] **Step 5: Commit**

```bash
git add app/assessment app/competency/schemas.py tests/test_assessment_schemas.py tests/test_competency_schemas.py tests/test_scorer.py
git commit -m "feat: define assessment and competency decision contracts"
```

### Task 4: Add assessment/competency persistence and transaction-safe audit

**Files:**
- Create: `app/assessment/models.py`, `app/assessment/repository.py`, `app/competency/models.py`, `app/competency/repository.py`
- Create: `alembic/versions/20260803_11_assessment_competency_decisions.py`
- Test: `tests/test_assessment_repository.py`, `tests/test_competency_repository.py`

**Interfaces:**

```python
class AssessmentDecisionRepository(Protocol):
    async def transition(
        self,
        decision_id: UUID,
        expected_version: int,
        transition: DecisionTransition,
        actor: ActorContext,
        authorization: AuthorizationDecision,
    ) -> CompetencyDecision: ...
```

- [ ] **Step 1: Write failing persistence tests**

```python
async def test_decision_persists_rubric_evidence_validity_and_safe_audit() -> None: ...
async def test_audit_failure_rolls_back_competency_state_and_decision_version() -> None: ...
async def test_verification_history_is_immutable_after_delegation_revoke() -> None: ...
```

- [ ] **Step 2: Run RED**

Run: `uv run --extra dev pytest tests/test_assessment_repository.py tests/test_competency_repository.py -q`  
Expected: ORM/repositories absent.

- [ ] **Step 3: Implement ORM and migration**

Create tables for template/rubric/task, submission, score proposal/review, assessment decision, competency record, immutable competency decision history and authorization/assessment audit. Store only submission references; decision transition takes row lock and expected version, updates derived record and appends audit in one session transaction.

- [ ] **Step 4: Run GREEN**

Run: `uv run --extra dev pytest tests/test_assessment_repository.py tests/test_competency_repository.py -q`  
Expected: persistence, immutable history and rollback tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/assessment app/competency alembic/versions/20260803_11_assessment_competency_decisions.py tests/test_assessment_repository.py tests/test_competency_repository.py
git commit -m "feat: persist assessment competency decisions"
```

### Task 5: Implement application authorization policy and decision service

**Files:**
- Create: `app/authorization/policy.py`, `app/competency/service.py`
- Modify: `app/assessment/repository.py`, `app/competency/repository.py`
- Test: `tests/test_competency_policy.py`, `tests/test_competency_service.py`

**Interfaces:**

```python
class CompetencyAuthorizationPolicy:
    async def can_mark_assessed(
        self,
        *,
        actor: ActorContext,
        organization_id: UUID,
        competency_id: str,
        assessment_decision_id: UUID,
    ) -> AuthorizationDecision: ...
    async def can_verify(
        self,
        *,
        actor: ActorContext,
        subject_id: UUID,
        organization_id: UUID,
        competency_id: str,
        assessment_decision_id: UUID,
    ) -> AuthorizationDecision: ...
```

- [ ] **Step 1: Write failing policy/service tests**

```python
async def test_sme_marks_assessed_but_plain_sme_cannot_verify() -> None: ...
async def test_delegated_sme_verifies_only_matching_org_scope_and_window() -> None: ...
async def test_high_risk_requires_distinct_assessor_and_verifier() -> None: ...
async def test_subject_admin_reviewer_and_learner_cannot_verify() -> None: ...
```

- [ ] **Step 2: Run RED**

Run: `uv run --extra dev pytest tests/test_competency_policy.py tests/test_competency_service.py -q`  
Expected: policy/service unavailable.

- [ ] **Step 3: Implement fail-closed policy and service transitions**

Check active roles/membership, state, subject conflict, active delegation org/scope/window and low/high risk SoD. Service calls policy for every transition, persists `AUTHORIZATION_DENIED` safely on denial, and maps `ASSESSED`, request/return review, verify, reassessment and revoke to explicit state transitions only.

- [ ] **Step 4: Run GREEN**

Run: `uv run --extra dev pytest tests/test_competency_policy.py tests/test_competency_service.py -q`  
Expected: required allow/deny/state/SoD cases pass without router involvement.

- [ ] **Step 5: Commit**

```bash
git add app/authorization/policy.py app/competency/service.py app/assessment app/competency tests/test_competency_policy.py tests/test_competency_service.py
git commit -m "feat: enforce delegated competency decisions"
```

### Task 6: Expose development-only delegation, assessment and decision APIs

**Files:**
- Create: `app/authorization/api.py`, `app/assessment/api.py`, `app/competency/api.py`
- Modify: `app/main.py`, `app/shared/errors.py`
- Test: `tests/test_delegation_api.py`, `tests/test_assessment_api.py`, `tests/test_competency_api.py`

**Interfaces:**

```python
POST /delegations
GET /delegations/{delegation_id}
GET /users/{user_id}/delegations
POST /delegations/{delegation_id}/activate|suspend|revoke
POST /assessment-templates
POST /assessment-submissions
POST /assessment-decisions/{decision_id}/mark-assessed|request-verification|verify|return-for-review
POST /competencies/{competency_record_id}/require-reassessment|revoke-verification
```

- [ ] **Step 1: Write failing API tests**

```python
async def test_client_role_header_cannot_make_learner_an_sme() -> None: ...
async def test_delegated_sme_can_verify_with_expected_version() -> None: ...
async def test_all_transition_errors_use_safe_envelope_and_403_or_409() -> None: ...
```

- [ ] **Step 2: Run RED**

Run: `uv run --extra dev pytest tests/test_delegation_api.py tests/test_assessment_api.py tests/test_competency_api.py -q`  
Expected: routers unavailable.

- [ ] **Step 3: Implement thin routers and app wiring**

Use only `ActorContext` dependency; request bodies contain references, reason and expected version, never actor/role/org/raw answer. Enforce ownership/scoped reads in service/repository and map typed errors to ADR-0003 responses/OpenAPI models.

- [ ] **Step 4: Run GREEN**

Run: `uv run --extra dev pytest tests/test_delegation_api.py tests/test_assessment_api.py tests/test_competency_api.py -q`  
Expected: authorized flows, every specified denial and stale conflict pass.

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/authorization/api.py app/assessment/api.py app/competency/api.py app/shared/errors.py tests/test_delegation_api.py tests/test_assessment_api.py tests/test_competency_api.py
git commit -m "feat: expose delegated assessment decision APIs"
```

### Task 7: Golden harness, documentation reconciliation and release verification

**Files:**
- Create: `tests/golden/assessment_competency_authorization.json`, `tests/test_golden_assessment_competency.py`
- Modify: `docs/security/authorization.md`, `docs/domain/three-layer-assessment.md`, `docs/superpowers/specs/2026-08-03-pr-006-assessment-competency-design.md`
- Test: `tests/test_migration_config.py`

- [ ] **Step 1: Write failing golden and revision tests**

```python
async def test_golden_delegation_and_competency_matrix_is_deterministic() -> None: ...
def test_alembic_head_includes_assessment_competency_revision() -> None: ...
```

- [ ] **Step 2: Run RED**

Run: `uv run --extra dev pytest tests/test_golden_assessment_competency.py tests/test_migration_config.py -q`  
Expected: fixture/head assertion fails until final harness is added.

- [ ] **Step 3: Add golden scenarios and reconcile docs**

Cover SME assessed, delegated verify, ADMIN/REVIEWER/LEARNER/self denial, org/scope/window/delegation state denial, stale version, invalid transitions, audit rollback, low/high risk SoD and deterministic rerun. Update docs only to reflect implemented API/migration semantics.

- [ ] **Step 4: Run full verification and migration**

Run: `uv run --extra dev ruff format --check . && uv run --extra dev ruff check . && uv run --extra dev mypy app && uv run --extra dev pytest -q && uv run --extra dev alembic upgrade head && uv run --extra dev pre-commit run --all-files`  
Expected: all commands exit 0; PostgreSQL reports final Alembic head.

- [ ] **Step 5: Commit**

```bash
git add tests/golden tests/test_golden_assessment_competency.py tests/test_migration_config.py docs
git commit -m "test: add competency authorization golden harness"
```
