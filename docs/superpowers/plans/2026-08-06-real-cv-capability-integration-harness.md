# Real CV Capability Integration Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a controlled seed fixture and operator-run harness that verifies capability analysis with one real CV and a synthetic, pre-approved role target.

**Architecture:** A dedicated seed module creates the accepted synthetic JD profile and immutable active `RoleCompetencyProfile` required by the existing service. An integration runner validates a locally supplied CV hash, calls the public API in the same order as a user workflow, and records only safe IDs/statuses. Cleanup is opt-in and constrained to run-scoped IDs.

**Tech Stack:** Python 3.13, SQLAlchemy async, FastAPI/httpx, Docker Compose, pytest, existing document/extraction/capability APIs.

## Global Constraints

- Never commit, fixture, log, snapshot, or print raw CV/JD content.
- Do not create role profiles from uploaded JD data; the seed target is synthetic test metadata.
- Use only existing API endpoints after seed creation; no inline CandidateProfile, evidence or role payload enters capability analysis.
- Require `PAI_REAL_CV_PATH` and matching `PAI_REAL_CV_SHA256`; reject an unset/mismatched path before upload.
- Keep cleanup disabled unless `PAI_REAL_CV_CLEANUP=true`; delete only exact run-scoped IDs.
- Assert provisional capability output, distinct current-role assessments/gaps, no combined score, and audit/API redaction.
- The public portfolio does not expose or persist `ProvisionalCurrentCapabilityProfile`.
  Keep its `verification_status=provisional` assertion in the existing
  rule-level contract test; the live harness asserts that API output is
  preliminary-safe and does not make verified/assessed claims.

---

### Task 1: Add deterministic seed target and seed tests

**Files:**
- Create: `backend/app/capability_analysis/integration_seed.py`
- Create: `backend/scripts/seed_real_cv_capability_integration.py`
- Test: `backend/tests/test_capability_analysis_integration_seed.py`

**Interfaces:**
- Produces `async seed_real_cv_capability_target(session_factory) -> SeededCapabilityTarget`.
- Returns `target_profile_id`, `target_profile_version`, and `source_jd_profile_id` only.
- Persists a succeeded synthetic JD extraction job plus
  `seed-real-cv-capability-jd` version `1` as accepted, then
  `seed-real-cv-capability-target` version `1.0` as active.

- [ ] **Step 1: Write failing seed idempotency and sentinel tests**

```python
@pytest.mark.asyncio
async def test_seed_creates_accepted_jd_and_active_target_once(session_factory) -> None:
    first = await seed_real_cv_capability_target(session_factory)
    second = await seed_real_cv_capability_target(session_factory)

    assert second == first
    assert first.target_profile_id == "seed-real-cv-capability-target"
    assert await accepted_jd_exists(session_factory, first.source_jd_profile_id, version=1)
    assert await target_has_requirement(
        session_factory, first.target_profile_id, "seed-integration-unavailable-signal"
    )
```

- [ ] **Step 2: Run RED test**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_integration_seed.py -q`

Expected: FAIL because the seed module does not exist.

- [ ] **Step 3: Implement bounded seed data**

```python
SENTINEL_REQUIREMENT_ID = "seed-integration-unavailable-signal"
SENTINEL_EVIDENCE_TERM = "seed-integration-unavailable-signal"

async def seed_real_cv_capability_target(
    session_factory: async_sessionmaker[AsyncSession],
) -> SeededCapabilityTarget:
    # Read exact IDs/versions first; insert only when absent; reject conflicts.
```

Create the synthetic JD `ExtractionJob` first, with deterministic ID, `SUCCEEDED`
status and a deterministic profile ID. Create its JD `ExtractionProfile` with
`DocumentKind.JD`, `ReviewState.ACCEPTED`, empty structured output and safe audit
metadata. Save a role profile with Python, FastAPI and sentinel requirements,
source JD ID/version, fixed rule/policy versions and `RoleProfileStatus.ACTIVE`.

- [ ] **Step 4: Run GREEN test**

Run: `cd backend && uv run --extra dev pytest tests/test_capability_analysis_integration_seed.py -q`

Expected: PASS; reruns do not create duplicate versions and the sentinel exists.

- [ ] **Step 5: Add operator seed entrypoint and commit**

```bash
git add backend/app/capability_analysis/integration_seed.py backend/scripts/seed_real_cv_capability_integration.py backend/tests/test_capability_analysis_integration_seed.py
git commit -m "test: seed real CV capability integration target"
```

The entrypoint calls `create_app()`, invokes the seed function with the runtime
session factory, prints only `target_profile_id`, `target_profile_version` and
`source_jd_profile_id`, and disposes the database.

### Task 2: Add safe real-CV API harness and unit tests

**Files:**
- Create: `backend/scripts/run_real_cv_capability_integration.py`
- Create: `backend/tests/test_real_cv_capability_integration_harness.py`
- Modify: `README.md`

**Interfaces:**
- Consumes environment variables `PAI_API_BASE_URL`, `PAI_REAL_CV_PATH`,
  `PAI_REAL_CV_SHA256`, `PAI_TARGET_PROFILE_ID`, and optional
  `PAI_REAL_CV_CLEANUP`.
- Produces a JSON-safe result containing opaque IDs, job/profile state,
  portfolio ID and assertion outcomes.

- [ ] **Step 1: Write failing preflight and redaction tests**

```python
def test_preflight_rejects_hash_mismatch_without_reading_or_uploading_content(tmp_path) -> None:
    cv_path = tmp_path / "candidate.pdf"
    cv_path.write_bytes(b"private CV bytes")

    with pytest.raises(IntegrationPreflightError, match="sha256"):
        validate_real_cv_input(cv_path, expected_sha256="0" * 64)


