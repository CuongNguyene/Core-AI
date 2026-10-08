# JD Luna Baseline Implementation Plan

> **For agentic workers:** Execute this plan natively in the isolated JD worktree; do not commit or push.

**Goal:** Run the frozen 40-posting EVAL-00 baseline through the approved OpenAI GPT-6 Luna Responses Structured Outputs adapter and report measured metrics without production claims.

**Architecture:** Preserve EVAL-00 bytes and its historical freeze provenance. Add a versioned OpenAI-specific experiment freeze and wire the eval runner to the existing isolated OpenAI gateway. Verify all component hashes and call cap before making any provider request; recreate only the identified backend service after inspecting its compose definition and effective configuration.

**Tech Stack:** Python, Pydantic v2, existing ModelGateway/PrivacyGateway, OpenAI Responses API, pytest, Docker Compose if the matching local BE service is found.

**Spec:** User-provided `PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-01` milestone in this conversation.

## Global Constraints

- EVAL-00 dataset, manifest, taxonomy, reviews, and conformance files remain unchanged.
- Provider is OpenAI Responses API, requested model exactly `gpt-6-luna`, strict Structured Outputs.
- PrivacyGateway must approve before transport; provider request excludes gold/eval metadata.
- Freeze runner, projection, prompts, schema, provenance, matcher, metrics, retry/model policy before call #1.
- One sequential full run; no result inspection or semantic tuning until all cases finish.
- No Gemini/Jev fallback, no production routing, API, DB, capability mapping, commit, or push.
- Do not print credentials; no transport call without an available OpenAI secret and passing freeze verifier.

## Review Focus

- Historical EVAL-00 `code_head` differs from current HEAD: preserve original identity while validating exact artifact hashes and counts.
- Existing EVAL-01 freeze and runner pin Gemini: create a distinct Luna freeze/run identity; never overwrite the historical Gemini run.
- Empty source cases must skip provider and count as completed empty results.
- Call cap must be nonempty cases × (1 + frozen retries); stop before any attempt beyond the cap.
- Recreated BE must use the intended service/compose file and must not expose secrets in logs.

---

### Task 1: Audit runtime and baseline prerequisites

**Files:** Read-only inspection of worktrees, EVAL-00, EVAL-01, backend settings, compose files, and approved adapter/tests.

- [ ] Record worktree/HEAD/dirty state and adapter source hashes.
- [ ] Verify EVAL-00 bytes/counts against its historical manifest without rewriting the historical code HEAD.
- [ ] Locate compose definition and BE service; inspect effective provider/model and secret-presence only.
- [ ] Confirm Luna key availability without displaying its value. Stop before external calls if absent.

### Task 2: Add a versioned Luna experiment freeze and runner path

**Files:** `services/pai-backend/backend/app/job_semantics_eval/runner.py`, focused tests, and new versioned EVAL-01 freeze/spec artifacts.

- [ ] Add tests proving runner selects `build_openai_luna_gateway`, exact Luna model, privacy gating, retry cap, and no fallback.
- [ ] Implement the minimal versioned runner path; retain Gemini v1 artifacts and old run unchanged.
- [ ] Freeze source adapter/projection, instructions/schema, provenance rules, matcher, metrics, runner, model/privacy/retry config, and source hashes with deterministic canonical hashes.
- [ ] Run the new freeze verifier and all offline focused regressions; verify provider call count remains zero.

### Task 3: Recreate the intended BE service

**Files:** Existing compose/config files only if required and explicitly in scope.

- [ ] Confirm the correct compose project/service and effective OpenAI configuration without exposing secrets.
- [ ] Recreate only that BE service; verify health and loaded provider/model.
- [ ] If key/config or compose target is missing/ambiguous, stop without container mutation or provider call.

### Task 4: Execute the immutable full baseline

**Files:** New unique run directory under `evals/job_semantics/requirement_breakdown_01/runs/` and the requested research report.

- [ ] Re-run EVAL-00 identity and the complete Luna freeze verifier immediately before transport.
- [ ] Enforce hard cap; execute all 40 cases sequentially using one exact spec, with same-spec technical retries only.
- [ ] Do not inspect semantic outputs until all cases have terminal records.
- [ ] Recompute metrics/error analysis offline; hash run artifacts and verify EVAL-00 remained unchanged.
- [ ] Run Ruff, format, scoped mypy, and `git diff --check`; report no commit/push.
