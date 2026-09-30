# PR-008 Credential Policy & Issuance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement versioned credential policy evaluation, delegated approval and issuance, validity/revocation, public verification and immutable audit without treating learning completion as competency verification.

**Architecture:** Add a `credential` modular-monolith package. Type-specific evaluators produce safe eligibility decisions; a credential application service applies authorization/state guards and asks one repository transaction to mutate a request/credential plus append audit. SQLAlchemy is runtime persistence; in-memory and unavailable/fake assertion adapters are test-only or safe runtime boundaries.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x async, Alembic, pytest/pytest-asyncio, Ruff, mypy.

## Global Constraints

- Credential types are exactly `COMPLETION`, `LEARNING_ACHIEVEMENT`, `COMPETENCY`; each has an independent evaluator.
- Completion/achievement runtime providers are unavailable and return `NOT_EVALUABLE`; fixture assertions are test-only and never get a public API or database table.
- A competency credential needs a matching `VERIFIED`, unexpired competency record and immutable decision/evidence/rubric/delegation references accepted by its exact active policy version.
- Clients never submit raw assertions, completion/achievement booleans, competency/evidence/rubric JSON, roles or organization authority.
- Delegation permissions are `competency.verify`, `credential.approve`, `credential.issue`, `credential.revoke`; ADMIN/SME do not bypass them.
- Every write uses actor UUID from trusted persistence, an expected version and a state/audit transaction. Audit does not store raw evidence, answer, document, PII, prompt or API key.
- No LMS delivery/progress, learning outcome owner, external AI, new service, QR/signing, registry or automatic competency transition.

---

### Task 1: Credential contracts and delegated permission vocabulary

**Files:**
- Create: `backend/app/credential/__init__.py`, `backend/app/credential/schemas.py`, `backend/app/credential/errors.py`, `backend/tests/test_credential_schemas.py`
- Modify: `backend/app/authorization/schemas.py`, `backend/app/authorization/api.py`, `backend/tests/test_delegation_repository.py`, `backend/tests/test_delegation_api.py`

**Interfaces:**
- `CredentialType`, `CredentialPolicyStatus`, `EligibilityStatus`, `CredentialRequestStatus`, `CredentialStatus` enums.
- Immutable `CredentialPolicy`, `EligibilityDecision`, `CredentialRequest`, `Credential`, `CredentialVerification` Pydantic models.
- `ScopedDelegation.permission: Literal["competency.verify", "credential.approve", "credential.issue", "credential.revoke"]` and `credential_scope` reusing the existing stored scope list.

- [ ] **Step 1: Write failing tests for contracts and delegation permission.** Assert an unknown type/status, invalid policy validity, inline assertion fields and unknown permission are rejected; assert `credential.issue` round-trips through in-memory delegation without changing `competency.verify` behavior.
- [ ] **Step 2: Run focused tests and verify RED.** Run `cd backend && uv run --extra dev pytest tests/test_credential_schemas.py tests/test_delegation_repository.py -q`; expect missing credential models and permission validation failures.
- [ ] **Step 3: Implement minimal immutable schemas and generalize delegation permission.** Keep organization/competency scope persistence compatible; interpret credential policy IDs as the scope only in credential policy code. Add safe domain exceptions with no user payload.
- [ ] **Step 4: Run focused tests to GREEN and format changed files.**
- [ ] **Step 5: Commit `feat: define credential contracts and delegated permissions`.**

### Task 2: Policy/evidence evaluator protocols and deterministic tests

**Files:**
- Create: `backend/app/credential/evaluators.py`, `backend/app/credential/providers.py`, `backend/tests/test_credential_evaluators.py`, `backend/tests/test_credential_authorization.py`
- Modify: `backend/app/competency/repository.py`

**Interfaces:**
- `CredentialEligibilityEvaluator.evaluate(input: CredentialEvaluationInput) -> EligibilityDecision`.
- `CourseCompletionAssertionProvider` and `LearningOutcomeAssertionProvider` protocols; unavailable runtime implementations and fake test implementations.
- `CompetencyCredentialEvaluator` uses reader methods `get_record`, `get_decision` and a read-only active-credential duplicate query.
- `CredentialAuthorizationPolicy.can_approve`, `.can_issue`, `.can_revoke` return `AuthorizationDecision` with delegation/policy metadata.

- [ ] **Step 1: Write failing evaluator/policy tests.** Cover unavailable completion/outcome providers (`NOT_EVALUABLE`), fake authoritative matching/wrong-version assertion, unrelated assessment rejection, verified/assessed/expired competency, missing decision/reference, duplicate active credential, no delegation, scope/org/time mismatch and requester self-approval/self-issuance.
- [ ] **Step 2: Run focused tests and verify RED.** Run `cd backend && uv run --extra dev pytest tests/test_credential_evaluators.py tests/test_credential_authorization.py -q`; expect unavailable evaluator/policy classes.
- [ ] **Step 3: Implement protocols, unavailable/fake adapters and type-specific evaluators.** Ensure fake providers are injected only in tests; unavailable providers do no I/O. Do not map a generic assessment to learning achievement.
- [ ] **Step 4: Implement application-layer credential authorization policy.** Require active delegated permission, matching organization and policy ID scope; enforce separation-of-duties in policy, not router.
- [ ] **Step 5: Run focused suite to GREEN and commit `feat: evaluate credential eligibility safely`.**

### Task 3: Persistence, immutable audit and Alembic migration

**Files:**
- Create: `backend/app/credential/models.py`, `backend/app/credential/repository.py`, `backend/alembic/versions/20260803_12_credential_policy_issuance.py`, `backend/tests/test_credential_repository.py`, `backend/tests/test_credential_sql_repository.py`
- Modify: `backend/app/shared/database.py`, `backend/tests/test_migration_config.py`

