import asyncio
import base64
from time import perf_counter
from typing import Any, cast
from urllib.parse import urlparse

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    OpenAIError,
    RateLimitError,
)
from pydantic import BaseModel, SecretStr, ValidationError

from app.model_gateway.errors import (
    ProviderOutputBudgetError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from app.model_gateway.providers import ProviderRequest, ProviderResponse


class OpenAIResponsesProvider:
    """OpenAI Responses API provider behind the internal ModelGateway contract."""

    provider_id = "openai"
    is_external = True

    def __init__(
        self,
        base_url: str,
        api_key: SecretStr,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        max_tokens: int,
        client: AsyncOpenAI | None = None,
        retry_delay_seconds: float = 0.05,
    ) -> None:
        parsed = urlparse(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path.rstrip("/") != "/v1"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OpenAI base URL must be an HTTPS API base ending in /v1")
        secret = api_key.get_secret_value()
        if not secret:
            raise ValueError("MODEL_API_KEY is required when MODEL_PROVIDER=openai")

        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._max_tokens = max_tokens
        self._retry_delay_seconds = retry_delay_seconds
        self._client = client or AsyncOpenAI(
            api_key=secret,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self.endpoint_origin = f"{parsed.scheme}://{parsed.netloc}"
        self.protocol = "openai_responses"
        self.deployment_type = "external"
        self.data_boundary = "external_provider"

    async def close(self) -> None:
        await self._client.close()

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        if request.max_tokens > self._max_tokens:
            raise ProviderOutputBudgetError(
                f"Requested output budget exceeds validated ceiling: {request.max_tokens}"
            )
        if request.require_json_object and request.response_model is None:
            raise ProviderResponseError("OpenAI structured output requires a registered schema")
        if request.document is not None and request.document.media_type != "application/pdf":
            raise ProviderResponseError("OpenAI document media type is not supported")

        instructions, input_messages = self._input_messages(request)
        started_at = perf_counter()
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._request(
                    request,
                    instructions=instructions,
                    input_messages=input_messages,
                )
                return self._provider_response(response, request=request, started_at=started_at)
            except (APITimeoutError, APIConnectionError) as exc:
                if attempt == self._max_retries:
                    raise ProviderTimeoutError(
                        "OpenAI request timed out or connection failed"
                    ) from exc
                await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
            except RateLimitError as exc:
                if attempt == self._max_retries:
                    raise ProviderResponseError("OpenAI rate limit was reached") from exc
                await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
            except APIStatusError as exc:
                if exc.status_code >= 500 and attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderResponseError(f"OpenAI returned HTTP {exc.status_code}") from exc
            except (ContentFilterFinishReasonError, LengthFinishReasonError) as exc:
                raise ProviderResponseError("OpenAI response was refused or incomplete") from exc
            except (OpenAIError, ValidationError, ValueError) as exc:
                raise ProviderResponseError("OpenAI response could not be validated") from exc

        raise AssertionError("Retry loop always returns or raises")

    async def _request(
        self,
        request: ProviderRequest,
        *,
        instructions: str | None,
        input_messages: list[dict[str, object]],
    ) -> object:
        common: dict[str, object] = {
            "model": request.model,
            "input": input_messages,
            "max_output_tokens": request.max_tokens,
            "store": False,
            "timeout": self._timeout_seconds,
        }
        if instructions is not None:
            common["instructions"] = instructions
        if request.require_json_object:
            response_model = request.response_model
            if response_model is None:
                raise ProviderResponseError("OpenAI structured output requires a registered schema")
            return await self._client.responses.parse(
                **cast(Any, common),
                text_format=response_model,
            )
        return await self._client.responses.create(**cast(Any, common))

    def _input_messages(
        self, request: ProviderRequest
    ) -> tuple[str | None, list[dict[str, object]]]:
        system_text = [message.content for message in request.messages if message.role == "system"]
        input_messages: list[dict[str, object]] = [
            {"role": message.role, "content": message.content}
            for message in request.messages
            if message.role != "system"
        ]
        if not input_messages:
            raise ProviderResponseError("OpenAI request has no non-system input")

        if request.document is not None:
            last_user_index = next(
                (
                    index
                    for index in range(len(input_messages) - 1, -1, -1)
                    if input_messages[index]["role"] == "user"
                ),
                None,
            )
            if last_user_index is None:
                raise ProviderResponseError("OpenAI document request has no user input")
            message = input_messages[last_user_index]
            content_text = message["content"]
            if not isinstance(content_text, str):
                raise ProviderResponseError("OpenAI user input content is invalid")
            document = request.document
            safe_filename = (document.filename or "document.pdf").replace("\\", "/").split("/")[-1]
            safe_filename = "".join(char for char in safe_filename if char.isprintable())[:128]
            if not safe_filename:
                safe_filename = "document.pdf"
            message["content"] = [
                {"type": "input_text", "text": content_text},
                {
                    "type": "input_file",
                    "filename": safe_filename,
                    "file_data": (
                        f"data:{document.media_type};base64,"
                        + base64.b64encode(document.content).decode("ascii")
                    ),
                },
            ]

        instructions = "\n\n".join(system_text) if system_text else None
        return instructions, input_messages

    def _provider_response(
        self,
        response: object,
        *,
        request: ProviderRequest,
        started_at: float,
    ) -> ProviderResponse:
        status = getattr(response, "status", None)
        if status == "incomplete":
            raise ProviderResponseError("OpenAI response was incomplete")
        if status != "completed":
            raise ProviderResponseError("OpenAI response did not complete successfully")

        output_items = getattr(response, "output", ())
        if any(
            getattr(content, "type", None) == "refusal"
            for item in output_items
            for content in getattr(item, "content", ())
        ):
            raise ProviderResponseError("OpenAI refused the request")

        if request.require_json_object:
            parsed = getattr(response, "output_parsed", None)
            if not isinstance(parsed, BaseModel):
                raise ProviderResponseError("OpenAI returned no parsed structured output")
            content = parsed.model_dump_json()
        else:
            output_text = getattr(response, "output_text", None)
            if not isinstance(output_text, str) or not output_text:
                raise ProviderResponseError("OpenAI returned no generated text")
            content = output_text

        usage = getattr(response, "usage", None)
        observed_model = getattr(response, "model", None)
        return ProviderResponse(
            provider="openai",
            model=request.model,
            model_revision=observed_model if isinstance(observed_model, str) else None,
            protocol="openai_responses",
            deployment_type="external",
            endpoint_origin=self.endpoint_origin,
            data_boundary="external_provider",
            content=content,
            latency_ms=int((perf_counter() - started_at) * 1000),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            finish_reason=status,
        )
