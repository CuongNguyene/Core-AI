import json

import httpx
import pytest
from pydantic import SecretStr

from app.model_gateway.errors import ProviderTimeoutError
from app.model_gateway.local_vllm import LocalVLLMProvider
from app.model_gateway.prompts import ChatMessage
from app.model_gateway.providers import ProviderRequest


@pytest.mark.asyncio
async def test_timeout_retries_once_then_returns_openai_compatible_response() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer local-secret"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 2048
        assert body["stream"] is False
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "model": "local-model-rev-1",
                "choices": [{"message": {"content": '{"skill":"Python"}'}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LocalVLLMProvider(
            base_url="http://vllm.local/v1",
            api_key=SecretStr("local-secret"),
            model="local-model",
            timeout_seconds=1,
            max_retries=1,
            client=client,
        )

        response = await provider.complete(
            ProviderRequest(
                model="local-model",
                messages=[ChatMessage(role="system", content="extract")],
                require_json_object=True,
            )
        )

    assert attempts == 2
    assert response.provider == "local-vllm"
    assert response.model == "local-model"
    assert response.model_revision == "local-model-rev-1"
    assert response.content == '{"skill":"Python"}'
    assert response.input_tokens == 12
    assert response.output_tokens == 4
    assert response.protocol == "openai_compatible"
    assert response.deployment_type == "local"
    assert response.endpoint_origin == "http://vllm.local"
    assert response.data_boundary == "local_runtime"


@pytest.mark.asyncio
async def test_timeout_after_retry_limit_raises_safe_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LocalVLLMProvider(
            base_url="http://vllm.local/v1",
            api_key=SecretStr("local-secret"),
            model="local-model",
            timeout_seconds=1,
            max_retries=1,
            client=client,
        )

        with pytest.raises(ProviderTimeoutError):
            await provider.complete(
                ProviderRequest(
                    model="local-model",
                    messages=[ChatMessage(role="system", content="extract")],
                )
            )


def test_local_vllm_strips_completed_reasoning_block() -> None:
    assert (
        LocalVLLMProvider._strip_completed_reasoning('internal reasoning\n</think>\n{"ok": true}')
        == '{"ok": true}'
    )


def test_local_vllm_strips_json_code_fence() -> None:
    assert LocalVLLMProvider._strip_completed_reasoning("```json\n{\"ok\": true}\n```") == (
        '{"ok": true}'
    )
