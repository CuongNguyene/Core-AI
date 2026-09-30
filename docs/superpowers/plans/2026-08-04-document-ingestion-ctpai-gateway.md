# Document Ingestion and CTPAI Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add development PDF/DOCX ingestion through MinIO and CTPAI Gateway-backed, reviewable CV/JD extraction.

**Architecture:** A documents module owns raw-object metadata, quarantine and object-store access; extraction consumes an eligible `DocumentSource`. A provider adapter maps the existing internal ModelGateway request to CTPAI's `/generate` contract while PrivacyGateway and routing retain control.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, MinIO Python client, pypdf, python-docx, httpx, Pydantic v2, pytest.

## Global Constraints

- PDF/DOCX raw bytes and parsed text are never stored in SQL/audit/logs.
- Only `CLEAN` and non-expired documents can be extracted.
- CTPAI provider ID is `local-vllm`; restricted data remains local-only and passes PrivacyGateway first.
- All new actor/resource authorization resolves from trusted UUID subject persistence.
- Development MinIO is not a production storage decision.

---

### Task 1: Document metadata and storage boundary

**Files:** create `app/documents/{schemas,models,repository,storage,safety}.py`; create migration; modify config and dependency lock; test `tests/test_documents.py`.

**Interfaces:** Produce `StoredDocument`, `DocumentStatus`, `DocumentRepository`, `DocumentBlobStore`, and `DocumentSafetyInspector` for upload and worker callers.

- [x] Write failing tests for opaque object keys, allowed PDF/DOCX signatures, state/retention eligibility and no raw data in metadata.
- [x] Run `pytest tests/test_documents.py -q` and verify failure because module is absent.
- [x] Implement schema/model/repository/blob/safety adapters and migration; use a development MinIO adapter plus in-memory test adapters.
- [x] Run `pytest tests/test_documents.py -q` and verify pass.
- [x] Commit `feat: add quarantined document storage boundary`.

### Task 2: Upload API and clean-document source

**Files:** create `app/documents/api.py`; modify `main.py`, extraction document-source composition and extraction API; test `tests/test_document_api.py` and extraction API eligibility cases.

**Interfaces:** `POST /documents` returns safe `StoredDocument`; `CompositeDocumentSource.get(document_id, kind)` resolves fixtures or CLEAN stored parsed content.

- [x] Write failing upload authorization/type/size/quarantine tests and extraction rejection for non-CLEAN document.
- [x] Run targeted tests and verify expected failure.
- [x] Implement multipart upload with state gate, trusted actor ownership, and worker-only parse adapter.
- [x] Run targeted tests and verify pass.
- [x] Commit `feat: upload clean documents for extraction`.

### Task 3: CTPAI ModelGateway provider

**Files:** create `app/model_gateway/ctpai_gateway.py`; modify gateway composition/config; test `tests/test_ctpai_gateway.py` and `tests/test_model_gateway.py`.

**Interfaces:** `CTPAIGatewayProvider.complete(ProviderRequest) -> ProviderResponse` posts model, prompt_system, prompt_user, temperature, max_tokens and stream=false, with bearer authorization and configured timeout.

- [x] Write failing contract tests for payload, header redaction, timeout/retry, error response, response text extraction and invalid response.
- [x] Run targeted tests and verify expected failure.
- [x] Implement the provider and composition root registration under `local-vllm`; preserve PrivacyGateway/routing before provider resolution.
- [x] Run targeted tests and verify pass.
- [x] Commit `feat: add internal ctai gateway provider`.

### Task 4: Worker integration and end-to-end harness

**Files:** modify extraction worker/composition; create parser fixture tests and `tests/test_document_extraction_integration.py`; update ADR-0006 references and API docs.

**Interfaces:** A queued CLEAN stored PDF/DOCX results in a `PENDING_REVIEW` profile with schema-valid output and safe audit metadata, or a safe failed job.

- [x] Write failing integration tests for CV and JD paths, invalid model JSON, parser failure and audit redaction.
- [x] Run targeted tests and verify expected failure.
- [x] Wire document source and ModelGateway into worker runtime; retain fixture-backed golden tests.
- [x] Run all backend tests, Ruff, mypy and Alembic head check; verify pass.
- [ ] Commit `feat: extract uploaded documents through ctai gateway`.
