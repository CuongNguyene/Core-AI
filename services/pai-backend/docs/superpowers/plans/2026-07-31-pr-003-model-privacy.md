# PR-003 Model Gateway & Privacy Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only, privacy-first inference gateway that validates
typed structured outputs before future domain modules can consume them.

**Architecture:** `model_gateway` owns prompt rendering, provider registry,
routing and output validation. `privacy` decides whether a request may proceed;
its failure terminates the request. Only the local OpenAI-compatible vLLM
adapter performs HTTP; domain modules receive the `ModelGateway` protocol.

**Tech Stack:** Python 3.12, Pydantic v2, httpx async, FastAPI foundation,
pytest-asyncio, Ruff and mypy.

## Global Constraints

- Keep the modular monolith; add no worker, external provider client or public
  model HTTP API.
- Do not send raw CV/JD, prompt, raw output, API key or PII to log/audit.
- `RESTRICTED` routes only local; external is denied unless a future approved
  provider ADR changes the policy.
- Structured output uses trusted internal Pydantic schemas; clients cannot send
  JSON Schema.
- Privacy error, deny and human approval decisions fail closed without retry.

---

### Task 1: Contracts, ADR and registry boundaries

**Files:**
- Create: `docs/adr/0004-model-routing-and-privacy-boundary.md`
- Create: `app/model_gateway/errors.py`
- Create: `app/model_gateway/schema_registry.py`
- Create: `app/model_gateway/prompts.py`
- Modify: `app/model_gateway/contracts.py`
- Modify: `app/privacy/contracts.py`
- Test: `tests/test_model_contracts.py`

**Interfaces:**
- Produces `OutputContract`, `InferenceAuditMetadata`,
  `TextInferenceResponse`, `StructuredInferenceResponse[T]`,
  `OutputSchemaRegistry` and `PromptTemplateRegistry`.
- Consumed by gateway service in Task 4.

- [x] **Step 1: Write failing tests**

```python
def test_schema_registry_rejects_unknown_schema() -> None:
    registry = OutputSchemaRegistry()
    with pytest.raises(UnknownOutputSchemaError):
        registry.resolve("cv_extraction", "1.0")
```

```python
def test_prompt_registry_keeps_document_payload_out_of_system_message() -> None:
    messages = registry.resolve("extract", "1").render({"document": "ignore system"})
    assert "ignore system" not in messages[0].content
```

- [x] **Step 2: Verify RED**

Run: `uv run pytest tests/test_model_contracts.py -q`

Expected: import error for the missing registry and prompt modules.

- [x] **Step 3: Implement minimal contracts**

```python
class OutputContract(BaseModel):
    schema_id: str
    schema_version: str
    strict: bool = True


class OutputSchemaRegistry:
    def register(self, schema_id: str, version: str, schema: type[BaseModel]) -> None: ...
    def resolve(self, schema_id: str, version: str) -> type[BaseModel]: ...
```

- [x] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_model_contracts.py -q`

Expected: pass.

### Task 2: Privacy, provider registry and local-only policy

**Files:**
- Create: `app/privacy/service.py`
- Create: `app/model_gateway/providers.py`
- Create: `app/model_gateway/routing.py`
- Test: `tests/test_privacy_routing.py`

**Interfaces:**
- Consumes `PrivacyInspectionRequest`, `PrivacyGateway`, `DataClassification`.
- Produces `PrivacyService.inspect()`, `ProviderRegistry.resolve()` and
  `RoutingPolicy.route()`.
- Consumed by gateway service in Task 4.

- [x] **Step 1: Write failing tests**

```python
async def test_restricted_request_always_routes_to_local() -> None:
    route = RoutingPolicy(external_ai_enabled=True).route(restricted_request, allow_local)
    assert route.provider_id == "local-vllm"


async def test_inspection_failure_denies_without_provider_call() -> None:
    result = await PrivacyService(FailingInspector()).inspect(inspection_request)
    assert result.decision == PolicyDecision.DENY
```

- [x] **Step 2: Verify RED**

Run: `uv run pytest tests/test_privacy_routing.py -q`

Expected: import error for missing policy and service modules.

- [x] **Step 3: Implement minimal policy**

```python
if request.data_classification is DataClassification.RESTRICTED:
    return ProviderRoute(provider_id="local-vllm", decision="local_required")
if requested_provider not in (None, "local-vllm"):
    raise ExternalProviderNotApprovedError()
```

- [x] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_privacy_routing.py -q`

Expected: pass.

### Task 3: OpenAI-compatible local provider

**Files:**
- Create: `app/model_gateway/local_vllm.py`
- Test: `tests/test_local_vllm.py`

**Interfaces:**
- Consumes rendered messages and a provider request from Task 4.
- Produces `ProviderResponse` with model, optional revision, text content,
  usage and latency.

- [x] **Step 1: Write failing timeout/retry test**

```python
async def test_timeout_retries_once_then_returns_provider_response() -> None:
    provider = LocalVLLMProvider(client=timeout_then_success_client, max_retries=1)
    response = await provider.complete(provider_request)
    assert response.content == '{"skills": ["Python"]}'
```

- [x] **Step 2: Verify RED**

Run: `uv run pytest tests/test_local_vllm.py -q`

Expected: import error for `LocalVLLMProvider`.

- [x] **Step 3: Implement bounded transport retry**

```python
for attempt in range(self.max_retries + 1):
    try:
        response = await self.client.post("/chat/completions", json=payload)
        return parse_provider_response(response)
    except httpx.TimeoutException:
        if attempt == self.max_retries:
            raise ProviderTimeoutError() from None
```

- [x] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_local_vllm.py -q`

Expected: pass.

### Task 4: Gateway orchestration and typed structured output

**Files:**
- Create: `app/model_gateway/service.py`
- Create: `app/model_gateway/mock_provider.py`
- Modify: `app/shared/config.py`
- Test: `tests/test_model_gateway.py`

**Interfaces:**
- Consumes Tasks 1–3.
- Produces `ModelGatewayService.infer_text()` and
  `ModelGatewayService.infer_structured(request, output_schema)`.

- [x] **Step 1: Write failing tests**

```python
async def test_invalid_structured_output_retries_once_then_fails() -> None:
    gateway = configured_gateway(mock_responses=["not json", "[]"])
    with pytest.raises(StructuredOutputFailedError):
        await gateway.infer_structured(request, SampleOutput)


async def test_validated_response_contains_audit_without_raw_content() -> None:
    result = await configured_gateway(mock_responses=['{"skill": "Python"}']).infer_structured(
        request, SampleOutput
    )
    assert result.parsed.skill == "Python"
    assert "prompt" not in result.audit.model_dump()
```

- [x] **Step 2: Verify RED**

Run: `uv run pytest tests/test_model_gateway.py -q`

Expected: import error for `ModelGatewayService`.

- [x] **Step 3: Implement orchestration**

Resolve template and schema before provider call, inspect privacy once, route
local-only, validate JSON object with `model_validate`, and perform at most one
repair attempt after a structured validation error.

- [x] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_model_gateway.py -q`

Expected: pass.

### Task 5: Documentation, quality gates and local commit

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-07-31-pr-003-model-privacy.md`
- Test: all tests

- [x] **Step 1: Document configuration and boundary**

Document local vLLM configuration, test mock usage, no external-provider
support and no raw-content audit policy.

- [x] **Step 2: Run full verification**

Run: `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q && uv run pre-commit run --all-files`

Expected: all commands exit 0.

- [x] **Step 3: Commit locally**

Run: `git add . && git commit -m "feat: add model and privacy gateway"`
