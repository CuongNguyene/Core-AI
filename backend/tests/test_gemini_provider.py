import json

import httpx
import pytest
from pydantic import SecretStr

from app.model_gateway.contracts import DocumentInput
from app.model_gateway.errors import ProviderResponseError, ProviderTimeoutError
from app.model_gateway.gemini import GeminiProvider
from app.model_gateway.prompts import ChatMessage
from app.model_gateway.providers import ProviderRequest


@pytest.mark.asyncio
async def test_gemini_provider_maps_structured_chat_completion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/gemini-3.5-flash-lite:generateContent")
        assert request.headers["x-goog-api-key"] == "gemini-secret"
        body = json.loads(request.content)
        assert body["systemInstruction"]["parts"][0]["text"] == "Return JSON."
        assert body["contents"][0]["parts"][0]["text"] == "Create a course."
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["maxOutputTokens"] == 8192
        assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "high"}
        assert body["generationConfig"]["responseJsonSchema"] == {"type": "object"}
        return httpx.Response(
            200,
            json={
                "candidates": [{
                    "content": {"parts": [{"text": '{"ok":true}'}]},
                    "finishReason": "STOP",
                }],
                "modelVersion": "gemini-3.5-flash-lite",
                "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiProvider(
            endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
            api_key=SecretStr("gemini-secret"),
            model="gemini-3.5-flash-lite",
            timeout_seconds=10,
            max_retries=0,
            client=client,
            provider_id="gemini",
        )
        response = await provider.complete(
            ProviderRequest(
                model="gemini-3.5-flash-lite",
                messages=[
                    ChatMessage(role="system", content="Return JSON."),
                    ChatMessage(role="user", content="Create a course."),
                ],
                require_json_object=True,
                max_tokens=8192,
                json_schema={"type": "object"},
            )
        )

    assert response.provider == "gemini"
    assert response.model == "gemini-3.5-flash-lite"
    assert response.content == '{"ok":true}'
    assert response.finish_reason == "STOP"
    assert response.input_tokens == 12
    assert response.output_tokens == 4
    assert response.protocol == "gemini_generate_content"
    assert response.deployment_type == "external"


@pytest.mark.asyncio
async def test_gemini_provider_retries_timeout_then_raises() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiProvider(
            endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
            api_key=SecretStr("gemini-secret"),
            model="gemini-3.5-flash-lite",
            timeout_seconds=1,
            max_retries=1,
            client=client,
        )
        with pytest.raises(ProviderTimeoutError):
            await provider.complete(
                ProviderRequest(
                    model="gemini-3.5-flash-lite",
                    messages=[ChatMessage(role="user", content="Create a course.")],
                )
            )

    assert attempts == 2


@pytest.mark.asyncio
async def test_gemini_provider_retries_temporary_service_failure() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiProvider(
            endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent",
            api_key=SecretStr("gemini-secret"),
            model="gemini-3.6-flash",
            timeout_seconds=1,
            max_retries=1,
            client=client,
        )
        response = await provider.complete(
            ProviderRequest(
                model="gemini-3.6-flash",
                messages=[ChatMessage(role="user", content="Create a course.")],
            )
        )

    assert attempts == 2
    assert response.content == "{}"


@pytest.mark.asyncio
async def test_gemini_provider_includes_safe_provider_error_message() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                503,
                request=request,
                json={"error": {"message": "Service is temporarily overloaded."}},
            )
        )
    ) as client:
        provider = GeminiProvider(
            endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent",
            api_key=SecretStr("gemini-secret"),
            model="gemini-3.6-flash",
            timeout_seconds=1,
            max_retries=0,
            client=client,
        )
        with pytest.raises(ProviderResponseError, match="Service is temporarily overloaded"):
            await provider.complete(
                ProviderRequest(
                    model="gemini-3.6-flash",
                    messages=[ChatMessage(role="user", content="Create a course.")],
                )
            )


@pytest.mark.asyncio
async def test_gemini_provider_sends_inline_document_part_without_textifying_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        parts = body["contents"][0]["parts"]
        assert parts[0]["text"] == "Extract the attached document."
        assert parts[1]["inlineData"]["mimeType"] == "application/pdf"
        assert parts[1]["inlineData"]["data"] == "JVBERi0xLjQ="
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiProvider(
            endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
            api_key=SecretStr("gemini-secret"),
            model="gemini-3.5-flash-lite",
            timeout_seconds=10,
            max_retries=0,
            client=client,
        )
        await provider.complete(
            ProviderRequest(
                model="gemini-3.5-flash-lite",
                messages=[ChatMessage(role="user", content="Extract the attached document.")],
                document=DocumentInput(media_type="application/pdf", content=b"%PDF-1.4"),
            )
        )