**Interfaces:**
- `CredentialRepository` methods `get_active_policy`, `create_evaluation`, `get_request`, `transition_request`, `issue`, `get_credential`, `revoke_or_expire`, `find_active_duplicate`.
- `InMemoryCredentialRepository` for unit tests, `SqlAlchemyCredentialRepository` for runtime.
- ORM records `CredentialPolicyRecord`, `CredentialRequestRecord`, `CredentialRecord`, `CredentialAuditEventRecord`.

- [ ] **Step 1: Write failing repository tests.** Assert immutable policy/version constraint, exact active lookup, optimistic request version conflict, duplicate active credential block, issue creates credential + changes request + audit atomically, revoke/expire state, safe audit metadata and rollback when `_append_audit` raises.
- [ ] **Step 2: Run focused repository tests and verify RED.**
- [ ] **Step 3: Add migration and ORM models.** Add `(policy_id, version)` uniqueness, status/index lookups, policy/request/credential FKs and a partial/transactional duplicate guard appropriate to PostgreSQL; no assertion/evidence payload columns.
- [ ] **Step 4: Implement in-memory and SQLAlchemy repositories.** Use row locks/expected versions for transitions and one transaction for all transition/audit writes. Return Pydantic snapshots, not ORM records.
- [ ] **Step 5: Run repository tests to GREEN, then run `DATABASE_URL=... uv run --extra dev alembic upgrade head` and `alembic current` against the development database.**
- [ ] **Step 6: Commit `feat: persist credential policy and issuance audit`.**

### Task 4: Credential orchestration service and policy fixtures

**Files:**
- Create: `backend/app/credential/service.py`, `backend/app/credential/fixtures.py`, `backend/tests/test_credential_service.py`
- Modify: `backend/app/authorization/fixtures.py`, `backend/app/main.py`

**Interfaces:**
- `CredentialService.evaluate_and_request`, `.approve`, `.reject`, `.issue`, `.revoke`, `.expire_if_due`, `.verify_public`.
- `CredentialPolicyRegistry` provides active versioned policies; fixture policy includes a competency policy requiring distinct requester/approver/issuer and no active duplicate.

- [ ] **Step 1: Write failing service tests.** Cover eligible → pending approval, ineligible/not-evaluable/requires-review audit without issue path, approved-only issue, policy version snapshot, revoked/expired public invalid result, no disclosure of subject/evidence, and audit failure rollback.
- [ ] **Step 2: Run service tests and verify RED.**
- [ ] **Step 3: Implement service orchestration.** Resolve exact policy first, evaluate before creating an issuable request, run delegated policy guards on every lifecycle command and preserve policy/evaluator/delegation/correlation metadata.
- [ ] **Step 4: Wire runtime SQL repository, policy registry, unavailable providers and authorization policy in `create_app`.** No model/provider HTTP call is introduced.
- [ ] **Step 5: Run focused tests to GREEN and commit `feat: orchestrate credential approval and issuance`.**

### Task 5: FastAPI endpoints, API safety and OpenAPI

**Files:**
- Create: `backend/app/credential/api.py`, `backend/tests/test_credential_api.py`, `backend/tests/test_credential_openapi.py`
- Modify: `backend/app/main.py`, `backend/app/shared/errors.py`

**Interfaces:**
- `POST /credential-requests`, `GET /credential-requests/{request_id}`.
- `POST /credential-requests/{request_id}/approve`, `/reject`, `/issue`.
- `POST /credentials/{credential_id}/revoke`, `/expire`; `GET /credentials/{credential_id}/verify`.

- [ ] **Step 1: Write failing ASGI tests.** Cover UUID identity, no raw/inline assertions accepted, authorization 403s, expected-version 409, approve/reject/issue/revoke/expire paths, safe verification output for issued/expired/revoked/unknown credential and OpenAPI error declarations.
- [ ] **Step 2: Run API tests and verify RED.**
- [ ] **Step 3: Implement request/response models, router mapping and safe errors.** Keep lifecycle/eligibility logic entirely in `CredentialService`; public verify has no actor dependency and returns no subject/evidence/audit fields.
- [ ] **Step 4: Register router in application factory and run API/OpenAPI tests to GREEN.**
- [ ] **Step 5: Commit `feat: expose credential issuance and verification API`.**

### Task 6: Golden harness, documentation and verification

**Files:**
- Create: `backend/tests/golden/credential_policy_issuance.json`, `backend/tests/test_golden_credential.py`
- Modify: `docs/domain/three-layer-assessment.md`, `docs/security/authorization.md`, `README.md`

- [x] **Step 1: Add golden cases.** Include unavailable/fake completion and outcome sources, verified/assessed/expired competency, revoked evidence/rubric, conflict/requires-review, approval-required, duplicate policy, delegation scope failure, expiry/revocation and deterministic re-evaluation.
- [x] **Step 2: Run the golden test before final suite.** Assert safe audit/public verification never contains raw assertion/evidence/subject PII.
- [x] **Step 3: Update domain/security/API documentation.** State credential distinctions, scopes, lifecycle, public verification redaction and PR-008 non-goals.
- [x] **Step 4: Run final verification.** From `backend/`: `uv run --extra dev pytest -q`, `uv run --extra dev ruff format --check .`, `uv run --extra dev ruff check .`, `uv run --extra dev mypy app`; then run Alembic upgrade/current against development PostgreSQL and `pre-commit run --all-files` from repository root.
- [x] **Step 5: Terra review gate.** Inspect `git diff khanhtruong...HEAD`, map every ADR/spec constraint to code/tests, check no raw data leaks or direct provider call, and record concrete Luna fixes if any.
- [x] **Step 6: Commit `test: add credential policy golden harness`.**
