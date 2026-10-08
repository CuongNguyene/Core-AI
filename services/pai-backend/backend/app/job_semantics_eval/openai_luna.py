"""Eval-only ModelGateway composition for the frozen GPT-6 Luna extractor path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel

from app.job_semantics_eval.contracts import JobRequirementExtractionOutputV1, ProviderInputV1
from app.job_semantics_eval.provider import (
    SYSTEM_INSTRUCTION,
    USER_INSTRUCTION,
    register_extractor_contracts,
)
from app.model_gateway.errors import (
    ProviderIncompleteError,
    ProviderRefusalError,
    ProviderResponseError,
    ProviderSchemaError,
    ProviderTimeoutError,
    StructuredOutputFailedError,
)
from app.model_gateway.openai_responses import LUNA_MODEL, OpenAIClient, OpenAIResponsesProvider
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.providers import ProviderRegistry
from app.model_gateway.routing import RoutingPolicy
from app.model_gateway.schema_registry import OutputSchemaRegistry
from app.model_gateway.service import ModelGatewayService
from app.privacy.service import LocalPIIInspector, PrivacyService
from app.shared.config import Settings

OPENAI_PROVIDER_ID = "openai"
SOURCE_ADAPTER_SHA256 = (
    "sha256:"
    + hashlib.sha256(Path(__file__).with_name("source_adapter.py").read_bytes()).hexdigest()
)


def prepare_openai_luna_settings(settings: Settings) -> Settings:
    """Bind the eval-only adapter to the repository's approved OpenAI settings.

    The shared deployment convention stores the OpenAI credential in
    ``MODEL_API_KEY``.  The eval gateway has an explicit external-provider
    boundary, so copy that credential into its isolated external-provider
    fields only after validating provider, model, endpoint, and privacy gates.
    """
    parsed_base_url = urlparse(settings.vllm_base_url)
    api_key = settings.vllm_api_key.get_secret_value()
    if (
        settings.model_provider != OPENAI_PROVIDER_ID
        or settings.vllm_model != LUNA_MODEL
        or parsed_base_url.scheme != "https"
        or parsed_base_url.hostname != "api.openai.com"
        or not api_key
        or api_key == "local-token"
        or not settings.external_ai_enabled
        or not settings.external_restricted_data_approved
    ):
        raise ValueError("configured OpenAI Luna provider/model/privacy settings are not approved")
    return settings.model_copy(
        update={
            "external_ai_provider": OPENAI_PROVIDER_ID,
            "external_ai_api_key": settings.vllm_api_key,
        }
    )


def openai_execution_status(error: Exception) -> str:
    """Normalize transport outcomes without conflating them with semantic output."""
    if isinstance(error, ProviderRefusalError):
        return "REFUSAL"
    if isinstance(error, ProviderIncompleteError):
        return "INCOMPLETE"
    if isinstance(error, (ProviderSchemaError, StructuredOutputFailedError)):
        return "SCHEMA_ERROR"
    if isinstance(error, (ProviderResponseError, ProviderTimeoutError)):
        return "PROVIDER_ERROR"
    return "PROVIDER_ERROR"


def build_openai_luna_gateway(
    settings: Settings, *, client: OpenAIClient | None = None
) -> ModelGatewayService:
    """Build an isolated gateway; never registered in the production composition root."""
    if (
        settings.external_ai_provider != OPENAI_PROVIDER_ID
        or not settings.external_ai_api_key.get_secret_value()
    ):
        raise ValueError("OpenAI eval provider is not selected/configured")

    provider = OpenAIResponsesProvider(
        api_key=settings.external_ai_api_key,
        timeout_seconds=settings.vllm_timeout_seconds,
        max_retries=settings.vllm_max_retries,
        retry_delay_seconds=settings.model_retry_base_delay_seconds,
        client=client,
    )
    providers = ProviderRegistry()
    providers.register(provider)
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extractor_contracts(prompts, schemas)
    return ModelGatewayService(
        prompt_templates=prompts,
        output_schemas=schemas,
        privacy_gateway=PrivacyService(
            LocalPIIInspector(),
            policy_version=settings.privacy_policy_version,
            external_public_data_enabled=settings.external_ai_enabled,
        ),
        routing_policy=RoutingPolicy(
            external_ai_enabled=settings.external_ai_enabled,
            external_restricted_data_approved=settings.external_restricted_data_approved,
            external_provider_id=OPENAI_PROVIDER_ID,
            configured_provider_id=OPENAI_PROVIDER_ID,
        ),
        providers=providers,
        model=LUNA_MODEL,
        # The provider uses strict Structured Outputs; a changed-prompt repair
        # would violate the frozen semantic request and is disabled for this path.
        max_structured_repair_retries=0,
    )


def openai_luna_spec_fingerprint(
    *,
    model: str = LUNA_MODEL,
    system_instruction: str = SYSTEM_INSTRUCTION,
    extractor_instruction: str = USER_INSTRUCTION,
    output_schema: type[BaseModel] = JobRequirementExtractionOutputV1,
    provider_input_schema: type[BaseModel] = ProviderInputV1,
    privacy_policy_identity: str,
    source_adapter_identity: str = SOURCE_ADAPTER_SHA256,
) -> str:
    """Hash all semantic/provider input identities required before a live run."""
    artifact = {
        "provider": OPENAI_PROVIDER_ID,
        "api_family": "responses",
        "structured_output": "json_schema_strict",
        "model": model,
        "system_instruction": system_instruction,
        "extractor_instruction": extractor_instruction,
        "output_schema": output_schema.model_json_schema(),
        "provider_input_schema": provider_input_schema.model_json_schema(),
        "privacy_policy_identity": privacy_policy_identity,
        "source_adapter_identity": source_adapter_identity,
    }
    canonical = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
