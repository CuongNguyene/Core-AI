import base64
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, ConfigDict, SecretStr

from app.model_gateway.contracts import DocumentInput
from app.model_gateway.errors import ProviderResponseError, ProviderTimeoutError
from app.model_gateway.openai_responses import OpenAIResponsesProvider
from app.model_gateway.prompts import ChatMessage
from app.model_gateway.providers import ProviderRequest


class FakeResponses:
    def __init__(self, results: list[object | Exception]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeClient:
    def __init__(self, results: list[object | Exception]) -> None:
        self.responses = FakeResponses(results)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def make_response(
    *,
    output_text: str = "plain response",
    model: str = "gpt-6-luna-2026-10-01",
    status: str = "completed",
    output: list[object] | None = None,
    output_parsed: BaseModel | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id="resp_test_123",
        model=model,
        status=status,
        output_text=output_text,
        output=output or [],
        output_parsed=output_parsed,
        incomplete_details=None,
        usage=SimpleNamespace(input_tokens=23, output_tokens=7),
    )


def make_provider(client: FakeClient, *, max_retries: int = 0) -> OpenAIResponsesProvider:
    return OpenAIResponsesProvider(
        base_url="https://api.openai.com/v1",
        api_key=SecretStr("test-secret"),
        model="gpt-6-luna",
        timeout_seconds=4,
        max_retries=max_retries,
        max_tokens=8192,
        retry_delay_seconds=0,
        client=client,  # type: ignore[arg-type]
    )


class SampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    value: str


@pytest.mark.asyncio
async def test_structured_request_uses_responses_strict_json_schema_and_requested_model() -> None:
    client = FakeClient(
        [make_response(output_text='{"value":"ok"}', output_parsed=SampleOutput(value="ok"))]
    )
    provider = make_provider(client)

    result = await provider.complete(
        ProviderRequest(
            model="gpt-6-luna",
            messages=[
                ChatMessage(role="system", content="Trusted instructions."),
                ChatMessage(role="user", content="Source data."),
            ],
            require_json_object=True,
            json_schema=SampleOutput.model_json_schema(),
            response_model=SampleOutput,
            max_tokens=128,
            temperature=0.2,
        )
    )

    call = client.responses.calls[0]
    assert call["model"] == "gpt-6-luna"
    assert call["instructions"] == "Trusted instructions."
    assert call["input"] == [
        {"role": "user", "content": "Source data."},
    ]
    assert call["text_format"] is SampleOutput
    assert call["max_output_tokens"] == 128
    assert "temperature" not in call
    assert call["store"] is False
    assert result.content == '{"value":"ok"}'
    assert result.provider == "openai"
    assert result.model == "gpt-6-luna"
    assert result.model_revision == "gpt-6-luna-2026-10-01"
    assert result.protocol == "openai_responses"
    assert result.deployment_type == "external"
    assert result.data_boundary == "external_provider"
    assert result.input_tokens == 23
    assert result.output_tokens == 7


@pytest.mark.asyncio
async def test_installed_sdk_emits_strict_json_schema_on_responses_endpoint() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        body = json.loads(request.content)
        captured["body"] = body
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "resp_sdk_test",
                "created_at": 1,
                "model": "gpt-6-luna-2026-10-01",
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": True,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "msg_sdk_test",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"value":"ok"}',
                                "annotations": [],
                                "logprobs": [],
                            }
                        ],
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        sdk_client = AsyncOpenAI(
            api_key="test-secret",
            base_url="https://api.openai.com/v1",
            http_client=http_client,
            max_retries=0,
        )
        provider = make_provider(sdk_client)  # type: ignore[arg-type]
        result = await provider.complete(
            ProviderRequest(
                model="gpt-6-luna",
                messages=[ChatMessage(role="user", content="return value")],
                require_json_object=True,
                json_schema=SampleOutput.model_json_schema(),
                response_model=SampleOutput,
            )
        )

    assert captured["path"] == "/v1/responses"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "gpt-6-luna"
    assert body["store"] is False
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    assert body["text"]["format"]["schema"] == SampleOutput.model_json_schema()
    assert result.content == '{"value":"ok"}'


@pytest.mark.asyncio
async def test_text_request_does_not_enable_json_mode() -> None:
    client = FakeClient([make_response(output_text="hello")])
    provider = make_provider(client)

    result = await provider.complete(
        ProviderRequest(
            model="gpt-6-luna",
            messages=[ChatMessage(role="user", content="hello?")],
        )
    )

    assert "text" not in client.responses.calls[0]
    assert result.content == "hello"


