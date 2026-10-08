"""OpenAI Responses API provider using strict Structured Outputs only."""

from __future__ import annotations

import asyncio
import re
from time import perf_counter
from typing import Protocol, cast

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from pydantic import SecretStr, ValidationError

from app.model_gateway.errors import (
    ProviderIncompleteError,
    ProviderRefusalError,
    ProviderResponseError,
    ProviderSchemaError,
    ProviderTimeoutError,
)
from app.model_gateway.providers import ProviderRequest, ProviderResponse

LUNA_MODEL = "gpt-6-luna"


class ResponsesEndpoint(Protocol):
    async def parse(self, **kwargs: object) -> object: ...


class OpenAIClient(Protocol):
    responses: ResponsesEndpoint


class OpenAITransportTimeoutError(ProviderTimeoutError):
    def __init__(self, *, attempt_count: int, diagnostics: list[dict[str, object]]) -> None:
        self.transport_diagnostics = diagnostics
        super().__init__("OpenAI Responses request timed out", attempt_count=attempt_count)


class OpenAITransportConnectionError(ProviderResponseError):
    def __init__(self, *, attempt_count: int, diagnostics: list[dict[str, object]]) -> None:
        self.transport_diagnostics = diagnostics
        super().__init__(
            "OpenAI Responses connection failed",
            attempt_count=attempt_count,
        )


class OpenAIResponsesProvider:
    """External provider implementation; composition remains owned by eval code."""

    provider_id = "openai"
    is_external = True
    protocol = "openai_responses_json_schema"
    deployment_type = "external"
    endpoint_origin = "https://api.openai.com"
    data_boundary = "external_provider"

    def __init__(
        self,
        *,
        api_key: SecretStr,
        timeout_seconds: float,
        max_retries: int,
        client: OpenAIClient | None = None,
        retry_delay_seconds: float = 0.05,
    ) -> None:
        if not api_key.get_secret_value():
            raise ValueError("OpenAI API key is required")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._client = client

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        if request.model != LUNA_MODEL:
            raise ProviderResponseError("OpenAI Luna adapter requires model gpt-6-luna")
        if not request.require_json_object or request.response_model is None:
            raise ProviderSchemaError("OpenAI Responses adapter requires a Pydantic response model")

        payload = self._request_payload(request)
        started = perf_counter()
        response: object | None = None
        provider_attempt_count = 0
        transport_diagnostics: list[dict[str, object]] = []
        for attempt in range(self._max_retries + 1):
            provider_attempt_count = attempt + 1
            try:
                response = await self._client_instance().responses.parse(**payload)
                break
            except APITimeoutError as exc:
                transport_diagnostics.append(_transport_diagnostic(exc, provider_attempt_count))
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise OpenAITransportTimeoutError(
                    attempt_count=provider_attempt_count, diagnostics=transport_diagnostics
                ) from exc
            except APIConnectionError as exc:
                transport_diagnostics.append(_transport_diagnostic(exc, provider_attempt_count))
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise OpenAITransportConnectionError(
                    attempt_count=provider_attempt_count, diagnostics=transport_diagnostics
                ) from exc
            except (RateLimitError, InternalServerError) as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderResponseError(
                    "OpenAI Responses transient failure exhausted retries",
                    attempt_count=provider_attempt_count,
                ) from exc
            except APIStatusError as exc:
                if (
                    exc.status_code == 429 or exc.status_code >= 500
                ) and attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                if exc.status_code == 400:
                    raise ProviderSchemaError(
                        "OpenAI rejected the strict structured-output request",
                        attempt_count=provider_attempt_count,
                    ) from exc
                raise ProviderResponseError(
                    f"OpenAI Responses request failed with HTTP {exc.status_code}",
                    attempt_count=provider_attempt_count,
                ) from exc
            except (ValidationError, ValueError) as exc:
                raise ProviderSchemaError(
                    "OpenAI Responses output did not satisfy the requested Pydantic schema",
                    attempt_count=provider_attempt_count,
                ) from exc

        if response is None:
            raise AssertionError("OpenAI retry loop must return or raise")

        status = _string_attr(response, "status")
        if status == "incomplete":
            raise ProviderIncompleteError(
                "OpenAI Responses returned an incomplete response",
                provider_response_id=_string_attr(response, "id") or None,
                observed_model=_string_attr(response, "model") or None,
                latency_ms=max(0, int((perf_counter() - started) * 1000)),
                attempt_count=provider_attempt_count,
            )
        if status != "completed":
            raise ProviderResponseError(
                "OpenAI Responses returned an unsuccessful status",
                attempt_count=provider_attempt_count,
            )
        if _contains_refusal(_attr(response, "output")):
            raise ProviderRefusalError(
                "OpenAI Responses refused the request",
                provider_response_id=_string_attr(response, "id") or None,
                observed_model=_string_attr(response, "model") or None,
                latency_ms=max(0, int((perf_counter() - started) * 1000)),
                attempt_count=provider_attempt_count,
            )

        parsed = _attr(response, "output_parsed")
        if not isinstance(parsed, request.response_model):
            raise ProviderSchemaError(
                "OpenAI Responses did not return the requested parsed model",
                provider_response_id=_string_attr(response, "id") or None,
                observed_model=_string_attr(response, "model") or None,
                latency_ms=max(0, int((perf_counter() - started) * 1000)),
                attempt_count=provider_attempt_count,
            )

        observed_model = _string_attr(response, "model")
        if not observed_model:
            raise ProviderResponseError(
                "OpenAI Responses omitted observed model identity",
                attempt_count=provider_attempt_count,
            )

        usage = _attr(response, "usage")
        input_details = _attr(usage, "input_tokens_details")
        return ProviderResponse(
            provider=self.provider_id,
            model=observed_model,
            requested_model=request.model,
            provider_response_id=_string_attr(response, "id") or None,
            content="",
            structured_output=parsed,
            protocol=self.protocol,
            deployment_type=self.deployment_type,
            endpoint_origin=self.endpoint_origin,
            data_boundary=self.data_boundary,
            finish_reason=status,
            latency_ms=max(0, int((perf_counter() - started) * 1000)),
            provider_attempt_count=provider_attempt_count,
            input_tokens=_int_attr(usage, "input_tokens"),
            output_tokens=_int_attr(usage, "output_tokens"),
            total_tokens=_int_attr(usage, "total_tokens"),
            cached_tokens=_int_attr(input_details, "cached_tokens"),
        )

    def _client_instance(self) -> OpenAIClient:
        if self._client is None:
            client = AsyncOpenAI(
                api_key=self._api_key.get_secret_value(),
                timeout=self._timeout_seconds,
                max_retries=0,
            )
            self._client = cast(OpenAIClient, client)
        return self._client

    @staticmethod
    def _request_payload(request: ProviderRequest) -> dict[str, object]:
        if request.response_model is None:
            raise ProviderSchemaError("OpenAI Responses adapter requires a Pydantic response model")
        return {
            "model": request.model,
            "input": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "text_format": request.response_model,
            "max_output_tokens": request.max_tokens,
            "temperature": request.temperature,
        }


