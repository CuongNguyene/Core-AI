# Evidence Graph CV Extraction Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor hybrid CV extraction into an evidence graph that preserves entity context, usage and source-backed confidence for JD-CV matching.

**Architecture:** Full-document extraction supplies cross-section relations and context; section extraction supplies grounded evidence. Both feed graph nodes/edges and then a typed `CandidateProfile`. Existing flattened extraction output remains a compatibility adapter until graph persistence and matching consumers migrate.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing ModelGateway/PrivacyGateway.

## Global Constraints

- Preserve full-document and section extraction as separate evidence sources.
- CV/JD content remains untrusted data; document instructions never become system/tool instructions.
- Every supported evidence item requires an exact source excerpt; unresolved evidence fails closed.
- Keep `SourceLocator`, audit redaction and existing extraction API compatibility during migration.
- Do not mark a technology as verified competency; graph evidence is observational only.
- Do not add raw prompt or raw document content to audit metadata.

---

### Task 1: Add evidence graph primitives ✅

**Files:**
- Create: `backend/app/extraction/evidence.py`
- Create: `backend/tests/test_evidence_graph.py`

**Interfaces:**
- `EvidenceContext` enum with mentioned/studied/project/research/production/system/team contexts.
- `EvidenceItem` with context, usage, source excerpt, confidence and source type.
- Evidence items remain source-backed and do not assert verified competency.

### Task 2: Add CandidateProfile entities ✅

**Files:**
- Create: `backend/app/extraction/profile.py`
- Create: `backend/tests/test_candidate_profile.py`

**Interfaces:**
- `CandidateProfile` fields: employment history, projects, research work, education, publications and skills.
- Entity models retain evidence lists and stable entity identifiers.

### Task 3: Add relation extraction contracts ✅

**Files:**
- Modify: `backend/app/extraction/schemas.py`
- Modify: `backend/app/extraction/prompts.py`
- Create: `backend/tests/test_relation_extraction_contracts.py`

**Interfaces:**
- Full-document relation extraction returns entity/context/usage candidates.
- Section extraction returns grounded evidence candidates scoped to one section.

### Task 4: Build graph merge and normalization ✅

**Files:**
- Create: `backend/app/extraction/graph_merge.py`
- Modify: `backend/app/extraction/normalization.py`
- Create: `backend/tests/test_graph_merge.py`

**Interfaces:**
- Merge full-context relations and section evidence by canonical entity identity.
- Preserve every distinct evidence context and exact source reference.
- Reject unsupported/inexact evidence instead of manufacturing edges.

### Task 5: Integrate worker/profile output ✅ (compatibility adapter)

**Files:**
- Modify: `backend/app/extraction/worker.py`
- Modify: `backend/app/extraction/repository.py`
- Modify: `backend/app/extraction/api.py`
- Create/update migrations only if persistence requires graph columns/tables.
- Create: `backend/tests/test_evidence_graph_worker.py`

**Interfaces:**
- Small documents use full extraction plus grounding.
- Large documents use structure/section extraction plus relation context.
- Extraction profile exposes `CandidateProfile` without removing compatibility reads.

### Task 6: Update matching and golden harness ✅ (graph-aware matching fallback)

**Files:**
- Modify: `backend/app/matching/`
- Create: `backend/tests/golden/evidence_graph_cv.json`
- Create: `backend/tests/test_evidence_graph_matching.py`
- Update: backend documentation and ADR/spec.

**Acceptance:**
- PyTorch mention, research usage and production usage remain distinguishable.
- Evidence is source-backed and confidence-preserving.
- Existing extraction tests remain green.
