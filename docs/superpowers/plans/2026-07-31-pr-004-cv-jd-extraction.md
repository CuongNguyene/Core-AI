# PR-004 CV/JD Extraction Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide fixture-backed, asynchronously processed CV/JD extraction
profiles with source evidence, review correction, API ownership and safe audit
metadata.

**Architecture:** The API writes/reads jobs and profiles only. A separate worker
claims a job and calls the internal ModelGateway. Fixtures are the sole document
source. Domain schemas represent evidence/profile states without competency
verification; repositories isolate SQLAlchemy persistence from API/domain code.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy async, Alembic,
pytest-asyncio and the PR-003 ModelGateway.

## Global Constraints

- Do not accept/store/log raw CV/JD or expose upload/object-storage APIs.
- All model calls run in worker code, never FastAPI router code.
- Every supported claim has a source locator; unknown/insufficient claims are
  explicit and no extraction state is competency verified.
- API uses development-only actor headers from ADR-0007 and fails closed outside
  development.
- Audit metadata excludes raw prompt, payload and model output.

---

### Task 1: Extraction schemas, fixture source and prompt registration

**Files:**
- Create: `app/extraction/schemas.py`
- Create: `app/extraction/fixtures.py`
- Create: `app/extraction/prompts.py`
- Test: `tests/test_extraction_schemas.py`

**Interfaces:**
- Produces `DocumentKind`, `SourceLocator`, `EvidenceStatus`, CV/JD profile
  schemas and `FixtureDocumentSource`.
- Consumed by persistence/worker in Tasks 2–3.

- [ ] **Step 1: Write failing source-evidence tests**

```python
def test_supported_claim_requires_source_locator() -> None:
    with pytest.raises(ValidationError):
        ExtractedClaim(value="Python", evidence_status="supported")
```

```python
def test_unknown_claim_has_no_invented_evidence() -> None:
    claim = ExtractedClaim(value=None, evidence_status="unknown")
    assert claim.source_locator is None
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_extraction_schemas.py -q`

Expected: import error for `app.extraction`.

- [ ] **Step 3: Implement fixture contracts**

Define strict CV/JD Pydantic outputs, versioned trusted prompts and two no-PII
fixture documents with stable locator spans.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_extraction_schemas.py -q`

Expected: pass.

### Task 2: Job/profile persistence and migration

**Files:**
- Create: `app/extraction/models.py`
- Create: `app/extraction/repository.py`
- Create: `alembic/versions/20260731_02_extraction_slice.py`
- Test: `tests/test_extraction_repository.py`

**Interfaces:**
- Produces `ExtractionRepository` methods `enqueue`, `claim_next`,
  `mark_succeeded`, `mark_failed`, `get_job`, `get_profile`, `create_correction`.
- Consumed by worker/API in Tasks 3–4.

- [ ] **Step 1: Write failing lifecycle test**

```python
async def test_claimed_job_transitions_to_succeeded_with_pending_profile() -> None:
    job = await repository.enqueue(new_job)
    claimed = await repository.claim_next()
    await repository.mark_succeeded(claimed.id, profile)
    assert (await repository.get_job(job.id)).status == JobStatus.SUCCEEDED
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_extraction_repository.py -q`

Expected: import error for extraction persistence.

- [ ] **Step 3: Implement models and migration**

Persist only IDs, normalized profiles/evidence JSON and safe audit metadata; no
raw document/model fields. Use versioned profiles and owner actor IDs.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_extraction_repository.py -q`

Expected: pass with deterministic in-memory repository; validate migration
offline SQL separately.

### Task 3: Worker and ModelGateway execution

**Files:**
- Create: `app/extraction/worker.py`
- Test: `tests/test_extraction_worker.py`

**Interfaces:**
- Consumes fixture source, prompt/schema registry, ModelGateway and repository.
- Produces a succeeded pending-review profile or safe failed job category.

- [ ] **Step 1: Write failing worker test**

```python
async def test_worker_creates_pending_review_profile_from_cv_fixture() -> None:
    await worker.run_once()
    profile = await repository.get_profile_for_job(job.id)
    assert profile.review_state is ReviewState.PENDING_REVIEW
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_extraction_worker.py -q`

Expected: import error for worker.

- [ ] **Step 3: Implement one-job worker**

Claim exactly one queued job, form a restricted inference request from fixture
text, dispatch matching CV/JD schema, persist safe audit metadata and never
upgrade competency state.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_extraction_worker.py -q`

Expected: pass.

### Task 4: Development API and human correction

**Files:**
- Create: `app/extraction/api.py`
- Create: `app/extraction/auth.py`
- Modify: `app/main.py`
- Test: `tests/test_extraction_api.py`

**Interfaces:**
- Consumes repository protocol.
- Produces four API endpoints and safe error/authorization behavior.

- [ ] **Step 1: Write failing API tests**

```python
async def test_create_job_requires_actor_header() -> None:
    response = await client.post("/extraction-jobs", json=fixture_request)
    assert response.status_code == 403


async def test_reviewer_correction_creates_new_profile_version() -> None:
    response = await client.post(correction_url, headers=reviewer_headers, json=correction)
    assert response.json()["version"] == 2
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_extraction_api.py -q`

Expected: 404 because router is not registered.

- [ ] **Step 3: Implement API boundary**

Use actor headers only in development, scope owner reads, require reviewer role
for correction, and map domain failures to existing safe `APIError` contract.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_extraction_api.py -q`

Expected: pass.

### Task 5: Golden harness, README and verification

**Files:**
- Create: `tests/golden/cv_basic.json`
- Create: `tests/golden/jd_basic.json`
- Create: `tests/test_golden_extraction.py`
- Modify: `README.md`
- Modify: plan checklist

- [ ] **Step 1: Write failing golden comparison test**

```python
async def test_cv_fixture_matches_golden_profile() -> None:
    profile = await run_fixture("fixture-cv-basic")
    assert profile.model_dump(mode="json") == load_golden("cv_basic.json")
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_golden_extraction.py -q`

Expected: missing golden fixture/harness.

- [ ] **Step 3: Implement harness and runbook**

Use mock provider responses for deterministic fixture extraction; document worker
boundary, fixture-only restriction, actor headers and test command.

- [ ] **Step 4: Verify GREEN and commit locally**

Run: `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q && uv run pre-commit run --all-files`

Expected: exit 0, then commit with `feat: add cv jd extraction slice`.
