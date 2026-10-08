# PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-01

Status: `BASELINE_MEASURED_NO_PRODUCTION_DECISION` — execution completed, but semantic quality metrics are not measurable because every provider attempt failed.

## Repository and frozen EVAL-00 identity

Implementation worktree: `/Users/mac/Developers/work/LMS/Core-AI-jd-breakdown-01`, branch `feat/pai-jd-semantic-requirement-breakdown-01`, HEAD `0654cf0f3d64aafaa7c001c74e578643d07d1e03` before and after. No commit or push.

Before implementation and again immediately before the first provider attempt, the frozen EVAL-00 verifier passed (`artifact_count=7`, `valid=true`). The corpus remains 40 postings / 301 statements, dataset SHA-256 `6b9453a1c000f51a95b0ead39a94aca55eb7582489fca2a1b13550128df32cc5`, semantic fingerprint `b479fe2ecce0b7278506c4376e336b0cda916eba9f57c4e73b661e829a867421`, taxonomy SHA-256 `bfb17a8f931e11f8c3e455048e9b4669c0cdd444246a66ade95a287e5a2622b4`, and `provider_calls_before_freeze=0`. Frozen EVAL-00 files were not edited.

## Gateway/privacy audit

The extractor uses `ModelGatewayService.infer_structured`, registered `PromptTemplateRegistry` and `OutputSchemaRegistry`, existing `PrivacyService`, and existing `RoutingPolicy`. It does not add an HTTP client or production routing. The selected configuration was external provider `gemini`, model `gemini-3.5-flash-lite`; external AI and restricted-data approval were enabled. The separate `external_ai_provider` setting named another provider, but the existing composition root selects the configured provider ID when that provider is external, so the effective route was Gemini. Secret values were never printed or placed in artifacts.

The request is `JD_EXTRACTION` / `RESTRICTED`. It contains only source block IDs, source field names, and visible text from `job_description_html` and `job_requirements_html`. It excludes application refs, posting URLs, candidate data, gold labels, and evaluation metadata. Existing prompt rendering marks the payload as untrusted data. Gateway/provider transport retries and the gateway's one bounded structured-output repair remain in force; retry count is not reliably exposed when the provider call fails.

## Extractor and validation

The deterministic adapter implements the frozen EVAL-00 HTML text view: no browser/network, inline markup is transparent, entities are decoded once, NBSP becomes a space, block/list order is retained, whitespace is normalized within blocks, empty blocks are removed, and deterministic source-local block IDs are assigned. Across all 40 corpus cases, its joined block view matched EVAL-00's normative HTML text view. Null, omitted, empty, and whitespace-only source fields produce no blocks and no fabricated text.

The strict output DTO permits only source block references, exact source text, normalized statement, frozen statement type and capability-relevance enums, and optional exact `capability_signal_text`. Unknown fields are rejected. Server validation rejects unknown/non-adjacent blocks, mixed source fields, invented spans, altered normalized text, and non-exact signal text. Field, offsets, and provenance are server-derived. No canonical capability ref, level, confidence, role profile, gap, or production semantic state is created. Every prediction would remain `UNVALIDATED`.

## Freeze before provider execution

Frozen extractor spec SHA-256: `a1342ed0eb386485f5e965acc8c25b24a45e717ad645d7e00c8cb74cb4ae6721`.

Freeze manifest: [`freeze-manifest-v1.json`](../../backend/evals/job_semantics/requirement_breakdown_01/freeze-manifest-v1.json). It binds the extractor and provider-input/output schemas, source adapter, validation, provider adapter, matching/metrics/runner specs, code HEAD, and EVAL-00 identities. Freeze time: `2026-10-08T04:12:41.082392Z`; `provider_calls_before_freeze=0`.

Artifact components include `extractor-spec-v1.json`, `provider-input-schema-v1.json`, `output-schema-v1.json`, `source-adapter-spec-v1.json`, `matching-spec-v1.json`, `metrics-spec-v1.json`, and `runner-spec-v1.json`. The matching plan uses exact `(source_field, source_text)` identity and source-order occurrence handling; no LLM judge or embeddings are used. Metrics include decomposition, statement type, capability relevance, source fidelity, and domain/language/difficulty/boundary slices. Generated run artifacts are local synthetic-only JSON; raw provider response bodies are not exposed by ModelGateway, so only the canonical parsed structured-output hash can be captured on successful output.

## First full run

The frozen corpus was attempted sequentially in one full run, without inspecting or tuning on partial outputs. Result directory: [`runs/20261008T041254Z-0b79cdb7/`](../../backend/evals/job_semantics/requirement_breakdown_01/runs/20261008T041254Z-0b79cdb7/).

- Cases attempted: 40/40
- Successful structured outputs: 0
- Provider errors: 40 (`provider_response_error`)
- Successful model audit/revision records: none
- Transport logs included HTTP 400 and HTTP 429 responses; case-level HTTP status/retry counts were not provided by gateway exception metadata.

The raw `metrics.json` is retained. It contains zero-denominator defaults that display some rates as `1.0`; with zero completed cases those are not measured results and must not be reported. The reviewed interpretation is [`metrics-review.json`](../../backend/evals/job_semantics/requirement_breakdown_01/runs/20261008T041254Z-0b79cdb7/metrics-review.json): semantic decomposition/classification/fidelity metrics are `NOT_MEASURABLE_NO_SUCCESSFUL_PROVIDER_OUTPUTS`. No case-level semantic error analysis is possible or claimed. No provider retry/rerun was performed after seeing the completed run.

## Verification

- Frozen EVAL-00 verifier: passed before implementation and immediately before provider execution.
- Focused bridge + EVAL-00 tests: 52 passed.
- Ruff check: passed.
- Ruff format check: passed after formatting.
- Scoped mypy: `mypy --follow-imports=silent app/job_semantics_eval` passed. Regular mypy also surfaced five pre-existing optional-writer errors in untouched `app/documents/safety.py`; those were not changed.
- Full backend suite: not run; all changes are isolated to eval-only extraction and focused tests.
- No migration, public API, production provider routing, capability mapping, role profile, capability level, gap, confidence threshold, or production promotion.
- `git diff --check` and final EVAL-00/freeze verification are recorded in handoff after the final local checks.

## Conclusion and next step

This is an execution/transport failure baseline, not a semantic quality baseline. The only supportable decision is `BASELINE_MEASURED_NO_PRODUCTION_DECISION`; there is no production-readiness conclusion. Before any extractor refinement or new provider run, diagnose the Gemini 400/429 failures through the existing provider contract/configuration. Because EVAL-00 has now been exposed to this extractor family, future quality claims need a fresh held-out corpus; EVAL-00 is now known diagnostic data. Do not change the frozen spec and call a rerun an unbiased improvement.
