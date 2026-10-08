import logging
from enum import StrEnum

import pytest
from pydantic import BaseModel, ConfigDict

from app.model_gateway.contracts import (
    DataClassification,
    InferencePurpose,
    InferenceRequest,
    OutputContract,
)
from app.model_gateway.errors import PrivacyDeniedError, StructuredOutputFailedError
from app.model_gateway.mock_provider import MockProvider
from app.model_gateway.prompts import PromptTemplate, PromptTemplateRegistry
from app.model_gateway.providers import ProviderRegistry, ProviderRequest, ProviderResponse
from app.model_gateway.routing import RoutingPolicy
from app.model_gateway.schema_registry import OutputSchemaRegistry
from app.model_gateway.service import ModelGatewayService
from app.privacy.service import PIIInspection, PrivacyService


class SampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str


class SampleProcess(StrEnum):
    APPLY = "apply"


class EnumOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    process: SampleProcess


class CleanInspector:
    async def inspect(self, payload: dict[str, object]) -> PIIInspection:
        return PIIInspection()


class FailingInspector:
    async def inspect(self, payload: dict[str, object]) -> PIIInspection:
        raise RuntimeError("PII service failed")


class RecordingProvider:
    provider_id = "local-vllm"
    is_external = False

    def __init__(self) -> None:
        self.call_count = 0
        self.last_request: ProviderRequest | None = None

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.call_count += 1
        self.last_request = request
        return ProviderResponse(
            provider=self.provider_id,
            model="mock-local",
            content='{"skill":"Python"}',
            latency_ms=0,
        )


@pytest.mark.asyncio
async def test_gateway_accepts_provider_parsed_output_without_a_second_json_parse() -> None:
    gateway, provider = configured_gateway(["not-json"])

    async def typed_complete(request: ProviderRequest) -> ProviderResponse:
        del request
        return ProviderResponse(
            provider="local-vllm",
            model="mock-local",
            content="not-json",
            structured_output=SampleOutput(skill="typed result"),
            latency_ms=0,
        )

    provider.complete = typed_complete  # type: ignore[method-assign]

    result = await gateway.infer_structured(structured_request(), SampleOutput)

    assert result.parsed == SampleOutput(skill="typed result")


def structured_request() -> InferenceRequest:
    return InferenceRequest(
        purpose=InferencePurpose.CV_EXTRACTION,
        data_classification=DataClassification.RESTRICTED,
        prompt_template_id="sample_extraction",
        prompt_template_version="1.0",
        payload={"document": "Candidate has Python experience."},
        output_contract=OutputContract(schema_id="sample_extraction", schema_version="1.0"),
        output_token_budget=3072,
        correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    )


def configured_gateway(
    responses: list[str], inspector: CleanInspector | FailingInspector | None = None
) -> tuple[ModelGatewayService, MockProvider]:
    templates = PromptTemplateRegistry()
    templates.register(
        PromptTemplate(
            template_id="sample_extraction",
            version="1.0",
            system_instruction="Extract structured evidence only.",
            user_instruction="Return the requested JSON object.",
        )
    )
    schemas = OutputSchemaRegistry()
    schemas.register("sample_extraction", "1.0", SampleOutput)
    provider = MockProvider(provider_id="local-vllm", model="mock-local", responses=responses)
    providers = ProviderRegistry()
    providers.register(provider)
    gateway = ModelGatewayService(
        prompt_templates=templates,
        output_schemas=schemas,
        privacy_gateway=PrivacyService(inspector or CleanInspector(), policy_version="privacy-v1"),
        routing_policy=RoutingPolicy(external_ai_enabled=False),
        providers=providers,
        model="mock-local",
    )
    return gateway, provider


@pytest.mark.asyncio
async def test_privacy_failure_stops_before_provider_call() -> None:
    gateway, provider = configured_gateway(['{"skill":"Python"}'], inspector=FailingInspector())

    with pytest.raises(PrivacyDeniedError):
        await gateway.infer_structured(structured_request(), SampleOutput)

    assert provider.call_count == 0


@pytest.mark.asyncio
async def test_structured_output_is_validated_and_returns_safe_audit_metadata() -> None:
    gateway, provider = configured_gateway(['{"skill":"Python"}'])

    result = await gateway.infer_structured(structured_request(), SampleOutput)

    assert result.parsed == SampleOutput(skill="Python")
    assert provider.call_count == 1
    audit = result.audit.model_dump()
    assert audit["provider"] == "local-vllm"
    assert audit["data_boundary"] == "unknown"
    assert audit["output_schema_id"] == "sample_extraction"
    assert audit["policy_version"] == "privacy-v1"
    assert "prompt" not in audit
    assert "payload" not in audit
    assert "raw_content" not in audit