@pytest.mark.asyncio
async def test_structured_request_requires_schema_before_provider_call() -> None:
    client = FakeClient([make_response()])
    provider = make_provider(client)

    with pytest.raises(ProviderResponseError, match="schema"):
        await provider.complete(
            ProviderRequest(
                model="gpt-6-luna",
                messages=[ChatMessage(role="user", content="extract")],
                require_json_object=True,
            )
        )

    assert client.responses.calls == []


@pytest.mark.asyncio
async def test_refusal_is_not_returned_as_semantic_content() -> None:
    refusal = SimpleNamespace(
        type="message",
        content=[SimpleNamespace(type="refusal", refusal="sensitive content")],
    )
    provider = make_provider(FakeClient([make_response(output_text="", output=[refusal])]))

    with pytest.raises(ProviderResponseError, match="refused") as exc_info:
        await provider.complete(
            ProviderRequest(
                model="gpt-6-luna",
                messages=[ChatMessage(role="user", content="request")],
            )
        )

    assert "sensitive content" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_incomplete_response_fails_closed() -> None:
    response = make_response(output_text='{"partial":', status="incomplete")
    response.incomplete_details = SimpleNamespace(reason="max_output_tokens")
    provider = make_provider(FakeClient([response]))

    with pytest.raises(ProviderResponseError, match="incomplete"):
        await provider.complete(
            ProviderRequest(
                model="gpt-6-luna",
                messages=[ChatMessage(role="user", content="request")],
            )
        )


@pytest.mark.asyncio
async def test_timeout_and_rate_limit_are_retried_with_identical_request() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    rate_response = httpx.Response(429, request=request)
    client = FakeClient(
        [
            APITimeoutError(request=request),
            RateLimitError("secret provider detail", response=rate_response, body=None),
            make_response(output_text="done"),
        ]
    )
    provider = make_provider(client, max_retries=2)
    request_body = ProviderRequest(
        model="gpt-6-luna",
        messages=[ChatMessage(role="user", content="same input")],
    )

    response = await provider.complete(request_body)

    assert response.content == "done"
    assert len(client.responses.calls) == 3
    assert client.responses.calls[0] == client.responses.calls[1] == client.responses.calls[2]


@pytest.mark.asyncio
async def test_retry_exhaustion_is_sanitized_and_does_not_echo_provider_details() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    client = FakeClient([APIConnectionError(message="secret-detail", request=request)])
    provider = make_provider(client, max_retries=0)

    with pytest.raises(ProviderTimeoutError) as exc_info:
        await provider.complete(
            ProviderRequest(
                model="gpt-6-luna",
                messages=[ChatMessage(role="user", content="private source text")],
            )
        )

    assert "secret-detail" not in str(exc_info.value)
    assert "private source text" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_pdf_document_is_inline_responses_input_file_and_client_closes() -> None:
    client = FakeClient([make_response(output_text="{}")])
    provider = make_provider(client)
    document_bytes = b"%PDF-1.4 synthetic"

    await provider.complete(
        ProviderRequest(
            model="gpt-6-luna",
            messages=[ChatMessage(role="user", content="Extract this document.")],
            document=DocumentInput(
                media_type="application/pdf",
                content=document_bytes,
                filename="synthetic.pdf",
            ),
        )
    )

    input_message = client.responses.calls[0]["input"][0]
    assert isinstance(input_message, dict)
    assert input_message["content"] == [
        {"type": "input_text", "text": "Extract this document."},
        {
            "type": "input_file",
            "filename": "synthetic.pdf",
            "file_data": (
                "data:application/pdf;base64," + base64.b64encode(document_bytes).decode("ascii")
            ),
        },
    ]
    await provider.close()
    assert client.closed is True


@pytest.mark.asyncio
async def test_unsupported_document_type_fails_without_provider_call() -> None:
    client = FakeClient([make_response()])
    provider = make_provider(client)

    with pytest.raises(ProviderResponseError, match="media type"):
        await provider.complete(
            ProviderRequest(
                model="gpt-6-luna",
                messages=[ChatMessage(role="user", content="extract")],
                document=DocumentInput(media_type="application/msword", content=b"file"),
            )
        )

    assert client.responses.calls == []
