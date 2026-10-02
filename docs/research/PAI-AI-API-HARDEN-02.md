# PAI-AI-API-HARDEN-02 — E2E FIXTURE + DATA-BACKED LIVE SMOKE

## Status

COMPLETE_WITH_EXPLICIT_BLOCKERS. Bootstrap and non-model read smoke passed where dependencies existed; storage and fresh capability creation remain explicitly blocked.

## 1. Repository / Preflight

Canonical repo: `/Users/mac/Developers/work/LMS/Core-AI` (runtime source; `.git` metadata is absent). Branch/HEAD: not available in canonical source. Recovery clone retained separately at `/private/tmp/core-ai-push-recovery-20261001`, branch `feat/deterministic-ai-course-planning-workspace`, HEAD `a6ef1d9632da6ed6e23e8d266e18ab124bd00222`. Health/readiness: HTTP 200. MinIO: HTTP 200. ClamAV: PONG from backend network. Workers: stopped. Model provider: placeholder/unavailable. LMS: unchanged.

## 2. Bootstrap Failure Reproduction

Command: `PYTHONPATH=. uv run --extra dev python scripts/bootstrap_e2e_fixtures.py`. Failure before fix: `asyncpg expected str, got UUID` at the new `ExtractionJobRecord` insert for `extraction_jobs.document_id`. Python value: UUID. Persistence expectation: text/string.

## 3. document_id Contract

| Layer | File | Declared Type | Runtime Type | Notes |
|---|---|---|---|---|
| Schema/domain | `app/extraction/schemas.py` | `str` | string reference | API extraction job contract |
| SQLAlchemy | `app/extraction/models.py` | `Mapped[str]` / `String(128)` | text | `extraction_jobs.document_id` |
| Migration | `alembic/versions/20260731_02_extraction_slice.py` | `sa.String(128)` | text | authoritative DB column |
| Repository | `app/extraction/repository.py` | `str` | string | repository boundary |
| API | `app/extraction/api.py` | `str` | string | request field |

Canonical type: string/text at the extraction persistence boundary.

## 4. Root Cause

Classification: `FIXTURE_DEFECT`. The fixture already serialized the UUID in its update/profile paths but passed the UUID object in the new-record path. Production contract defect: NO. Migration defect: NO. Fixture defect: YES.

## 5. Fix

Files changed: `scripts/bootstrap_e2e_fixtures.py`, `tests/test_e2e_fixture_bootstrap.py`, plus the two HARDEN-01 test fixtures. Change: added `_document_id_for_persistence()` and used it for new extraction job/profile records. Production schema changed: NO. Production domain changed: NO.

## 6. Regression Test

Test: `tests/test_e2e_fixture_bootstrap.py`. Before: collection failed because the serializer helper was absent. After: `1 passed`. Result: PASS.

## 7. Fixture Bootstrap

First run: exit code 0. Second run: exit code 0 and identical manifest. Synthetic records include candidate `08b10000-0000-4000-8000-000000000001`, accepted CV/JD profiles, role draft/active profiles, persisted capability portfolios and historical learning path. No manual SQL INSERT/UPDATE was used.

## 8. Storage Boundary

Application put/read/delete through `MinioDocumentBlobStore`: put blocked by `NoSuchBucket: pai-documents`; read/delete not run. MinIO itself was healthy and ClamAV returned PONG. Result: `BLOCKED_BY_STORAGE`; no bucket was created directly.

## 9. CV / Candidate

Synthetic extraction job `e2e-cv-job-08b1` and accepted CV profile `e2e-cv-profile-08b1` both returned HTTP 200. Candidate projection was returned in live capability reads. Actual extraction execution was not run because the worker/model boundary is unavailable. Final status: prebuilt synthetic Candidate Profile `VERIFIED`; extraction execution `BLOCKED_BY_MODEL`.

## 10. JD / Role

JD profile, JD review projection, role, role-profile draft and active competency profile each returned HTTP 200. Draft state was `draft`; active profile state was `active`. Model-backed JD extraction was not run. Final status: prebuilt role lifecycle reads `VERIFIED`; extraction execution `BLOCKED_BY_MODEL`.

## 11. Capability Analysis

Persisted positive and negative portfolios returned HTTP 200 through the signed integration API and reloaded canonical candidate/role/profile data. Positive evidence states were `supported`, `insufficient`, and `not_found_in_evidence`; negative evidence was `not_found_in_evidence`. Usage mode was `preview`, with explicit provisional/source-preview warnings and no verification queue entries. A fresh create reached product code but returned `409 semantic_policy_not_configured`; therefore fresh analysis is `BLOCKED_BY_DATA`, while persisted read projection is `VERIFIED`.

## 12. Capability Governance

| Scenario | Expected | Actual | Result |
|---|---|---|---|
| Provisional target | Preview only | `usage_mode=preview`, provisional warning | VERIFIED |
| Active profile read | Active profile exposed | HTTP 200, `status=active` | VERIFIED |
| Missing semantic policy | Reject fresh analysis without policy | HTTP 409 `semantic_policy_not_configured` | BLOCKED_BY_DATA |
| Forbidden transitions/cross-owner/cross-org | Reject | Existing governance/auth tests passed | VERIFIED by regression |

