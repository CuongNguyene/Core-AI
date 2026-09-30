import asyncio
import base64
from time import perf_counter
from urllib.parse import urlparse

import httpx
from pydantic import SecretStr

from app.model_gateway.errors import (
    ProviderOutputBudgetError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from app.model_gateway.providers import ProviderRequest, ProviderResponse


class GeminiProvider:
    """Google Gemini generateContent adapter for the production model gateway."""

    provider_id = "gemini"
    is_external = True

    def __init__(
        self,
        endpoint: str,
        api_key: SecretStr,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        max_tokens: int = 131072,
        thinking_level: str = "high",
        client: httpx.AsyncClient | None = None,
        retry_delay_seconds: float = 0.05,
        provider_id: str = "gemini",
    ) -> None:
        self._endpoint = endpoint
        parsed_endpoint = urlparse(endpoint)
        self.endpoint_origin = f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
        self.provider_id = provider_id
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._max_tokens = max_tokens
        self._thinking_level = thinking_level
        self._client = client
        self._retry_delay_seconds = retry_delay_seconds
        self.protocol = "gemini_generate_content"
        self.deployment_type = "external"
        self.data_boundary = "external_provider"

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        if request.max_tokens > self._max_tokens:
            raise ProviderOutputBudgetError(
                f"Requested output budget exceeds validated ceiling: {request.max_tokens}"
            )
        started_at = perf_counter()
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._post(request)
                payload = response.json()
                content, finish_reason = self._content_from(payload)
                usage = payload.get("usageMetadata", {})
                return ProviderResponse(
                    provider=self.provider_id,
                    model=self._model,
                    model_revision=payload.get("modelVersion"),
                    protocol=self.protocol,
                    deployment_type=self.deployment_type,
                    endpoint_origin=self.endpoint_origin,
                    data_boundary=self.data_boundary,
                    content=content,
                    latency_ms=int((perf_counter() - started_at) * 1000),
                    input_tokens=usage.get("promptTokenCount"),
                    output_tokens=usage.get("candidatesTokenCount"),
                    finish_reason=finish_reason,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == self._max_retries:
                    raise ProviderTimeoutError("Gemini request timed out") from exc
                await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code in {429, 500, 502, 503, 504} and attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                error_summary = self._error_summary(exc.response)
                raise ProviderResponseError(
                    f"Gemini returned HTTP {status_code}: {error_summary}"
                ) from exc
            except (ValueError, ProviderResponseError) as exc:
                if isinstance(exc, ProviderResponseError):
                    raise
                raise ProviderResponseError("Gemini response is invalid") from exc

        raise AssertionError("Retry loop always returns or raises")

    async def _post(self, request: ProviderRequest) -> httpx.Response:
        system_messages = [
            message.content for message in request.messages if message.role == "system"
        ]
        contents: list[dict[str, object]] = [
            {
                "role": "user" if message.role == "user" else "model",
                "parts": [{"text": message.content}],
            }
            for message in request.messages
            if message.role != "system"
        ]
        if not contents:
            raise ProviderResponseError("Gemini request has no user content")
        if request.document is not None:
            parts = contents[-1].get("parts")
            if not isinstance(parts, list):
                raise ProviderResponseError("Gemini request has invalid content parts")
            parts.append(
                {
                    "inlineData": {
                        "mimeType": request.document.media_type,
                        "data": base64.b64encode(request.document.content).decode("ascii"),
                    }
                }
            )
        generation_config: dict[str, object] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_tokens,
            "thinkingConfig": {"thinkingLevel": self._thinking_level},
        }
        if request.require_json_object:
            generation_config["responseMimeType"] = "application/json"
            if request.json_schema is not None:
                generation_config["responseJsonSchema"] = request.json_schema
        payload: dict[str, object] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_messages:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_messages)}]}
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self._api_key.get_secret_value(),
        }
        if self._client is not None:
            response = await self._client.post(
                self._endpoint,
                json=payload,
                headers=headers,
                timeout=self._timeout_seconds,
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(self._endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return response

    @staticmethod
    def _error_summary(response: httpx.Response) -> str:
        """Keep provider failures actionable without persisting a full response body."""
        try:
            payload = response.json()
        except ValueError:
            return "non-JSON provider error"
        if not isinstance(payload, dict):
            return "invalid provider error payload"
        error = payload.get("error")
        if not isinstance(error, dict):
            return "provider error payload missing details"
        message = error.get("message")
        if not isinstance(message, str) or not message.strip():
            return "provider error message missing"
        return " ".join(message.split())[:300]

    @staticmethod
    def _content_from(payload: object) -> tuple[str, str | None]:
        if not isinstance(payload, dict):
            raise ProviderResponseError("Gemini returned an invalid response")
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderResponseError("Gemini returned no candidates")
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise ProviderResponseError("Gemini returned an invalid candidate")
        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        text_parts: list[str] = []
        for part in parts or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
        text = "".join(text_parts).strip()
        if not text:
            raise ProviderResponseError("Gemini returned no generated text")
        finish_reason = candidate.get("finishReason")
        return text, finish_reason if isinstance(finish_reason, str) else None
