import asyncio
import logging
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

logger = logging.getLogger(__name__)


class CTPAIGatewayProvider:
    """Provider adapter for the organization-controlled CTPAI /generate API."""

    provider_id = "local-vllm"
    is_external = False

    def __init__(
        self,
        endpoint: str,
        api_key: SecretStr,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        client: httpx.AsyncClient | None = None,
        retry_delay_seconds: float = 0.05,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        parsed_endpoint = urlparse(self._endpoint)
        self.endpoint_origin = f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
        self.protocol = "ctpai_generate"
        self.deployment_type = "internal_gateway"
        self.data_boundary = "internal_gateway"
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client = client
        self._retry_delay_seconds = retry_delay_seconds
        self._temperature = temperature
        self._max_tokens = max_tokens

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
                content = self._content_from(payload)
                return ProviderResponse(
                    provider=self.provider_id,
                    model=self._model,
                    model_revision=payload.get("model") if isinstance(payload, dict) else None,
                    protocol=self.protocol,
                    deployment_type=self.deployment_type,
                    endpoint_origin=self.endpoint_origin,
                    data_boundary=self.data_boundary,
                    content=content,
                    latency_ms=int((perf_counter() - started_at) * 1000),
                    input_tokens=self._usage_value(payload, "prompt_tokens"),
                    output_tokens=self._usage_value(payload, "completion_tokens"),
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == self._max_retries:
                    raise ProviderTimeoutError("CTPAI Gateway request timed out") from exc
                await asyncio.sleep(self._retry_delay_seconds)
            except (httpx.HTTPStatusError, ValueError, ProviderResponseError) as exc:
                if isinstance(exc, ProviderResponseError):
                    raise
                if isinstance(exc, httpx.HTTPStatusError):
                    self._log_http_failure(exc.response)
                raise ProviderResponseError("CTPAI Gateway response is invalid") from exc

        raise AssertionError("Retry loop always returns or raises")

    async def _post(self, request: ProviderRequest) -> httpx.Response:
        system_messages = [
            message.content for message in request.messages if message.role == "system"
        ]
        user_messages = [message.content for message in request.messages if message.role == "user"]
        payload = {
            "model": request.model,
            "prompt_system": "\n\n".join(system_messages),
            "prompt_user": "\n\n".join(user_messages),
            "temperature": self._temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        api_key = self._api_key.get_secret_value()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if self._client is not None:
            response = await self._client.post(
                self._endpoint, json=payload, headers=headers, timeout=self._timeout_seconds
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(self._endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return response

    @staticmethod
    def _content_from(payload: object) -> str:
        if not isinstance(payload, dict):
            raise ProviderResponseError("CTPAI Gateway returned an invalid response")
        candidates: list[object] = [
            payload.get("response"),
            payload.get("text"),
            payload.get("generated_text"),
            payload.get("output"),
        ]
        choices = payload.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            choice = choices[0]
            candidates.extend(
                [
                    choice.get("text"),
                    (choice.get("message") or {}).get("content")
                    if isinstance(choice.get("message"), dict)
                    else None,
                ]
            )
        for candidate in candidates:
            if isinstance(candidate, str) and candidate:
                return CTPAIGatewayProvider._strip_completed_reasoning(candidate)
        CTPAIGatewayProvider._log_missing_content(payload)
        raise ProviderResponseError("CTPAI Gateway returned no generated text")

    @staticmethod
    def _log_missing_content(payload: object) -> None:
        if not isinstance(payload, dict):
            logger.warning(
                "ctpai_gateway_invalid_payload", extra={"payload_type": type(payload).__name__}
            )
            return
        choices = payload.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else None
        message = first.get("message") if isinstance(first, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        logger.warning(
            "ctpai_gateway_missing_generated_text",
            extra={
                "response_keys": sorted(payload.keys()),
                "choices_count": len(choices) if isinstance(choices, list) else None,
                "finish_reason": first.get("finish_reason") if isinstance(first, dict) else None,
                "stop_reason": first.get("stop_reason") if isinstance(first, dict) else None,
                "message_keys": sorted(message.keys()) if isinstance(message, dict) else None,
                "content_type": type(content).__name__,
                "content_length": len(content) if isinstance(content, str) else None,
            },
        )

    @staticmethod
    def _log_http_failure(response: httpx.Response) -> None:
        logger.warning(
            "ctpai_gateway_http_failure status=%s response_content_type=%s "
            "response_length=%s request_content_length=%s",
            response.status_code,
            response.headers.get("content-type"),
            len(response.content),
            response.request.headers.get("content-length"),
        )

    @staticmethod
    def _strip_completed_reasoning(content: str) -> str:
        """Discard Qwen reasoning only when a completed delimiter precedes output."""
        marker = "</think>"
        if marker not in content:
            return content
        final_content = content.rsplit(marker, 1)[1].strip()
        return final_content or content

    @staticmethod
    def _usage_value(payload: object, key: str) -> int | None:
        if not isinstance(payload, dict) or not isinstance(payload.get("usage"), dict):
            return None
        value = payload["usage"].get(key)
        return value if isinstance(value, int) and value >= 0 else None
