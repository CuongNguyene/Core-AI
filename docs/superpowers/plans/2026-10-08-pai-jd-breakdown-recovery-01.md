# PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-01-RECOVERY-01 Implementation Plan

> **For agentic workers:** Execute natively in the existing isolated JD worktree. Apply test-first changes; preserve the recorded failed-run artifacts byte-for-byte.

**Goal:** Preserve the failed Luna run, add sanitized transport diagnostics, make all-error reporting complete, verify with offline tests, then run one approved non-EVAL connectivity canary and only on success create a fresh baseline run identity.

**Architecture:** Keep the existing OpenAI Responses adapter and ModelGateway boundary. Attach safe transport-cause metadata to gateway exceptions, serialize only allowlisted diagnostic fields in runner artifacts, and make report quality nullable when no prediction succeeded. A separate one-shot canary uses a synthetic non-EVAL payload; it must not read EVAL-00.

**Tech Stack:** Python, OpenAI Python SDK, httpx, Pydantic, pytest, existing ModelGateway/PrivacyGateway and Luna eval runner.

**Spec:** User-provided `PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-01-RECOVERY-01` scope in the active conversation.

## Global Constraints

- Failed run `20261008T095324Z-luna-2ba7a268` is immutable; preserve its two recorded SHA-256 identities.
- Do not change EVAL-00, the frozen Luna semantic spec, prompts, schema, or matching/metric definitions.
- Do not make another EVAL-00 provider request under the old run ID.
- Persist exception class/cause class/transport phase only; never exception repr, key, auth header, or request body.
- Run no more than one synthetic non-EVAL canary request after offline checks pass.
- Create a new baseline run ID only if the canary returns a parsed strict structured result; do not execute the 40-posting baseline in this recovery task.
- No commit or push.

## Review Focus

- Nested SDK/httpx errors may expose secrets in messages: serialize class names only.
- DNS and TLS errors may be wrapped several levels deep: traverse causes/contexts with cycle protection.
- `APIConnectionError` may have no cause: retain its top-level class and `unknown` phase.
- An all-error report has operational evidence but no measurable quality: quality metrics must be `null`, not fabricated zero scores.
- The canary must use synthetic data and a fresh one-call cap, never EVAL-00 inputs.

---

### Task 1: Pin failed-run immutability

**Files:**
- Modify: `evals/job_semantics/requirement_breakdown_01/openai-gpt-6-luna-v1/` only by adding a separate recovery manifest outside the failed run directory.
- Test: `tests/test_job_requirement_breakdown_openai_luna_runner.py`

**Interfaces:**
- Consumes: the existing failed run artifact paths and SHA-256 values.
- Produces: a recovery record with failed run ID, result/manifest hashes, 40-case terminal count, and frozen status.

- [ ] Add a test proving the recovery manifest points to the existing failed run hashes and does not rewrite either file.
- [ ] Run the test and verify it fails before implementation.
- [ ] Implement the separate recovery manifest generation/verification.
- [ ] Re-run the test and compare the failed-run file hashes before and after.

### Task 2: Add sanitized OpenAI transport diagnostics

**Files:**
- Modify: `app/model_gateway/errors.py`
- Modify: `app/model_gateway/openai_responses.py`
- Modify: `app/job_semantics_eval/runner_openai_luna.py`
- Test: `tests/test_openai_responses_provider.py`
- Test: `tests/test_job_requirement_breakdown_openai_luna_runner.py`

**Interfaces:**
- Consumes: OpenAI `APITimeoutError` / `APIConnectionError` and nested httpx/socket/SSL causes.
- Produces: allowlisted diagnostic `{error_class, transport_error_class, transport_phase, attempt, cause_chain}` with class names only.

- [ ] Add failing tests for Connect/Read/Write/Pool timeout, DNS, TLS, connection reset, wrapped and absent causes.
- [ ] Verify the tests fail because diagnostic metadata is absent.
- [ ] Implement cycle-safe cause traversal and deterministic phase classification without persisting exception text.
- [ ] Preserve retry behavior and requested model/schema/input exactly.
- [ ] Verify new tests pass and existing retry tests remain green.

### Task 3: Make all-error reporting complete

**Files:**
- Modify: `app/job_semantics_eval/runner_openai_luna.py`
- Test: `tests/test_job_requirement_breakdown_openai_luna_runner.py`

**Interfaces:**
- Consumes: complete per-case result JSONL including provider-error metadata.
- Produces: `report_status=complete`, `quality_status=NOT_MEASURABLE`, `metrics=null`, and available operational/provider-error/error-analysis summaries.

- [ ] Add a 40-error fixture test asserting report recomputation completes offline and reports null quality metrics.
- [ ] Run it and verify it reproduces the current aggregation failure.
- [ ] Implement guarded quality-metric computation and complete operational/error breakdowns.
- [ ] Verify report recomputation constructs no gateway and makes zero calls.

### Task 4: Add offline recovery regression coverage

**Files:**
- Modify: `tests/test_openai_responses_provider.py`
- Modify: `tests/test_job_requirement_breakdown_openai_luna_runner.py`

**Interfaces:**
- Consumes: sanitized diagnostics, report status, and failed-run integrity record.
- Produces: offline regressions for all transport causes, secret exclusion, 0-success reporting, immutable failed artifacts, and no provider construction during recompute.

- [ ] Add assertions that error messages/URLs/secret-like fixture text never enter serialized diagnostics.
- [ ] Add an end-to-end offline report fixture with all 40 provider failures.
- [ ] Verify all new tests fail before corresponding implementation and pass afterward.
- [ ] Run focused tests, Ruff, format, scoped mypy, and `git diff --check` before any canary.

### Task 5: One non-EVAL connectivity canary and fresh run identity

**Files:**
- Create or modify: `app/job_semantics_eval/openai_luna_canary.py` (only if needed for a bounded reusable canary entry point).
- Create: a separate canary artifact under `evals/job_semantics/requirement_breakdown_01/openai-gpt-6-luna-v1/canaries/`.
- Create: a new baseline run directory/manifest only after canary success.

**Interfaces:**
- Consumes: one fixed synthetic technical prompt, exact model `gpt-6-luna`, PrivacyGateway approval, and strict Pydantic schema.
- Produces: sanitized canary status with response ID/model/parsed result hash; on success only, a new baseline run ID and fresh cap metadata.

- [ ] Verify all offline tests and freeze identity before the canary.
- [ ] Execute exactly one provider request, with no EVAL-00 or JD corpus text.
- [ ] On failure, persist sanitized failure diagnostics and stop without creating a runnable baseline ID.
- [ ] On success, create a unique new run ID and fresh call-cap manifest; do not start the 40-case run in Recovery-01.
- [ ] Verify the old failed run hashes are unchanged and no second canary occurred.
