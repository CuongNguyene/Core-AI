# Legacy Role Profile Draft Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make legacy JD-derived RoleProfileDrafts reviewable without losing source semantics, duplicating findings, or claiming ACTIVE eligibility prematurely.

**Architecture:** Preserve detailed, per-requirement authoring findings in the draft JSON column and derive a compact quality-gate summary from them. The legacy adapter will classify conservatively, validate its source chain at draft construction, and expose duplicate candidates for reviewer action without merging requirements.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, pytest.

## Global Constraints

- Do not mutate accepted extraction profiles or rerun model extraction.
- `quality_gate.passed` means eligible for ACTIVE only.
- Only missing source-chain metadata is BLOCKING for legacy compatibility.
- Warnings may permit PROVISIONAL according to policy, but never ACTIVE.
- No capability analysis or learning-path generation in this work.

---

### Task 1: Findings and eligibility schemas

**Files:**
- Modify: `backend/app/role_profile_authoring/schemas.py`
- Modify: `backend/tests/test_role_profile_authoring_api.py`

**Interfaces:**
- Produces `QualityGateResult(summary_findings=...)`, `RequirementFinding`, `ApprovalEligibility`, and `DuplicateCandidateGroup`.

- [ ] **Step 1: Write failing API/schema tests**

```python
assert body["quality_gate"] == {"passed": False, "summary_findings": [...]}
assert "authoring_findings" not in body
assert detail_body["authoring_findings"][0]["requirement_id"] == "jd-skill-1-python"
assert body["approval_eligibility"] == {
    "can_create_draft": True,
    "can_approve_provisional": True,
    "can_approve_active": False,
}
```

- [ ] **Step 2: Run the API/schema tests and verify they fail**

Run: `uv run pytest tests/test_role_profile_authoring_api.py -q`

- [ ] **Step 3: Add the minimal response schemas and API response projection**

```python
class QualityGateResult(BaseModel):
    passed: bool
    summary_findings: list[SummaryFinding]

class RoleProfileDraftResponse(RoleProfileDraft):
    authoring_findings: list[RequirementFinding] | None = None
```

- [ ] **Step 4: Run the API/schema tests and verify they pass**

Run: `uv run pytest tests/test_role_profile_authoring_api.py -q`

### Task 2: Conservative legacy source adapter

**Files:**
- Modify: `backend/app/role_profile_authoring/source_adapter.py`
- Modify: `backend/tests/test_role_profile_source_adapter.py`

**Interfaces:**
- Produces legacy requirements with source locator/reference and per-requirement findings.
- Produces `DuplicateCandidateGroup` values without mutating requirements.

- [ ] **Step 1: Write failing legacy adapter tests**

```python
assert experience_requirement.criterion_dimension is CriterionDimension.EXPERIENCE
assert degree_requirement.criterion_dimension is CriterionDimension.EDUCATION
assert advantage_requirement.classification is RequirementClassification.PREFERRED
assert "legacy_uncertain_priority" in findings_for(required_skill.id)
assert adapted.duplicate_candidate_groups[0].reviewer_required is True
```

- [ ] **Step 2: Run the adapter tests and verify they fail**

Run: `uv run pytest tests/test_role_profile_source_adapter.py -q`

- [ ] **Step 3: Implement the minimal legacy mapping and duplicate detector**

```python
if _is_advantage(claim.value):
    classification = RequirementClassification.PREFERRED
elif prefix == "responsibility":
    classification = RequirementClassification.ROLE_CRITICAL
else:
    classification = RequirementClassification.UNCLASSIFIED
```

- [ ] **Step 4: Run the adapter tests and verify they pass**

Run: `uv run pytest tests/test_role_profile_source_adapter.py -q`

### Task 3: Source-chain gate and approval eligibility

**Files:**
- Modify: `backend/app/role_profile_authoring/quality_gate.py`
- Modify: `backend/app/role_profile_authoring/repository.py`
- Modify: `backend/tests/test_role_profile_authoring_quality_gate.py`
- Modify: `backend/tests/test_role_profile_authoring_repository.py`

**Interfaces:**
- Consumes draft-level source metadata, detailed findings, and requirements.
- Produces summary findings and `ApprovalEligibility`.

- [ ] **Step 1: Write failing gate/repository tests**

```python
assert "legacy_missing_provenance" not in summary_codes(draft)
assert draft.approval_eligibility.can_approve_provisional is True
assert draft.approval_eligibility.can_approve_active is False
assert blocked_draft.approval_eligibility.can_approve_provisional is False
```

- [ ] **Step 2: Run the gate/repository tests and verify they fail**

Run: `uv run pytest tests/test_role_profile_authoring_quality_gate.py tests/test_role_profile_authoring_repository.py -q`

- [ ] **Step 3: Implement source-chain validation and summary aggregation**

```python
summary = aggregate_requirement_findings(detail_findings)
source_blocking = missing_draft_source or any(missing_requirement_source(requirement))
eligibility = ApprovalEligibility(
    can_create_draft=True,
    can_approve_provisional=not source_blocking,
    can_approve_active=gate.passed,
)
```

- [ ] **Step 4: Run the gate/repository tests and verify they pass**

Run: `uv run pytest tests/test_role_profile_authoring_quality_gate.py tests/test_role_profile_authoring_repository.py -q`

### Task 4: Full regression verification

**Files:**
- Test: `backend/tests/test_role_profile_source_adapter.py`
- Test: `backend/tests/test_role_profile_authoring_repository.py`
- Test: `backend/tests/test_role_profile_authoring_api.py`

- [ ] **Step 1: Run the focused full suite**

Run: `uv run pytest tests/test_role_profile_source_adapter.py tests/test_role_profile_authoring_quality_gate.py tests/test_role_profile_authoring_repository.py tests/test_role_profile_authoring_api.py -q`

- [ ] **Step 2: Run static checks for changed modules**

Run: `uv run ruff check app/role_profile_authoring tests/test_role_profile_source_adapter.py tests/test_role_profile_authoring_quality_gate.py tests/test_role_profile_authoring_repository.py tests/test_role_profile_authoring_api.py`

Run: `uv run mypy app/role_profile_authoring tests/test_role_profile_source_adapter.py tests/test_role_profile_authoring_quality_gate.py tests/test_role_profile_authoring_repository.py tests/test_role_profile_authoring_api.py`