No direct DB status transition was performed.

## 13. Learning Need

API exposed: `/api/v1/authoring/learning-needs/{learning_need_id}`. A negative synthetic TargetGap projected to Learning Need with HTTP 200, source gap ref preserved, target `working`, and no current level. A supported gap returned HTTP 404 as `learning_need_not_found`, which is the correct non-learning projection. TargetGap was not mutated. Final status: `VERIFIED` for the non-model projection.

## 14. Worker Dependencies

| Capability | Worker Needed | Running? | Tested? | Status |
|---|---:|---:|---:|---|
| CV/JD extraction | Yes | No | No | BLOCKED_BY_MODEL |
| Capability Analysis read/create | No | No | Read yes; create policy-blocked | BLOCKED_BY_DATA for create |
| Learning Need projection | No | No | Yes | VERIFIED |
| Learning Path read | No | No | Isolated read yes | VERIFIED |

## 15. Model Dependencies

| Capability | Model Required | Automated Contract | Live | Status |
|---|---:|---|---|---|
| CV extraction | Yes | PASS | Not run | BLOCKED_BY_MODEL |
| JD extraction | Yes | PASS | Not run | BLOCKED_BY_MODEL |
| Conversational Brief | Yes | PASS/covered by prior baseline | Not run | BLOCKED_BY_MODEL |
| Curriculum generation | Yes | PASS/covered by prior baseline | Not run | BLOCKED_BY_MODEL |
| Content generation | Yes | PASS | Not run | BLOCKED_BY_MODEL |

## 16. Non-Model Curriculum Reads

No valid synthetic persisted curriculum plan was available. Generation was not attempted with the placeholder provider. Status: `BLOCKED_BY_MODEL` for generation and `BLOCKED_BY_DATA` for data-backed plan reads.

## 17. Recommendation

Internal: persisted capability projections expose provisional recommendation references, but no independent catalog-backed recommendation API smoke was run. Status: `BLOCKED_BY_DATA`. External: provider not configured. Status: `BLOCKED_BY_EXTERNAL_DEPENDENCY`.

## 18. Learning Path

Historical synthetic learning path `e2e-historical-learning-path-08b1` returned HTTP 200 in an isolated signed read, with source capability analysis, gap refs, evidence refs, preview-safe metadata and `ready_for_review=true`. Status: `VERIFIED` for the existing non-model read projection.

## 19. Regression

Bootstrap regression: `1 passed`. Focused UAT selection plus fixture regression: `126 passed, 0 failed` after rerun with network permission. Auth/security/governance/learning selection: `104 passed, 0 failed`. Course authoring included in focused selection: PASS. Ruff: PASS. Mypy combined script/module invocation was not clean because the same script was discovered under duplicate module names; no production typing change was made.

## 20. Security

Missing signed actor context remains HTTP 401 in the existing boundary probe. Auth bypass introduced: NO. Legacy auth fallback: NO. Secrets/private keys introduced into evidence: NO. Manual DB insert: NO. Secret scan: no matches. Actor signing was used only by a temporary local smoke helper and not persisted in artifacts.

## 21. Defects Found

| ID | Capability | Type | Severity | Blocks Verification | Status |
|---|---|---|---|---:|---|
| H02-D01 | Fixture bootstrap | FIXTURE_DEFECT | medium | YES before fix | FIXED |
| H02-B01 | Capability create | BLOCKED_BY_DATA | medium | YES | OPEN: semantic policy not configured |
| H02-B02 | Storage abstraction | BLOCKED_BY_STORAGE | medium | YES | OPEN: application bucket missing |

No `CONTRACT_DEFECT` or `IMPLEMENTATION_DEFECT` was established.

## 22. Capability Readiness — Before vs After

| Capability | Before | After | Evidence |
|---|---|---|---|
| Health/Auth | VERIFIED | VERIFIED | live health and signed auth boundary |
| Deterministic Course Authoring | VERIFIED | VERIFIED | regression baseline |
| CV Document | NOT_YET_VERIFIED | BLOCKED_BY_STORAGE | application bucket missing |
| CV Extraction | NOT_YET_VERIFIED | BLOCKED_BY_MODEL | worker/model unavailable |
| Candidate Profile | NOT_YET_VERIFIED | VERIFIED | accepted synthetic profile read |
| JD Document | NOT_YET_VERIFIED | BLOCKED_BY_STORAGE | application bucket missing |
| JD Extraction | NOT_YET_VERIFIED | BLOCKED_BY_MODEL | worker/model unavailable |
| Role Profile | NOT_YET_VERIFIED | VERIFIED | draft and active reads |
| Capability Analysis | NOT_YET_VERIFIED | BLOCKED_BY_DATA | persisted read pass; fresh create needs semantic policy |
| Learning Need | NOT_YET_VERIFIED | VERIFIED | synthetic gap projection HTTP 200 |
| Conversational Brief | NOT_YET_VERIFIED | BLOCKED_BY_MODEL | no model provider |
| Curriculum Planning | NOT_YET_VERIFIED | BLOCKED_BY_MODEL | no model-backed generation |
| Internal Recommendation | NOT_YET_VERIFIED | BLOCKED_BY_DATA | no catalog fixture |
| External Recommendation | NOT_YET_VERIFIED | BLOCKED_BY_EXTERNAL_DEPENDENCY | no provider |
| Learning Path | NOT_YET_VERIFIED | VERIFIED | historical synthetic read HTTP 200 |
| Content Generation | NOT_YET_VERIFIED | BLOCKED_BY_MODEL | no model provider |

