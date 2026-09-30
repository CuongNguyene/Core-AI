# Hybrid Document Extraction Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select full-document extraction for documents at or below 12,000 characters and section-based extraction for larger documents.

**Architecture:** Add a pure extraction router with no provider or persistence dependencies. The router returns an explicit `ExtractionMode`; later worker orchestration can use this decision to select full-document or section-aware extraction while retaining existing privacy and evidence boundaries.

**Tech Stack:** Python 3.13, `enum.Enum`, pytest.

## Global Constraints

- Document content remains untrusted data.
- This change must not alter provider routing, prompt handling, evidence validation, or persistence.
- Boundary behavior is inclusive: exactly 12,000 characters uses full-document mode.

---

### Task 1: Add the extraction mode router

**Files:**
- Create: `backend/app/extraction/router.py`
- Create: `backend/tests/test_extraction_router.py`

**Interfaces:**
- Produces `ExtractionMode.FULL_DOCUMENT`, `ExtractionMode.SECTION_BASED`, and `choose_extraction_mode(text: str, threshold: int = 12000) -> ExtractionMode`.

- [x] **Step 1: Write failing boundary tests**

```python
def test_documents_at_or_below_threshold_use_full_document_mode():
    assert choose_extraction_mode("x" * 12_000) is ExtractionMode.FULL_DOCUMENT


def test_documents_above_threshold_use_section_based_mode():
    assert choose_extraction_mode("x" * 12_001) is ExtractionMode.SECTION_BASED


def test_custom_threshold_is_respected():
    assert choose_extraction_mode("x" * 101, threshold=100) is ExtractionMode.SECTION_BASED
```

- [x] **Step 2: Run the router tests and verify they fail because the module is absent**

Run: `UV_CACHE_DIR=/tmp/pai-uv-cache uv run pytest -q backend/tests/test_extraction_router.py`

- [x] **Step 3: Implement the minimal pure router**

```python
from enum import Enum


class ExtractionMode(Enum):
    FULL_DOCUMENT = "full_document"
    SECTION_BASED = "section_based"


def choose_extraction_mode(text: str, threshold: int = 12_000) -> ExtractionMode:
    if len(text) <= threshold:
        return ExtractionMode.FULL_DOCUMENT
    return ExtractionMode.SECTION_BASED
```

- [x] **Step 4: Run focused and full verification**

Run: `UV_CACHE_DIR=/tmp/pai-uv-cache uv run pytest -q backend/tests/test_extraction_router.py`

Run: `UV_CACHE_DIR=/tmp/pai-uv-cache uv run ruff check backend/app/extraction/router.py backend/tests/test_extraction_router.py`

- [ ] **Step 5: Commit**

### Task 2: Add deterministic document structure extraction

**Files:**
- Create: `backend/app/extraction/structure.py`
- Modify: `backend/app/extraction/schemas.py`
- Create: `backend/tests/test_extraction_structure.py`
- Modify: `backend/be_document.md`

**Interfaces:**
- Produces `SectionType`, `DocumentSection`, `DocumentStructureOutput` and `detect_document_structure(text: str, document_type: str = "unknown") -> DocumentStructureOutput`.
- Section boundaries are line-based, ordered, non-overlapping offsets into normalized text.

- [x] **Step 1: Write failing schema and detector tests**
- [x] **Step 2: Run focused tests and verify the missing module/schema failure**
- [x] **Step 3: Implement strict section schemas and heading detector**
- [x] **Step 4: Run focused and full verification**
- [ ] **Step 5: Commit**

### Task 3: Add section-aware chunking

**Files:**
- Modify: `backend/app/extraction/chunking.py`
- Modify: `backend/tests/test_extraction_chunking.py`
- Modify: `backend/be_document.md`

**Interfaces:**
- Produces `ExtractionChunk` with `ordinal`, `section_type`, `text`, `start_offset`, and `end_offset`.
- Adds `split_sections(content: str, sections: Sequence[DocumentSection], max_chars: int = 2000, overlap_chars: int = 150) -> list[ExtractionChunk]`.
- Keeps `split_document` as a compatibility path for full-document mode; those chunks carry `SectionType.UNKNOWN`.

- [x] **Step 1: Write failing section-boundary and overlap tests**
- [x] **Step 2: Run focused tests and verify the new API/model failure**
- [x] **Step 3: Implement section-aware chunking with bounded offsets**
- [x] **Step 4: Run focused and full verification**
- [ ] **Step 5: Commit**

## Scope gap

