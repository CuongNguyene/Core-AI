from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from app.model_gateway.contracts import (
    DataClassification,
    InferencePurpose,
    InferenceRequest,
    OutputContract,
)
from app.model_gateway.errors import PrivacyDeniedError
from app.model_gateway.openai_responses import OpenAIResponsesProvider
from app.model_gateway.prompts import PromptTemplate, PromptTemplateRegistry
from app.model_gateway.providers import ProviderRegistry
from app.model_gateway.routing import RoutingPolicy
from app.model_gateway.schema_registry import OutputSchemaRegistry
from app.model_gateway.service import ModelGatewayService
from app.privacy.service import PIIInspection, PrivacyService


class GatewayOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    extracted_text: str


class CleanInspector:
    async def inspect(self, payload: dict[str, object]) -> PIIInspection:
        del payload
        return PIIInspection()


class FailingInspector:
    async def inspect(self, payload: dict[str, object]) -> PIIInspection:
        del payload
        raise RuntimeError("private inspector detail")


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            status="completed",
            output=[SimpleNamespace(type="message", content=[])],
            output_parsed=GatewayOutput(extracted_text="synthetic result"),
            model="gpt-6-luna-2026-10-01",
            usage=SimpleNamespace(input_tokens=9, output_tokens=4),
        )

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            status="completed",
            output=[SimpleNamespace(type="message", content=[])],
            output_text="synthetic text",
            model="gpt-6-luna-2026-10-01",
            usage=SimpleNamespace(input_tokens=4, output_tokens=2),
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()

    async def close(self) -> None:
        return None


def build_gateway(
    *, inspector: CleanInspector | FailingInspector, client: FakeOpenAIClient
) -> ModelGatewayService:
    prompt_registry = PromptTemplateRegistry()
    prompt_registry.register(
        PromptTemplate(
            template_id="synthetic_cv_extract",
            version="1.0",
            system_instruction="Extract only source-grounded text.",
            user_instruction="Extract the requested field.",
        )
    )
    schema_registry = OutputSchemaRegistry()
    schema_registry.register("synthetic_cv_extract", "1.0", GatewayOutput)
    provider = OpenAIResponsesProvider(
        base_url="https://api.openai.com/v1",
        api_key=SecretStr("synthetic-test-key"),
        model="gpt-6-luna",
        timeout_seconds=5,
        max_retries=0,
        max_tokens=2048,
        client=client,  # type: ignore[arg-type]
    )
    providers = ProviderRegistry()
    providers.register(provider)
    return ModelGatewayService(
        prompt_templates=prompt_registry,
        output_schemas=schema_registry,
        privacy_gateway=PrivacyService(
            inspector,
            policy_version="synthetic-test-policy",
            external_public_data_enabled=True,
        ),
        routing_policy=RoutingPolicy(
            external_ai_enabled=True,
            external_restricted_data_approved=True,
            external_provider_id="openai",
            configured_provider_id="openai",
        ),
        providers=providers,
        model="gpt-6-luna",
        max_structured_repair_retries=0,
    )


def structured_request() -> InferenceRequest:
    return InferenceRequest(
        purpose=InferencePurpose.CV_EXTRACTION,
        data_classification=DataClassification.RESTRICTED,
        prompt_template_id="synthetic_cv_extract",
        prompt_template_version="1.0",
        payload={"source_text": "synthetic candidate evidence"},
        output_contract=OutputContract(
            schema_id="synthetic_cv_extract",
            schema_version="1.0",
            strict=True,
        ),
        requested_provider="openai",
        correlation_id="synthetic-correlation",
    )


@pytest.mark.asyncio
async def test_model_gateway_retains_local_pydantic_validation_and_openai_audit() -> None:
    client = FakeOpenAIClient()
    gateway = build_gateway(inspector=CleanInspector(), client=client)

    response = await gateway.infer_structured(structured_request(), GatewayOutput)

    assert response.parsed == GatewayOutput(extracted_text="synthetic result")
    assert response.audit.provider == "openai"
    assert response.audit.model == "gpt-6-luna"
    assert response.audit.model_revision == "gpt-6-luna-2026-10-01"
    assert response.audit.routing_decision == "approved_external_restricted"
    assert len(client.responses.calls) == 1
    assert client.responses.calls[0]["text_format"] is GatewayOutput


@pytest.mark.asyncio
async def test_privacy_inspection_failure_prevents_openai_transport() -> None:
    client = FakeOpenAIClient()
    gateway = build_gateway(inspector=FailingInspector(), client=client)

    with pytest.raises(PrivacyDeniedError):
        await gateway.infer_structured(structured_request(), GatewayOutput)

    assert client.responses.calls == []