## 23. Live VERIFIED Capabilities

Health/Auth, accepted Candidate Profile read, Role/Profile read lifecycle, persisted Capability Analysis read projection, Learning Need projection, and historical Learning Path read projection.

## 24. Remaining Blockers

### Model

`MODEL_NAME=replace-with-approved-model`; no model-backed execution.

### Worker

Workers remain stopped; extraction execution is model-dependent.

### Data

Semantic policy is not configured for fresh Capability Analysis. Recommendation catalog data is absent.

### Storage

`pai-documents` bucket is missing for the application blob abstraction.

### Contract

None established.

### Implementation

None established.

## 25. Frappe Integration Readiness

| Capability | Automated tests clean? | Live data-backed? | Contract stable? | Dependency available? | Safe to integrate? | Reason |
|---|---:|---:|---:|---:|---:|---|
| Candidate Profile read | Yes | Yes | Yes | Yes | YES | bounded synthetic read verified |
| Role Profile read | Yes | Yes | Yes | Yes | YES | draft/active reads verified |
| Learning Need read | Yes | Yes | Yes | Yes | YES | source refs preserved |
| Capability Analysis create | Yes | No | Yes | No | NO | semantic policy missing |
| CV/JD extraction | Yes | No | Yes | No | NO | model/worker unavailable |
| Storage upload/read/delete | Yes | No | Yes | No | NO | application bucket missing |

No integration recommendation is made solely from automated tests.

## 26. Evidence Artifacts

Created under `test/results/pai-ai-api-harden-02/`: bootstrap failure, contract, fix verification, storage, CV/candidate, JD/role, capability analysis, learning need, governance, regression, readiness, blockers and summary JSON artifacts. Human-readable report: `docs/research/PAI-AI-API-HARDEN-02.md`.

## 27. Git Diff Classification

| File | Type | Reason |
|---|---|---|
| `scripts/bootstrap_e2e_fixtures.py` | FIXTURE | UUID-to-text serialization at fixture boundary |
| `tests/test_e2e_fixture_bootstrap.py` | TEST | regression protection |
| `tests/test_capability_gap_integration_api.py` | TEST | HARDEN-01 signed auth fixture alignment |
| `tests/test_content_generation_api.py` | TEST | HARDEN-01 schema fixture alignment |
| `test/results/pai-ai-api-harden-02/*` | EVIDENCE | sanitized verification artifacts |
| `docs/research/PAI-AI-API-HARDEN-02.md` | DOC | bounded milestone report |

Production code: none. Migration: none. LMS: none.

## 28. Final Decision

Did `bootstrap_e2e_fixtures.py` pass? YES.

Was `document_id` issue fixture-side? YES.

Is application storage now VERIFIED? NO; `BLOCKED_BY_STORAGE` because the bucket is absent.

Is CV/Candidate data-backed flow VERIFIED? YES for the prebuilt accepted profile/read path; extraction execution remains `BLOCKED_BY_MODEL`.

Is JD/Role data-backed flow VERIFIED? YES for prebuilt profile/review/draft/active reads; extraction execution remains `BLOCKED_BY_MODEL`.

Is Capability Analysis live VERIFIED? NO for fresh create; persisted read projection is verified, but fresh create is `BLOCKED_BY_DATA`.

Is Learning Need live VERIFIED? YES for the non-model projection path.

Capabilities blocked only by model provider: CV extraction, JD extraction, Conversational Brief, Curriculum generation and Content Generation.

Genuine product defects remaining: none established.

## 29. Next Eligible Work

Capability: application storage boundary. Ready: NO. Reason: provision `pai-documents` through the supported development Compose/bootstrap path, then rerun put/read/delete.

Capability: Capability Analysis create. Ready: NO. Reason: configure the existing semantic policy fixture through its supported path, then rerun fresh signed create/reload.

Capability: CV/JD extraction. Ready: NO. Reason: approved model/worker dependency remains unavailable.

Do not implement these in H02.

## 30. Git Status

Core-AI canonical source: no `.git` metadata is present, so branch/HEAD/status cannot be reported from that source. The recovery clone remains uncommitted with prior HARDEN-01 test/docs/evidence changes. No commit performed. No push performed.

LMS: UNCHANGED.

STOP. No model provider configured, no Frappe feature work started.