Full-document prompt contracts, worker branching, section extraction orchestration, and section-aware merge require their own concrete schemas and acceptance tests before implementation.

### Task 6: Add section extraction contracts

**Files:**
- Modify: `backend/app/extraction/schemas.py`
- Modify: `backend/app/extraction/prompts.py`
- Create: `backend/tests/test_section_extraction_contracts.py`
- Modify: `backend/be_document.md`

**Interfaces:**
- Produces `CVSectionExtractionOutput` and `JDSectionExtractionOutput`.
- Registers `cv_section_extraction` and `jd_section_extraction` with versioned prompt/schema contracts.
- Section payloads contain `section_type` and `section_text`; prompts forbid using context outside the current section.

- [x] **Step 1: Write failing section contract tests**
- [x] **Step 2: Run focused tests and verify missing section contracts**
- [x] **Step 3: Implement schemas and prompt registrations**
- [x] **Step 4: Run focused verification**

### Task 7: Refactor merge evidence allocation

**Files:**
- Modify: `backend/app/extraction/schemas.py`
- Modify: `backend/app/extraction/merge.py`
- Modify: `backend/tests/test_extraction_merge.py`

**Interfaces:**
- Dedupe supported claims by normalized value plus evidence type.
- Preserve distinct evidence types in one claim's `evidence` list.
- For duplicate value/type claims, retain the higher-confidence evidence and its locator.

- [x] **Step 1: Write failing multi-evidence and stronger-evidence tests**
- [x] **Step 2: Run focused tests and verify current merge behavior fails**
- [x] **Step 3: Implement evidence aggregation and stronger-evidence retention**
- [x] **Step 4: Run full verification**

### Task 10: Add hybrid extraction acceptance tests

**Files:**
- Create: `backend/tests/extraction/test_hybrid_pipeline.py`
- Create: `backend/tests/extraction/test_validation_boundaries.py`
- Modify: `backend/be_document.md`

**Interfaces:**
- Verifies router, structure detector, section chunking, evidence validation and audit redaction behavior without sending real documents to a provider.

- [x] **Step 1: Write failing acceptance tests**
- [x] **Step 2: Run focused tests and verify failures identify missing behavior**
- [x] **Step 3: Implement only required compatibility fixes**
- [x] **Step 4: Run full verification**

### Task 8: Add entity normalization without changing evidence

**Files:**
- Create: `backend/app/extraction/normalization.py`
- Modify: `backend/app/extraction/merge.py`
- Create: `backend/tests/test_extraction_normalization.py`
- Modify: `backend/tests/test_extraction_merge.py`
- Modify: `backend/be_document.md`

**Interfaces:**
- Produces `canonicalize_entity(value: str) -> str` and `normalization_key(value: str) -> str`.
- Canonicalization affects only dedupe/matching keys; original claim values, excerpts, locators and audit metadata remain unchanged.
- Existing exact excerpt lookup, `SourceLocator`, fail-closed errors and audit metadata remain mandatory.

- [x] **Step 1: Write failing alias and evidence-preservation tests**
- [x] **Step 2: Run focused tests and verify missing normalization behavior**
- [x] **Step 3: Implement canonicalization and integrate only the merge key**
- [x] **Step 4: Run full verification**

### Task 4: Extend evidence claim schemas

**Files:**
- Modify: `backend/app/extraction/schemas.py`
- Create: `backend/tests/test_full_extraction_contracts.py`

**Interfaces:**
- Produces `EvidenceType`, `EvidenceClaim`, `CVFullExtractionOutput`, and `JDFullExtractionOutput`.
- Full claims require an evidence type and source excerpt when supported; insufficient/unknown claims cannot carry invented values or excerpts.

- [x] **Step 1: Write failing evidence schema tests**
- [x] **Step 2: Run focused tests and verify the missing types failure**
- [x] **Step 3: Implement strict evidence and full output schemas**
- [x] **Step 4: Run focused verification**

### Task 5: Register full-document prompt contracts

**Files:**
- Modify: `backend/app/extraction/prompts.py`
- Modify: `backend/tests/test_full_extraction_contracts.py`
- Modify: `backend/be_document.md`

**Interfaces:**
- Registers `cv_full_extraction` and `jd_full_extraction` with a versioned full-document schema contract.
- Full prompt payload remains bounded by the existing untrusted-document boundary and returns the matching full output schema.

- [x] **Step 1: Write failing registry tests**
- [x] **Step 2: Run focused tests and verify missing full contract IDs**
- [x] **Step 3: Register full prompts and schemas**
- [x] **Step 4: Run full verification**