def test_strict_structured_json_accepts_valid_enum_wire_values() -> None:
    gateway, _ = configured_gateway(['{"skill":"Python"}'])

    result = gateway._validate_structured_output('{"process":"apply"}', EnumOutput, strict=True)

    assert result == EnumOutput(process=SampleProcess.APPLY)


def test_structured_json_recovers_common_llm_syntax_errors() -> None:
    gateway, _ = configured_gateway(['{"skill":"Python"}'])

    result = gateway._validate_structured_output(
        '```json\n{"skill":"Python",}\n```', SampleOutput, strict=True
    )

    assert result == SampleOutput(skill="Python")


@pytest.mark.asyncio
async def test_invalid_structured_output_retries_once_then_fails() -> None:
    gateway, provider = configured_gateway(["not-json", "[]"])

    with pytest.raises(StructuredOutputFailedError) as error:
        await gateway.infer_structured(structured_request(), SampleOutput)

    assert error.value.category == "invalid_model_output_shape"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_invalid_json_log_excludes_raw_model_content(caplog) -> None:
    gateway, provider = configured_gateway(["not-json", "still-not-json"])

    with (
        caplog.at_level(logging.WARNING, logger="app.model_gateway.service"),
        pytest.raises(StructuredOutputFailedError) as error,
    ):
        await gateway.infer_structured(structured_request(), SampleOutput)

    assert error.value.category == "invalid_model_json"
    assert "model_output_invalid_json" in caplog.text
    assert "content_length" in caplog.text
    assert "not-json" not in caplog.text
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_schema_validation_failure_is_not_returned_to_domain() -> None:
    gateway, provider = configured_gateway(['{"skill":[],"unexpected":true}', '{"skill":[]}'])

    with pytest.raises(StructuredOutputFailedError) as error:
        await gateway.infer_structured(structured_request(), SampleOutput)

    assert error.value.category == "model_output_validation_failed"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_schema_validation_log_contains_only_safe_error_paths(caplog) -> None:
    gateway, provider = configured_gateway(['{"skill":[]}', '{"skill":[]}'])

    with (
        caplog.at_level(logging.WARNING, logger="app.model_gateway.service"),
        pytest.raises(StructuredOutputFailedError),
    ):
        await gateway.infer_structured(structured_request(), SampleOutput)

    assert "model_output_validation_failed" in caplog.text
    assert "skill" in caplog.text
    assert "[]" not in caplog.text
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_schema_repair_prompt_includes_safe_validation_paths() -> None:
    gateway, provider = configured_gateway(['{"skill":[]}', '{"skill":"Python"}'])

    result = await gateway.infer_structured(structured_request(), SampleOutput)

    assert result.parsed == SampleOutput(skill="Python")
    assert (
        provider.requests[1]
        .messages[-1]
        .content.endswith(
            "Error category: model_output_validation_failed; paths=skill; types=string_type."
        )
    )


@pytest.mark.asyncio
async def test_invalid_json_recovery_is_bounded_and_audited() -> None:
    gateway, provider = configured_gateway(["fenced or malformed output", '{"skill":"Python"}'])

    result = await gateway.infer_structured(structured_request(), SampleOutput)

    assert result.parsed == SampleOutput(skill="Python")
    assert provider.call_count == 2
    assert result.audit.attempt_count == 2


def test_inference_request_exposes_output_token_budget() -> None:
    request = structured_request()

    assert request.output_token_budget == 3072


@pytest.mark.asyncio
async def test_structured_inference_passes_request_budget_to_provider() -> None:
    templates = PromptTemplateRegistry()
    templates.register(
        PromptTemplate(
            template_id="sample_extraction",
            version="1.0",
            system_instruction="Extract structured evidence only.",
            user_instruction="Return the requested JSON object.",
        )
    )
    schemas = OutputSchemaRegistry()
    schemas.register("sample_extraction", "1.0", SampleOutput)
    provider = RecordingProvider()
    providers = ProviderRegistry()
    providers.register(provider)
    gateway = ModelGatewayService(
        prompt_templates=templates,
        output_schemas=schemas,
        privacy_gateway=PrivacyService(CleanInspector(), policy_version="privacy-v1"),
        routing_policy=RoutingPolicy(external_ai_enabled=False),
        providers=providers,
        model="mock-local",
    )

    await gateway.infer_structured(structured_request(), SampleOutput)

    assert provider.last_request is not None
    assert provider.last_request.max_tokens == 3072
