# P1.5 Capability Assessment Correctness & Explainability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PREVIEW capability assessments requirement-aware, claim-isolated, and deterministically explainable without changing P2 governance.

**Architecture:** Preserve `EvidenceSemantics` as the source-of-truth observation contract. Extend the semantic projection with fixed decision details, apply compatibility by authored requirement expectation, and keep domain-pack canonicalization at claim level. Additive Pydantic fields preserve historical portfolio reads.

**Tech Stack:** Python 3.13, Pydantic, pytest, SQLAlchemy JSON persistence, Ruff, scoped mypy.

## Global Constraints

- Do not add aliases, ontology rules, LLM inference, threshold lowering, extraction changes, or P2 governance changes.
- Education/credential support is separate from verification status and never becomes VERIFIED.
- Shared source locators do not merge sibling claims; aliases still require explicit domain packs.
- Missing evidence is not capability absence; PREVIEW remains provisional and no OFFICIAL analysis is added.

---

### Task 1: Freeze structured reason and decision contracts

**Files:**
- Modify: `backend/app/capability_analysis/semantic_core/retrieval.py`
- Modify: `backend/app/capability_analysis/schemas.py`
- Test: `backend/tests/test_p1_5_explainability.py`

- [ ] Write RED tests asserting fixed reason codes, coverage fields, confidence fields, and a reason for every non-supported status.
- [ ] Run `pytest backend/tests/test_p1_5_explainability.py -q` and verify it fails because the fields/contracts are absent.
- [ ] Add minimal frozen/internal decision details and additive `RequirementAssessment`/`TargetGap` fields with defaults.
- [ ] Re-run the focused tests and existing schema tests.

### Task 2: Preserve requirement-aware directness and verification separation

**Files:**
- Modify: `backend/app/capability_analysis/semantic_core/compatibility.py`
- Modify: `backend/app/capability_analysis/semantic_core/retrieval.py`
- Test: `backend/tests/test_p1_5_compatibility.py`

- [ ] Add RED tests for education/credential direct support, education-not-work, and credential-not-practice.
- [ ] Run the tests and confirm current mention/verification projection fails the assertions.
- [ ] Implement only generic expectation/source-kind compatibility and a separate verification-needed detail.
- [ ] Run compatibility and existing semantic-core tests.

### Task 3: Isolate claim-level mapping from shared excerpts

**Files:**
- Modify: `backend/app/capability_analysis/rules.py`
- Test: `backend/tests/test_p1_5_claim_isolation.py`

- [ ] Add RED fixtures with shared locators for Python/PyTorch/TensorFlow/SQL, Azure/Docker/Git/Slurm, Excel/Bloomberg/Power BI, plus Apache Kafka/Spark aliases.
- [ ] Run the tests and confirm sibling counts are inflated before the fix.
- [ ] Map packs using observation-owned claim fields while retaining explicit alias behavior.
- [ ] Verify retrieval and eligibility counts reflect only independently matching observations.

### Task 4: Wire assessment projection and Python regression

**Files:**
- Modify: `backend/app/capability_analysis/rules.py`
- Modify: `backend/app/capability_analysis/repository.py` only if additive fields need explicit compatibility handling
- Test: `backend/tests/test_p1_5_live_regressions.py`

- [ ] Add RED tests for degree, TensorFlow, Docker, Python, production deployment, and MLOps negative control.
- [ ] Run focused tests and record the exact failing decision basis.
- [ ] Project structured reasons/coverage/confidence into assessments and gaps without inventing target signals.
- [ ] Verify production remains context mismatch and MLOps remains not found/insufficient.

### Task 5: Regression verification and report

**Files:**
- No production files beyond tasks above.

- [ ] Run focused P1.5, capability-analysis, and P2 governance suites.
- [ ] Run full backend pytest, Ruff, scoped mypy, and `git diff --check`.
- [ ] Confirm historical portfolio reads and PREVIEW/semantic-policy invariants.
- [ ] Report root causes, before/after results, tests, and intentional follow-ups.

### Task 6: Closing correctness checks

- [x] Add generic `AND`/`OR` semantics to requirement and JD extraction contracts.
- [x] Verify a Data Science education claim satisfies one alternative in an education OR
      group without manufacturing a missing ML capability requirement.
- [x] Version confidence defaults and persist threshold provenance in decision details;
      do not mutate accepted historical profiles.
- [x] Distinguish a plain capability requirement from an explicitly authored
      `demonstrated_usage` requirement; do not invent usage constraints.
- [x] Run the full backend suite and static checks.

The closing scope is intentionally limited to deterministic contract and assessment
correctness. Cross-requirement authoring/UI for composing larger logical groups remains
an authoring concern; the runtime must consume explicit operators and must not infer them.
