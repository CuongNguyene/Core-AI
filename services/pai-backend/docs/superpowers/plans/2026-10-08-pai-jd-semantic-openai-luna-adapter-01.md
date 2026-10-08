# PAI-JD-SEMANTIC-OPENAI-LUNA-ADAPTER-01 Implementation Plan

> **For agentic workers:** Execute this plan in the existing `Core-AI-jd-breakdown-01` worktree. Preserve untracked parent-milestone artifacts. Do not commit or push.

**Goal:** Add an eval-only OpenAI Responses Structured Outputs provider for `gpt-6-luna`, keeping ModelGateway and PrivacyGateway as the only inference/privacy boundaries.

**Architecture:** Add a narrow OpenAI SDK provider implementing the existing `ModelProvider` protocol. Add an eval-only gateway composition/config path that selects exactly OpenAI without changing the production composition root. Amend the privacy ADR to record the user's explicit, bounded approval for restricted JD processing by this eval path.

**Tech Stack:** Python 3.13, Pydantic v2, OpenAI Python SDK Responses API, existing ModelGateway/PrivacyGateway, pytest, Ruff, mypy.

**Spec:** `PAI-JD-SEMANTIC-OPENAI-LUNA-ADAPTER-01` in the user request; existing extractor contract under `backend/app/job_semantics_eval/`.

## Global Constraints

- Requested model is exactly `gpt-6-luna`.
- Use Responses API strict JSON Schema; never fall back to free-form JSON mode.
- Do not call OpenAI or run EVAL-00 in this milestone.
- RESTRICTED JD data may be processed only under the user's explicit bounded approval and through PrivacyGateway/RoutingPolicy.
- Do not register OpenAI in production routing or change global production defaults.
- Preserve Gemini support and frozen EVAL-00/EVAL-01 artifacts byte-for-byte.
- No fallback provider, prompt/schema relaxation, API, DB, migration, capability mapping, or production routing changes.

## Review Focus

- Privacy denial must happen before provider transport — test with a denied PrivacyGateway and a zero-call fake client.
- Refusal/incomplete/provider/schema failures must not become predictions or trigger Gemini fallback — test each outcome distinctly.
- Provider payload must contain only source blocks, with embedded instructions kept in data — assert exact serialized request.
- SDK model drift must retain requested and observed identities separately — test a snapshot model response.
- Frozen baseline artifacts must remain unchanged — run verifier and assert no diff in frozen eval directories.

### Task 1: Add OpenAI Responses provider and gateway metadata

Add `app/model_gateway/openai_responses.py`; minimally extend provider/audit contracts for response ID and total/cached token usage; map SDK refusal, incomplete, transient transport, and schema/provider failures to distinct safe gateway errors. Use strict `text.format.type=json_schema` with the supplied schema.

### Task 2: Add eval-only configuration/composition and privacy ADR amendment

Add `OPENAI_API_KEY` as a secret setting and an eval-only composer that explicitly requests provider `openai`, model `gpt-6-luna`, and the existing restricted-data PrivacyGateway/RoutingPolicy. Do not modify `app.main` or the frozen EVAL-00 runner. Amend ADR-0004 to record the bounded approval and non-production scope.

### Task 3: Regression tests

Use fake SDK transports only. Cover exact model/API/schema, strict parse through existing gateway, payload allowlist/injection, privacy denial before transport, refusal/incomplete/schema/provider failures, bounded retries/no fallback, response metadata/model identity, configuration, and deterministic spec hashing. Confirm no test requires an API key.

### Task 4: Verify frozen artifacts and regressions

Run focused OpenAI/extractor/privacy/gateway/provider tests; verify EVAL-00/EVAL-01 freeze identities and byte-level immutability; run Ruff, format, scoped mypy, diff check, then the broader backend suite if available. Never execute the live baseline.