def test_safe_result_never_contains_document_content() -> None:
    result = safe_result(document_id="doc-1", portfolio_id="portfolio-1")
    assert "content" not in result
    assert "excerpt" not in result
```

- [ ] **Step 2: Run RED test**

Run: `cd backend && uv run --extra dev pytest tests/test_real_cv_capability_integration_harness.py -q`

Expected: FAIL because the harness helpers do not exist.

- [ ] **Step 3: Implement preflight, polling and assertions**

```python
async def run_integration(config: RealCVIntegrationConfig) -> SafeIntegrationResult:
    validate_real_cv_input(config.cv_path, config.expected_sha256)
    document = await upload_cv(config)
    job = await create_extraction_job(document["id"])
    profile = await poll_succeeded_profile(job["id"])
    accepted = await accept_profile(profile["id"], profile["version"])
    portfolio = await create_portfolio(accepted["id"], config.target_profile_id)
    assert_portfolio_contract(portfolio)
    return safe_result(...)
```

Use `X-PAI-Actor-ID` learner/reviewer IDs from migration `20260803_08`. Poll
only job status/profile ID, bound retries and timeout, and redact every HTTP
failure to status/error code/correlation ID. Send this exact analysis payload:

```json
{
  "cv_profile_id": "<accepted-cv-profile-id>",
  "current_target_profile_id": "seed-real-cv-capability-target",
  "correlation_id": "real-cv-run-<opaque-suffix>"
}
```

Assert `201`, `current_role` target type, `official` usage mode for the active
seed, target-local gaps, sentinel gap, no combined score, and no
raw/excerpt/CandidateProfile response field. Run the existing
`test_provisional_current_capability_profile_is_immutable_and_source_referenced`
contract alongside this harness
to assert `verification_status=provisional`; do not claim the portfolio API
returns that internal non-persisted profile.

- [ ] **Step 4: Run GREEN test**

Run: `cd backend && uv run --extra dev pytest tests/test_real_cv_capability_integration_harness.py -q`

Expected: PASS; no test output or result contains raw CV text.

- [ ] **Step 5: Document exact operator commands and commit**

```bash
bash devops/scripts/init-network.sh
docker compose -f devops/database/docker-compose.yml up -d
docker compose -f devops/redis/docker-compose.yml up -d
docker compose -f devops/minio/docker-compose.yml up -d
docker compose -f devops/backend/docker-compose.yml up -d --build
docker compose -f devops/backend/docker-compose.yml exec backend uv run alembic upgrade head
curl --fail "$PAI_API_BASE_URL/health/ready"
docker compose -f devops/backend/docker-compose.yml exec backend uv run python -m scripts.seed_real_cv_capability_integration
PAI_REAL_CV_PATH=/absolute/path/cv.pdf PAI_REAL_CV_SHA256=<sha256> PAI_TARGET_PROFILE_ID=seed-real-cv-capability-target uv run python -m scripts.run_real_cv_capability_integration
```

```bash
git add backend/scripts/run_real_cv_capability_integration.py backend/tests/test_real_cv_capability_integration_harness.py README.md
git commit -m "test: add real CV capability integration harness"
```

### Task 3: Add live-stack acceptance procedure and opt-in cleanup

**Files:**
- Create: `docs/testing/real-cv-capability-integration.md`
- Modify: `README.md`
- Test: `backend/tests/test_real_cv_capability_integration_harness.py`

**Interfaces:**
- Cleanup accepts a `SafeIntegrationResult` and never discovers targets through
  broad table scans.
- Produces `cleanup_completed` or a safe list of unreleased opaque IDs.

- [ ] **Step 1: Write failing cleanup scope test**

```python
@pytest.mark.asyncio
async def test_cleanup_deletes_only_run_scoped_identifiers(repository) -> None:
    result = SafeIntegrationResult(document_id="doc-run", portfolio_id="portfolio-run", ...)
    await cleanup(result, enabled=True)

    assert await repository.get("portfolio-run") is None
    assert await repository.get("portfolio-unrelated") is not None
```

- [ ] **Step 2: Run RED test**

Run: `cd backend && uv run --extra dev pytest tests/test_real_cv_capability_integration_harness.py -q`

Expected: FAIL because cleanup is not implemented.

- [ ] **Step 3: Implement explicit cleanup and acceptance checklist**

Require `PAI_REAL_CV_CLEANUP=true`; reject all other values. Delete in child-to-
parent order using exact run IDs, including portfolio children/audit, extraction
profile/job, stored document record and exact object key. Never truncate tables,
delete by owner, or infer paths from CV filename. Document manual verification
of MinIO object removal and container logs without raw payloads.

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
cd backend && uv run --extra dev pytest tests/test_capability_analysis_integration_seed.py tests/test_real_cv_capability_integration_harness.py -q
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run --extra dev pytest -q
```

Expected: all commands exit `0`.

- [ ] **Step 5: Record live acceptance and commit documentation**

Run the commands in `docs/testing/real-cv-capability-integration.md` with a
consented CV. Record only service versions, opaque IDs, success/failure status,
and cleanup result in a local operator log. Do not commit that log or the CV.

```bash
git add docs/testing/real-cv-capability-integration.md README.md backend/tests/test_real_cv_capability_integration_harness.py
git commit -m "docs: define real CV capability integration acceptance"
```

## Plan Self-Review

- Scope is limited to a seeded role target plus CV integration; no JD-to-role
  authoring task appears here.
- Seed data creates the accepted source-JD record demanded by the existing
  capability service without handling a raw JD.
- Every task has a red/green verification, bounded data handling and a commit.
- The operator command requires explicit CV path/hash and opt-in cleanup.
