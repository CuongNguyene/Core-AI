# PAI-JD-SEMANTIC-OPENAI-LUNA-ADAPTER-01

Status: `OPENAI_GPT6_LUNA_ADAPTER_READY_FOR_FROZEN_BASELINE`

## Scope and privacy decision

The user explicitly approved OpenAI processing of restricted JD source blocks
for this bounded eval-only adapter. ADR-0004 records the scope: only the
requirement-breakdown path with configured provider `openai` and exact model
`gpt-6-luna`; no candidate/CV/employee/ATS data and no production routing.
`EXTERNAL_AI_ENABLED` and `EXTERNAL_RESTRICTED_DATA_APPROVED` remain mandatory
at the existing PrivacyGateway/RoutingPolicy boundary.

## Provider contract

- SDK: `openai==1.109.1` in `uv.lock` (declared as `openai>=1.99.5,<2`).
- API: Responses API `responses.parse(..., text_format=PydanticModel)`.
- Structured output: SDK-generated strict JSON Schema; `output_parsed` must be
  an instance of the exact registered Pydantic model. No prose/JSON repair,
  Markdown stripping, or arbitrary-dict acceptance is used by this adapter.
- The SDK call runs behind `ModelProvider`; the extractor still calls only
  `ModelGateway.infer_structured`. OpenAI is composed in
  `job_semantics_eval.openai_luna` and is not registered in `app.main`.
- Requested model is fixed to `gpt-6-luna`. The provider-returned model is kept
  separately as observed identity; an exact ID or a dated snapshot ID is
  recognized by `model_identity_matches`.
- The production registry and Gemini implementation are unchanged. This
  adapter has no provider fallback. Structured-output repair is disabled for
  the eval composer so schema errors cannot cause a changed-prompt retry.

The official Structured Outputs guide documents the Responses `parse` helper
and Pydantic `text_format` contract:
<https://developers.openai.com/api/docs/guides/structured-outputs>.

## Payload and data handling

The provider request contains only the rendered trusted extractor instructions
and an explicit `source_blocks` projection (`block_id`, `source_field`, `text`).
The trusted instruction treats block contents as untrusted data. The adapter
does not send source application references, posting URLs, EVAL case IDs/gold,
review metadata, candidate evidence, or employee identity. Existing server-side
provenance validation remains responsible for checking returned spans.

The API key uses the existing `EXTERNAL_AI_API_KEY` secret setting; no secret
is emitted in metadata. The Core-AI provider records only parsed structured
output and operational response ID/model/latency/token usage. It does not log
or persist raw SDK response objects or source content. Provider-side retention
and account controls must be checked before a later live run.

## Operational outcomes

Refusal, incomplete response, schema failure, timeout, and other provider
failures remain exceptions rather than semantic predictions. Refusal/incomplete
and schema errors carry only safe response ID/model/latency metadata when
available. `openai_execution_status` maps these into distinct `REFUSAL`,
`INCOMPLETE`, `SCHEMA_ERROR`, and `PROVIDER_ERROR` result categories for a future
runner. Retries are bounded and limited to transport timeout/connection,
rate-limit, and server failures; the same model, schema, and messages are used.

The gateway audit now distinguishes requested and observed model IDs, stores
provider response ID, and records input/output/total/cached token counts where
available. These are operational fields only.
Provider-level retry attempts are also recorded separately from ModelGateway
attempts, including exhausted technical retries. The frozen baseline runner
uses that count and accepts a dated provider snapshot of the exact requested
model as the same model identity.

## Spec hashing and frozen parent artifacts

`openai_luna_spec_fingerprint` binds provider/API family/model, trusted and
extractor instructions, output schema, provider-input schema, privacy identity,
and exact source-adapter file hash. Regression tests prove deterministic
identity and hash changes when these inputs change.

The parent Gemini-based EVAL-00/EVAL-01 artifacts were not edited. EVAL-00
identity remains:

- dataset SHA-256: `sha256:6b9453a1c000f51a95b0ead39a94aca55eb7582489fca2a1b13550128df32cc5`
- semantic fingerprint: `sha256:b479fe2ecce0b7278506c4376e336b0cda916eba9f57c4e73b661e829a867421`
- taxonomy SHA-256: `sha256:bfb17a8f931e11f8c3e455048e9b4669c0cdd444246a66ade95a287e5a2622b4`
- 40 postings / 301 statements

The parent extractor freeze manifest still identifies the earlier Gemini
baseline specification. This adapter does not overwrite it. The next baseline
gate must freeze a separate OpenAI-specific extractor, matching, metrics, and
runner specification before any EVAL-00 provider call.

## Verification

- OpenAI adapter + eval-composition tests: 15 passed (included in focused run).
- Combined adapter, EVAL-00/EVAL-01, JD requirement, privacy, ModelGateway, and
  existing provider regressions: 102 passed in the final focused verification.
- Full backend run: 1,741 passed, 5 skipped, 1 environment-only failure because
  the sandbox denied a test's ephemeral `127.0.0.1` bind. That exact ClamAV
  test passed when rerun with local loopback permission.
- Ruff and format check: passed for touched Python files.
- Scoped mypy: passed for touched production modules.
- EVAL-00 and parent extractor freeze verification: passed with pinned hashes.
- Live OpenAI calls: 0. EVAL-00 baseline calls in this milestone: 0.

No public API, database change, migration, capability mapping, role profile,
gap, or production provider routing was added. This result does not establish
model availability or semantic quality; it only establishes adapter behavior
against fake/local SDK transport.
