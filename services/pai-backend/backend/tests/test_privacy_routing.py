import pytest

from app.model_gateway.contracts import DataClassification, InferencePurpose, InferenceRequest
from app.model_gateway.errors import PrivacyDeniedError
from app.model_gateway.providers import ProviderRegistry
from app.model_gateway.routing import ExternalRoutingDisabledError, RoutingPolicy
from app.privacy.contracts import (
    PolicyDecision,
    PrivacyInspectionRequest,
    PrivacyInspectionResult,
)
from app.privacy.service import PIIInspection, PrivacyService


class FailingInspector:
    async def inspect(self, payload: dict[str, object]) -> PIIInspection:
        raise RuntimeError("PII detector is unavailable")


class CleanInspector:
    async def inspect(self, payload: dict[str, object]) -> PIIInspection:
        return PIIInspection(detected_entity_types=[])


class LocalProvider:
    provider_id = "local-vllm"
    is_external = False


class ExternalProvider:
    provider_id = "vilao-external"
    is_external = True


def inference_request(
    classification: DataClassification, requested_provider: str | None = None
) -> InferenceRequest:
    return InferenceRequest(
        purpose=InferencePurpose.CV_EXTRACTION,
        data_classification=classification,
        prompt_template_id="sample_extraction",
        prompt_template_version="1.0",
        payload={"document": "untrusted content"},
        requested_provider=requested_provider,
        correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    )


def allow_local() -> PrivacyInspectionResult:
    return PrivacyInspectionResult(
        decision=PolicyDecision.ALLOW_LOCAL,
        policy_version="privacy-v1",
    )


def allow_external_sanitized() -> PrivacyInspectionResult:
    return PrivacyInspectionResult(
        decision=PolicyDecision.ALLOW_EXTERNAL_SANITIZED,
        sanitized_payload={"document": "sanitized"},
        policy_version="privacy-v1",
    )


@pytest.mark.asyncio
async def test_privacy_inspection_failure_fails_closed() -> None:
    service = PrivacyService(inspector=FailingInspector(), policy_version="privacy-v1")

    result = await service.inspect(
        PrivacyInspectionRequest(
            purpose=InferencePurpose.CV_EXTRACTION,
            data_classification=DataClassification.SENSITIVE,
            payload={"document": "untrusted content"},
        )
    )

    assert result.decision == PolicyDecision.DENY
    assert result.reasons == ["pii_inspection_failed"]


@pytest.mark.asyncio
async def test_clean_public_research_payload_can_receive_external_sanitized_approval() -> None:
    service = PrivacyService(
        inspector=CleanInspector(),
        policy_version="privacy-v1",
        external_public_data_enabled=True,
    )

    result = await service.inspect(
        PrivacyInspectionRequest(
            purpose=InferencePurpose.LEARNING_CONTENT_GENERATION,
            data_classification=DataClassification.PUBLIC,
            payload={"brief": {"provenance": {"type": "research_fixture"}}},
            requested_provider="vilao",
        )
    )

    assert result.decision is PolicyDecision.ALLOW_EXTERNAL_SANITIZED
    assert result.sanitized_payload == {"brief": {"provenance": {"type": "research_fixture"}}}


@pytest.mark.asyncio
async def test_restricted_data_always_routes_to_local() -> None:
    route = RoutingPolicy(external_ai_enabled=True).route(
        inference_request(DataClassification.RESTRICTED, requested_provider="future-external"),
        allow_local(),
    )

    assert route.provider_id == "local-vllm"
    assert route.decision == "restricted_local_only"


def test_restricted_data_cannot_route_to_external_even_when_requested() -> None:
    with pytest.raises(PrivacyDeniedError):
        RoutingPolicy(
            external_ai_enabled=True, external_provider_id="vilao-external"
        ).route(
            inference_request(DataClassification.RESTRICTED, requested_provider="vilao-external"),
            allow_external_sanitized(),
        )


def test_restricted_default_route_is_denied_when_configured_provider_is_external() -> None:
    with pytest.raises(PrivacyDeniedError):
        RoutingPolicy(
            external_ai_enabled=False,
            configured_provider_id="vilao-external",
            external_provider_id="vilao-external",
        ).route(
            inference_request(DataClassification.RESTRICTED),
            allow_local(),
        )


def test_restricted_default_route_is_denied_for_vilao_actual_endpoint() -> None:
    with pytest.raises(PrivacyDeniedError):
        RoutingPolicy(
            external_ai_enabled=True,
            external_provider_id="vilao",
            configured_provider_id="vilao",
        ).route(
            inference_request(DataClassification.RESTRICTED),
            allow_local(),
        )


def test_restricted_vilao_route_requires_explicit_external_approval() -> None:
    route = RoutingPolicy(
        external_ai_enabled=True,
        external_restricted_data_approved=True,
        external_provider_id="vilao",
        configured_provider_id="vilao",
    ).route(
        inference_request(DataClassification.RESTRICTED),
        allow_local(),
    )

    assert route.provider_id == "vilao"
    assert route.decision == "approved_external_restricted"


def test_external_route_requires_sanitized_privacy_decision() -> None:
    with pytest.raises(PrivacyDeniedError):
        RoutingPolicy(
            external_ai_enabled=True, external_provider_id="vilao-external"
        ).route(
            inference_request(DataClassification.PUBLIC, requested_provider="vilao-external"),
            allow_local(),
        )


def test_approved_external_route_is_explicit_and_identifiable() -> None:
    route = RoutingPolicy(
        external_ai_enabled=True, external_provider_id="vilao-external"
    ).route(
        inference_request(DataClassification.PUBLIC, requested_provider="vilao-external"),
        allow_external_sanitized(),
    )

    assert route.provider_id == "vilao-external"
    assert route.decision == "approved_external_sanitized"


@pytest.mark.asyncio
async def test_external_request_is_denied_when_external_ai_is_disabled() -> None:
    with pytest.raises(ExternalRoutingDisabledError):
        RoutingPolicy(external_ai_enabled=False).route(
            inference_request(DataClassification.PUBLIC, requested_provider="future-external"),
            allow_local(),
        )


def test_provider_registry_resolves_registered_local_provider() -> None:
    provider = LocalProvider()
    registry = ProviderRegistry()
    registry.register(provider)

    assert registry.resolve("local-vllm") is provider
    external = ExternalProvider()
    registry.register(external)
    assert registry.resolve("vilao-external") is external