def model_identity_matches(requested_model: str, observed_model: str) -> bool:
    """Accept only the exact ID or the approved YYYY-MM-DD snapshot form."""
    if observed_model == requested_model:
        return True
    return (
        re.fullmatch(re.escape(requested_model) + r"-\d{4}-\d{2}-\d{2}", observed_model) is not None
    )


def _attr(value: object | None, name: str) -> object | None:
    return getattr(value, name, None) if value is not None else None


def _string_attr(value: object, name: str) -> str:
    candidate = _attr(value, name)
    return candidate if isinstance(candidate, str) else ""


def _int_attr(value: object | None, name: str) -> int | None:
    candidate = _attr(value, name)
    return candidate if isinstance(candidate, int) and not isinstance(candidate, bool) else None


def _contains_refusal(output: object | None) -> bool:
    if not isinstance(output, (list, tuple)):
        return False
    for item in output:
        content = _attr(item, "content")
        if not isinstance(content, (list, tuple)):
            continue
        if any(_string_attr(part, "type") == "refusal" for part in content):
            return True
    return False


def _transport_diagnostic(error: Exception, attempt: int) -> dict[str, object]:
    """Return exception class metadata only; never persist messages or reprs."""
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__

    names = [type(item).__name__ for item in chain]
    transport_names = names[1:]
    phase = "unknown"
    for name in transport_names:
        if name == "gaierror":
            phase = "dns"
            break
        if name.startswith("SSL"):
            phase = "tls"
            break
        if name in {"ProxyError", "ProxyConnectionError"}:
            phase = "proxy"
            break
        if name == "ConnectTimeout":
            phase = "connect"
            break
        if name == "ReadTimeout":
            phase = "read"
            break
        if name == "WriteTimeout":
            phase = "write"
            break
        if name == "PoolTimeout":
            phase = "pool"
            break
        if name in {"ConnectionResetError", "BrokenPipeError"}:
            phase = "connection_reset" if name == "ConnectionResetError" else "write"
            break
        if name == "ConnectError":
            phase = "connect"

    transport_error_class = next(
        (
            name
            for name in reversed(transport_names)
            if name.startswith("SSL")
            or name
            in {
                "ConnectTimeout",
                "ReadTimeout",
                "WriteTimeout",
                "PoolTimeout",
                "ConnectError",
                "ProxyError",
                "ProxyConnectionError",
                "gaierror",
                "ConnectionResetError",
                "BrokenPipeError",
            }
        ),
        transport_names[-1] if transport_names else names[0],
    )
    return {
        "error_class": names[0],
        "transport_error_class": transport_error_class,
        "transport_phase": phase,
        "attempt": attempt,
        "cause_chain": names,
    }
