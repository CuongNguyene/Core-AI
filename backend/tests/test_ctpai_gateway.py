import json

import httpx
import pytest
from pydantic import SecretStr

from app.model_gateway.ctpai_gateway import CTPAIGatewayProvider
from app.model_gateway.errors import (
    ModelGatewayError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from app.model_gateway.prompts import ChatMessage
from app.model_gateway.providers import ProviderRequest


@pytest.mark.asyncio
async def test_ctpai_gateway_maps_messages_and_bearer_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/generate"
        assert request.headers["Authorization"] == "Bearer gateway-secret"
        body = json.loads(request.content)
        assert body == {
            "model": "QuantTrio/Qwen3.5-9B-AWQ",
            "prompt_system": "system instruction",
            "prompt_user": "user instruction",
            "temperature": 0.1,
            "max_tokens": 3072,
            "stream": False,
        }
        return httpx.Response(
            200,
            json={"model": "qwen-revision", "response": '{"required_skills": []}'},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CTPAIGatewayProvider(
            endpoint="http://gateway.local/api/v1/generate",
            api_key=SecretStr("gateway-secret"),
            model="QuantTrio/Qwen3.5-9B-AWQ",
            timeout_seconds=200,
            max_retries=0,
            client=client,
            temperature=0.1,
            max_tokens=8192,
        )
        response = await provider.complete(
            ProviderRequest(
                model="QuantTrio/Qwen3.5-9B-AWQ",
                messages=[
                    ChatMessage(role="system", content="system instruction"),
                    ChatMessage(role="user", content="user instruction"),
                ],
                require_json_object=True,
                max_tokens=3072,
            )
        )

    assert response.provider == "local-vllm"
    assert response.model_revision == "qwen-revision"
    assert response.content == '{"required_skills": []}'
    assert response.protocol == "ctpai_generate"
    assert response.deployment_type == "internal_gateway"
    assert response.endpoint_origin == "http://gateway.local"
    assert response.data_boundary == "internal_gateway"


@pytest.mark.asyncio
async def test_ctpai_gateway_retries_timeout_then_fails_safe() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CTPAIGatewayProvider(
            endpoint="http://gateway.local/api/v1/generate",
            api_key=SecretStr("gateway-secret"),
            model="qwen",
            timeout_seconds=1,
            max_retries=1,
            client=client,
        )
        with pytest.raises(ProviderTimeoutError):
            await provider.complete(
                ProviderRequest(model="qwen", messages=[ChatMessage(role="user", content="x")])
            )

    assert attempts == 2


@pytest.mark.asyncio
async def test_ctpai_gateway_rejects_response_without_generated_text() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "ok"}))
    ) as client:
        provider = CTPAIGatewayProvider(
            endpoint="http://gateway.local/api/v1/generate",
            api_key=SecretStr("gateway-secret"),
            model="qwen",
            timeout_seconds=1,
            max_retries=0,
            client=client,
        )
        with pytest.raises(ProviderResponseError):
            await provider.complete(
                ProviderRequest(model="qwen", messages=[ChatMessage(role="user", content="x")])
            )


@pytest.mark.asyncio
async def test_ctpai_gateway_logs_safe_metadata_for_http_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500, text="internal error"))
    ) as client:
        provider = CTPAIGatewayProvider(
            endpoint="http://gateway.local/api/v1/generate",
            api_key=SecretStr("gateway-secret"),
            model="qwen",
            timeout_seconds=1,
            max_retries=0,
            client=client,
        )
        with pytest.raises(ProviderResponseError):
            await provider.complete(
                ProviderRequest(model="qwen", messages=[ChatMessage(role="user", content="x")])
            )

    assert "ctpai_gateway_http_failure" in caplog.text
    assert "internal error" not in caplog.text


@pytest.mark.asyncio
async def test_ctpai_gateway_rejects_output_budget_above_ceiling_without_http_call() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"response": "{}"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CTPAIGatewayProvider(
            endpoint="http://gateway.local/api/v1/generate",
            api_key=SecretStr("gateway-secret"),
            model="qwen",
            timeout_seconds=1,
            max_retries=0,
            client=client,
            max_tokens=8192,
        )
        with pytest.raises(ModelGatewayError):
            await provider.complete(
                ProviderRequest(
                    model="qwen",
                    messages=[ChatMessage(role="user", content="x")],
                    max_tokens=8193,
                )
            )

    assert called is False


def test_ctpai_gateway_strips_completed_reasoning_block() -> None:
    payload = {"choices": [{"message": {"content": 'reasoning\n</think>\n{"status": "ok"}'}}]}

    assert CTPAIGatewayProvider._content_from(payload) == '{"status": "ok"}'
