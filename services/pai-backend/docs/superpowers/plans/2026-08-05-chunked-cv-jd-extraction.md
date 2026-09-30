# Chunked CV/JD Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract long restricted CV/JD documents in deterministic chunks, with a trusted 2048 output budget per chunk, into one reviewable profile.

**Architecture:** ModelGateway accepts a trusted output budget and passes it to providers under an 8192 ceiling. The worker splits normalized document text and calls the unchanged PrivacyGateway/local-vLLM route sequentially. Internal chunk schemas require source excerpts; deterministic application logic locates, validates and merges claims into the existing profile schema.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy async, httpx, pytest, Ruff and mypy.

## Global Constraints

- Raw CV/JD, chunks, prompts and responses never enter SQL, audit metadata or logs.
- Restricted data remains local-only through ModelGateway then PrivacyGateway.
- Provider ceiling is 8192; initial CV/JD chunk budget is 2048.
- Chunks are sequential, deterministic and worker-only; there is no public chunk API.
- Source excerpts must occur exactly once in their chunk before a final locator exists.
- A chunk failure fails the whole job closed and creates no profile.
- Chunk extraction and merge never verify competency or make a hiring decision.

---

### Task 1: Trusted output budget propagation

**Files:**
- Modify: `backend/app/model_gateway/contracts.py`, `backend/app/model_gateway/service.py`, `backend/app/model_gateway/ctpai_gateway.py`
- Modify: `backend/app/shared/config.py`, `backend/app/main.py`, `backend/.env.example`
- Test: `backend/tests/test_model_gateway.py`, `backend/tests/test_ctpai_gateway.py`, `backend/tests/test_settings.py`

**Interfaces:** `InferenceRequest.output_token_budget: int | None`; `CTPAIGatewayProvider` has a validated `max_output_tokens=8192` ceiling; settings expose `cv_jd_extraction_max_tokens=2048`.

- [ ] Write failing tests proving a structured inference propagates `output_token_budget=2048`, a provider rejects 8193 before HTTP, and settings reject an extraction budget above its ceiling.
- [ ] Run `uv run pytest -q tests/test_model_gateway.py tests/test_ctpai_gateway.py tests/test_settings.py`; confirm the missing budget flow causes failure.
- [ ] Add the typed request field, pass it from `ModelGatewayService` to `ProviderRequest.max_tokens`, validate it in `CTPAIGatewayProvider`, and configure 8192 ceiling plus 2048 extraction default.
- [ ] Re-run the focused tests; confirm they pass and no external call occurs for an over-ceiling request.
- [ ] Commit: `feat: add trusted inference output budgets`.

### Task 2: Deterministic chunks and internal candidate schema

**Files:**
- Create: `backend/app/extraction/chunking.py`
- Modify: `backend/app/extraction/schemas.py`, `backend/app/extraction/prompts.py`
- Test: `backend/tests/test_extraction_chunking.py`, `backend/tests/test_extraction_schemas.py`, `backend/tests/test_model_contracts.py`

**Interfaces:** `TextChunk(ordinal, start_offset, end_offset, text)` and `split_document(content, max_chars=2000, overlap_chars=150) -> list[TextChunk]`. `CVChunkExtractionOutput`/`JDChunkExtractionOutput` contain candidate claims without model-supplied locators.

- [ ] Write failing tests for newline-preferred splits, 150-character overlap, short final chunk and invalid chunk settings; add a supported candidate test requiring only value/confidence/bounded excerpt.
- [ ] Run `uv run pytest -q tests/test_extraction_chunking.py tests/test_extraction_schemas.py tests/test_model_contracts.py`; confirm the new module/contracts are absent.
- [ ] Implement forward-progress chunking and trusted chunk prompt/schema registrations. Unknown/insufficient candidates must carry neither value nor excerpt.
- [ ] Re-run focused tests; confirm deterministic ranges and prompt injection boundaries remain intact.
- [ ] Commit: `feat: add deterministic extraction chunks`.

### Task 3: Evidence location and deterministic merge

**Files:**
- Create: `backend/app/extraction/merge.py`
- Test: `backend/tests/test_extraction_merge.py`

**Interfaces:** `locate_candidate(chunk, document, excerpt) -> SourceLocator` and `merge_chunk_outputs(document, chunks, outputs) -> CVExtractionOutput | JDExtractionOutput`.

- [ ] Write failing tests for one exact excerpt mapping to a document-relative locator, overlap deduplication, retained non-overlapping evidence, missing excerpt and ambiguous excerpt failure.
- [ ] Run `uv run pytest -q tests/test_extraction_merge.py`; confirm the module does not exist.
- [ ] Implement exact excerpt matching within each chunk, document-relative locator construction, whitespace/case-only normalization for deduplication and document-order preservation. Do not aggregate confidence.
- [ ] Re-run focused tests; confirm ambiguous/missing evidence fails closed and no LLM merge occurs.
- [ ] Commit: `feat: merge chunked extraction evidence`.

### Task 4: Worker orchestration and integration verification

**Files:**
- Modify: `backend/app/extraction/worker.py`, `backend/app/extraction/prompts.py`
- Test: `backend/tests/test_extraction_worker.py`, `backend/tests/test_document_extraction_integration.py`, `backend/tests/test_golden_extraction.py`
- Modify: `docs/superpowers/specs/2026-08-04-document-ingestion-ctpai-gateway-design.md`, `backend/be_document.md`

**Interfaces:** Worker invokes `split_document`, submits chunks in ordinal order with `output_token_budget=2048`, merges only after all calls validate, and uses safe category `chunk_<ordinal>:<safe_category>` on failure.

- [ ] Write failing worker tests proving sequential requests use 2048, a multi-chunk fake document persists one merged profile, and a second-chunk failure creates no profile with a safe chunk category.
- [ ] Run `uv run pytest -q tests/test_extraction_worker.py tests/test_document_extraction_integration.py tests/test_golden_extraction.py`; confirm the current worker makes a single request and fails these tests.
- [ ] Implement worker orchestration and aggregate-only audit metadata. Never persist raw chunk text, excerpts in errors or model output.
- [ ] Run `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q && uv run alembic heads && bash ../devops/scripts/test-compose-config.sh`.
- [ ] Rebuild the dedicated worker and run supplied CV/JD through the API. Record only job status, profile ID/audit-safe metadata and safe log categories.
- [ ] Commit: `feat: extract restricted documents in chunks`.
