# PR-003 Model Gateway & Privacy Gateway Design

## Goal

Provide an internal, typed inference boundary for future CV/JD extraction and
other MVP use cases. It must route restricted data locally, deny external use
by default, validate structured model output before it reaches domain modules,
and create privacy-safe audit metadata.

## Scope

- Implement the existing `ModelGateway` and `PrivacyGateway` contracts.
- Add a local OpenAI-compatible vLLM HTTP provider and an in-memory mock
  provider for tests.
- Add provider registry, local-only routing policy, bounded transport retry and
  one structured-output repair retry.
- Add PII inspection abstraction and a policy gateway that fails closed.
- Add internal Pydantic output-schema registry keyed by schema ID and version.
- Add audit metadata only; raw prompt, payload, model response and API key are
  never persisted or logged.

## Non-goals

- No HTTP endpoint accepts model requests or client-supplied JSON Schema.
- No external provider client, external provider allow-list, production
  identity, queue/worker, CV/JD business schema, or domain extraction service.
- No semantic validation rules beyond the Pydantic model supplied by a future
  use case.

## Selected approach

`ModelGateway` exposes two internal methods:

```python
async def infer_text(request: InferenceRequest) -> TextInferenceResponse: ...


async def infer_structured(
    request: InferenceRequest,
    output_schema: type[T],
) -> StructuredInferenceResponse[T]: ...
```

`InferenceRequest` contains serializable `OutputContract(schema_id,
schema_version, strict)` metadata. The runtime `type[T]` is not serialized and
is supplied only by trusted application code. The gateway registers or resolves
the matching schema in `OutputSchemaRegistry`; a mismatch or unknown schema is
a local programming error and makes no provider call.

The gateway treats a provider response as untrusted:

```text
provider response
→ extract JSON
→ parse JSON
→ require top-level object
→ Pydantic model_validate
→ typed result for trusted caller
```

Invalid JSON, non-object JSON, and Pydantic validation failure have distinct
internal errors. A structured-output failure receives at most one repair retry
with sanitized error categories; neither raw output nor prompt is logged.
Future CV/JD modules own semantic/domain validation after this boundary.

## Routing and privacy design

`PrivacyGateway.inspect()` is executed before routing. Its PII inspector is a
protocol with a conservative local implementation and an injectable fake for
tests. Inspection exception, missing result, `DENY`, or human approval result
terminates the request; it never falls back to another provider.

`RoutingPolicy` returns only `local-vllm` in PR-003. `RESTRICTED` is always
local. `external_ai_enabled=false` forbids every external route. Even if a
future external provider is registered, no route is allowed until a separate
approved-provider ADR changes this policy.

```text
InferenceRequest
→ PrivacyGateway.inspect
→ RoutingPolicy.route
→ ProviderRegistry.resolve("local-vllm" | "mock")
→ LocalVLLMProvider / MockProvider
→ Pydantic structured validation when requested
→ audit metadata
```

The local vLLM adapter uses `httpx.AsyncClient` and OpenAI-compatible
`/chat/completions`. API keys are read only from `Settings` as `SecretStr` and
are sent as an HTTP header only when non-empty. Timeout/network failures retry
with a small, configured attempt count; privacy/policy and schema-registry
failures do not retry.

## Audit metadata

The gateway returns or emits an internal `InferenceAuditMetadata` record with:

- provider and model;
- model revision when returned by the provider;
- prompt template ID/version;
- output schema ID/version when structured;
- policy version and routing decision;
- correlation ID, attempt count, latency and token usage;
- outcome category only.

It excludes prompt, payload, raw response, PII detector values and API keys.
PR-003 does not add persistence; a later Audit module can consume this typed
metadata.

## Alternatives rejected

- Valid JSON object only: too weak because wrong field types and missing source
  evidence would leak into domain logic.
- Client-provided JSON Schema: expands attack surface, cost and audit surface,
  and makes public API depend on provider capability.
- Trusting provider JSON mode: useful as an optimization but not an application
  trust boundary.
- Sending inspection failures to a fallback provider: violates fail-closed
  privacy behavior.

## ADR and migration

PR-003 adds ADR-0004 to record local-only routing, internal schema registry,
Pydantic re-validation and the requirement for a future approved-provider ADR.
There is no database migration and no public HTTP API change.

## Test acceptance criteria

- `RESTRICTED` request routes to local provider regardless of preference.
- External route is rejected when `external_ai_enabled` is false.
- PII inspection error or deny decision prevents every provider call.
- HTTP timeout retries only within the configured limit.
- Invalid JSON, non-object JSON and invalid Pydantic output fail with the
  correct error category; structured repair runs at most once.
- Audit metadata contains required operational fields and does not contain raw
  prompt/payload/output values.
