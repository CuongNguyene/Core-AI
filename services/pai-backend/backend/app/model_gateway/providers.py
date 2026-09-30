from typing import Protocol

from pydantic import BaseModel, Field

from app.model_gateway.contracts import DocumentInput
from app.model_gateway.errors import DuplicateProviderError, UnknownProviderError
from app.model_gateway.prompts import ChatMessage


class ProviderRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    require_json_object: bool = False
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, gt=0)
    json_schema: dict[str, object] | None = None
    document: DocumentInput | None = None


class ProviderResponse(BaseModel):
    provider: str
    model: str
    model_revision: str | None = None
    content: str
    protocol: str = "unknown"
    deployment_type: str = "unknown"
    endpoint_origin: str | None = None
    data_boundary: str = "unknown"
    finish_reason: str | None = None
    latency_ms: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class ModelProvider(Protocol):
    provider_id: str
    is_external: bool

    async def complete(self, request: ProviderRequest) -> ProviderResponse: ...


class ProviderRegistry:
    """Provider instances available to the internal gateway composition root."""

    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider) -> None:
        if provider.provider_id in self._providers:
            raise DuplicateProviderError(f"Provider already registered: {provider.provider_id}")
        self._providers[provider.provider_id] = provider

    def resolve(self, provider_id: str) -> ModelProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise UnknownProviderError(f"Provider is not registered: {provider_id}") from exc
