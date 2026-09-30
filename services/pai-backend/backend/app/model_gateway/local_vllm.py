import asyncio
from time import perf_counter
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, SecretStr, ValidationError

from app.model_gateway.errors import ProviderResponseError, ProviderTimeoutError
from app.model_gateway.providers import ProviderRequest, ProviderResponse


class _OpenAIMessage(BaseModel):
    content: str


class _OpenAIChoice(BaseModel):
    message: _OpenAIMessage
    finish_reason: str | None = None


class _OpenAIUsage(BaseModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


class _OpenAICompletionResponse(BaseModel):
    model: str | None = None
    choices: list[_OpenAIChoice]
    usage: _OpenAIUsage = Field(default_factory=_OpenAIUsage)


class LocalVLLMProvider:
    def __init__(
        self,
        base_url: str,
        api_key: SecretStr,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        client: httpx.AsyncClient | None = None,
        retry_delay_seconds: float = 0.05,
        provider_id: str = "local-vllm",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        parsed_endpoint = urlparse(self._base_url)
        self.endpoint_origin = f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
        endpoint_host = (parsed_endpoint.hostname or "").casefold()
        if provider_id == "local-vllm" and endpoint_host == "api.vilao.ai":
            provider_id = "vilao"
        self.provider_id = provider_id
        self.is_external = provider_id != "local-vllm" or endpoint_host not in {
            "localhost",
            "127.0.0.1",
            "::1",
            "pai-vllm",
        } and not endpoint_host.endswith(".local")
        self.protocol = "openai_compatible"
        self.deployment_type = "external" if self.is_external else "local"
        self.data_boundary = "external_provider" if self.is_external else "local_runtime"
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client = client
        self._retry_delay_seconds = retry_delay_seconds

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        started_at = perf_counter()
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._post_completion(request)
                parsed = _OpenAICompletionResponse.model_validate(response.json())
                if not parsed.choices:
                    raise ProviderResponseError("Local model returned no choices")
                return ProviderResponse(
                    provider=self.provider_id,
                    model=self._model,
                    model_revision=parsed.model,
                    protocol=self.protocol,
                    deployment_type=self.deployment_type,
                    endpoint_origin=self.endpoint_origin,
                    data_boundary=self.data_boundary,
                    content=self._strip_completed_reasoning(parsed.choices[0].message.content),
                    latency_ms=int((perf_counter() - started_at) * 1000),
                    input_tokens=parsed.usage.prompt_tokens,
                    output_tokens=parsed.usage.completion_tokens,
                    finish_reason=parsed.choices[0].finish_reason,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == self._max_retries:
                    raise ProviderTimeoutError("Local model request timed out") from exc
                await asyncio.sleep(self._retry_delay_seconds)
            except ValidationError as exc:
                raise ProviderResponseError("Local model response is invalid") from exc

        raise AssertionError("Retry loop always returns or raises")

    @staticmethod
    def _strip_completed_reasoning(content: str) -> str:
        marker = "</think>"
        if marker in content:
            content = content.split(marker, 1)[1]
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return stripped

    async def _post_completion(self, request: ProviderRequest) -> httpx.Response:
        payload: dict[str, object] = {
            "model": request.model,
            "messages": [message.model_dump() for message in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        if request.require_json_object:
            payload["response_format"] = {"type": "json_object"}

        headers: dict[str, str] = {}
        api_key = self._api_key.get_secret_value()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if self._client is not None:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self._timeout_seconds,
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        response.raise_for_status()
        return response
