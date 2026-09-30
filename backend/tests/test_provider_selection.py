from pydantic import SecretStr

from app.main import _build_model_provider
from app.model_gateway.ctpai_gateway import CTPAIGatewayProvider
from app.model_gateway.gemini import GeminiProvider
from app.model_gateway.local_vllm import LocalVLLMProvider


def test_vilao_openai_base_url_selects_chat_completions_provider() -> None:
    provider = _build_model_provider(
        provider_id="vilao-external",
        endpoint="https://api.vilao.ai/v1",
        api_key=SecretStr("token"),
        model="claude-sonnet-5",
        timeout_seconds=10,
        max_retries=1,
        max_tokens=2048,
    )

    assert isinstance(provider, LocalVLLMProvider)
    assert provider.provider_id == "vilao-external"
    assert provider.is_external is True
    assert provider.protocol == "openai_compatible"
    assert provider.deployment_type == "external"
    assert provider.endpoint_origin == "https://api.vilao.ai"
    assert provider.data_boundary == "external_provider"


def test_vilao_endpoint_cannot_hide_behind_local_provider_id() -> None:
    provider = _build_model_provider(
        provider_id="local-vllm",
        endpoint="https://api.vilao.ai/v1",
        api_key=SecretStr("token"),
        model="claude-sonnet-5",
        timeout_seconds=10,
        max_retries=1,
        max_tokens=2048,
    )

    assert provider.provider_id == "vilao"
    assert provider.is_external is True
    assert provider.data_boundary == "external_provider"


def test_ctpai_generate_endpoint_selects_ctpai_provider() -> None:
    provider = _build_model_provider(
        provider_id="local-vllm",
        endpoint="https://service.ctpai.vn/vllm_pai/generate",
        api_key=SecretStr("token"),
        model="approved-model",
        timeout_seconds=10,
        max_retries=1,
        max_tokens=2048,
    )

    assert isinstance(provider, CTPAIGatewayProvider)
    assert provider.provider_id == "local-vllm"
    assert provider.is_external is False


def test_local_openai_compatible_endpoint_is_classified_as_local() -> None:
    provider = _build_model_provider(
        provider_id="local-vllm",
        endpoint="http://pai-vllm:8001/v1",
        api_key=SecretStr("token"),
        model="approved-model",
        timeout_seconds=10,
        max_retries=1,
        max_tokens=2048,
    )

    assert provider.provider_id == "local-vllm"
    assert provider.is_external is False


def test_gemini_generate_content_endpoint_selects_gemini_provider() -> None:
    provider = _build_model_provider(
        provider_id="gemini",
        endpoint=(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-3.5-flash-lite:generateContent"
        ),
        api_key=SecretStr("token"),
        model="gemini-3.5-flash-lite",
        timeout_seconds=10,
        max_retries=1,
        max_tokens=8192,
    )

    assert isinstance(provider, GeminiProvider)
    assert provider.provider_id == "gemini"
    assert provider.is_external is True
