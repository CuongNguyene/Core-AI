# PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-01 Implementation Plan

> **For agentic workers:** execute this plan task-by-task with test-first changes. Do not commit or push.

**Goal:** Implement a frozen-spec, restricted-data structured extractor and measure its first complete baseline against the immutable synthetic EVAL-00 corpus.

**Architecture:** Keep all new behavior evaluation-only under `app/job_semantics_eval/` and `evals/job_semantics/requirement_breakdown_01/`. Reuse ModelGateway structured inference and PrivacyGateway, the exact EVAL-00 HTML text-view contract, and deterministic source-span matching; do not add production routes, persistence, capability mapping, or model routing.

**Tech Stack:** Python 3.13, Pydantic v2, existing FastAPI backend ModelGateway/PrivacyGateway, pytest, Ruff, mypy.

**Spec:** User-provided milestone `PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-01`; frozen predecessor contract under `backend/evals/job_semantics/requirement_breakdown_eval_00/`.

## Global Constraints

- Verify frozen EVAL-00 exact hashes before implementation and never mutate its artifacts.
- Provider receives only deterministic source blocks from the two JD HTML fields; no URL, source application reference, labels, or eval metadata.
- Provider output is strict, source-backed, remains `UNVALIDATED`, and never contains canonical capability identity/level or confidence.
- Freeze provider/model operation, privacy tier, prompts, output schema, source adapter, and input projection before any EVAL-00 provider call.
- Run one complete first baseline only after freeze; no partial-run prompt tuning.
- No production routing/API/database/migration/LMS/ATS/HRM changes; no commit/push.

## Review Focus

- Omitted/null/empty/whitespace source states must yield zero fabricated blocks/statements; pin cases 001–006 and conformance states.
- HTML inline formatting/entity decoding/list boundaries must match the frozen text view exactly; pin normalization/source order.
- Provider cannot invent or misattribute a span; pin unknown block, non-contiguous span, duplicate span, and cross-field rejection.
- A technically malformed result/provider error must not become `OTHER` or `UNCLEAR`; preserve distinct execution/error states.
- Evaluation matching must handle duplicates/order deterministically and keep decomposition, classification, and fidelity metrics separate.

## Planned Files and Interfaces

- `backend/app/job_semantics_eval/contracts.py`: strict extraction output, source-block, validated-prediction, execution-result contracts.
- `backend/app/job_semantics_eval/source_adapter.py`: deterministic `JobSourceBlock` conversion from nullable `target_job_source` using frozen text-view semantics.
- `backend/app/job_semantics_eval/extractor.py`: frozen prompt/schema definition, bounded `ModelGateway.infer_structured` + `PrivacyGateway` call, strict validation and server-authored provenance.
- `backend/app/job_semantics_eval/validation.py`: output schema and source-block/span validation.
- `backend/evals/job_semantics/requirement_breakdown_01/`: immutable extractor spec/freeze manifest, one-shot runner, deterministic matching/metrics, append-only results.
- `backend/tests/test_job_requirement_breakdown_01*.py`: focused contract, adapter, leakage, validation, matching, metrics, freeze and manifest tests.
- `backend/docs/research/PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-01.md`: exact baseline and scope report.

## Tasks

Follow this exact release order supplied by the user:

1. Verify EVAL-00 freeze.
2. Audit ModelGateway + PrivacyGateway.
3. Implement source adapter.
4. Implement strict output/provenance validation.
5. Implement deterministic matcher + metrics.
6. Freeze extractor spec, provider input schema, output schema, source adapter, matching spec, metrics spec, and runner spec.
7. Reverify EVAL-00.
8. Make the first provider call.
9. Run all 40 cases with the same frozen spec.
10. Compute metrics.
11. Perform error analysis only after all cases complete.
12. Report `BASELINE_MEASURED_NO_PRODUCTION_DECISION`.

### Tasks 1–2. Baseline and gateway/privacy audit

- Verify exact manifest and corpus identity and predecessor tests.
- Record current HEAD/worktree, ModelGateway structured-output/schema-registry/routing behavior, PrivacyGateway behavior, retry/error conventions, and external restricted-data gating.
- Do not proceed if frozen identity changes.

### 3. Deterministic source adapter (TDD)

- Add tests first for DOM text view, HTML entity decode once, inline transparency, block/list order, whitespace, null/omitted/empty/whitespace and deterministic IDs.
- Implement only the exact EVAL-00 text-view rules. No semantic segmentation.

### 4. Strict structured output and provenance validation (TDD)

- Add tests first for exact enums/strict extra-forbid schema, forbidden fields, known block IDs, source-field fidelity, and exact contiguous source spans.
- Implement server validation without repairing hallucinated spans.

### 5. Deterministic matcher and metrics (TDD)

- Add tests for frozen normalization rules and stable duplicate/source-order matching.
- Define decomposition/type/relevance/fidelity metrics and subgroup denominator handling.

### 6. Frozen provider specification and ModelGateway adapter (TDD)

- Add mocked tests for exact privacy class/purpose, prompt boundary/injection treatment, provider projection leakage, typed output and safe errors.
- Freeze complete spec/hash manifest before any live call; provider operation must reuse `infer_structured` with strict Pydantic schema and `PrivacyGateway`.

### 7. Freeze and reverify before first inference

- Freeze all seven requested spec/schema/adapter/matching/metrics/runner artifacts and hashes; verify source EVAL-00 identity again.
- No smoke or partial provider execution before this gate.

### 8–12. First full baseline and report

- Verify spec and dataset one last time, then make call #1 and execute the full 40 cases with the same frozen spec. Bounded technical retries only; append-only artifacts and model-drift checks.
- Compute metrics after complete execution; only then inspect individual errors/cases.
- If config/privacy policy does not permit provider use, do not call; report the precise blocker rather than fabricating a baseline.
- Run focused tests, Ruff, format, scoped mypy, diff check; write final report and confirm no production mapping/API/DB changes.

## Execution Note

The user explicitly supplied the execution profile and end-to-end milestone specification. This plan does not authorize semantic edits after seeing baseline output; any semantic refinement requires a new extractor version and future held-out corpus.
