import pytest
from pydantic import ValidationError

from app.shared.config import Settings


def test_settings_exposes_separate_redis_urls_and_base_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_CACHE_URL", raising=False)
    monkeypatch.delenv("REDIS_QUEUE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.redis_cache_url == "redis://localhost:6379/0"
    assert settings.redis_queue_url == "redis://localhost:6379/1"
    assert settings.pai_base_path == ""


def test_integration_settings_reject_missing_jwt_signing_key() -> None:
    with pytest.raises(ValidationError, match="jwt_signing_key"):
        Settings(_env_file=None, app_env="integration", jwt_signing_key="")


def test_integration_settings_reject_missing_pai_api_key() -> None:
    with pytest.raises(ValidationError, match="integration_api_key"):
        Settings(
            _env_file=None,
            app_env="integration",
            jwt_signing_key="jwt-test-key",
            integration_api_key="",
        )


def test_production_settings_require_clamav_document_scanner() -> None:
    with pytest.raises(ValidationError, match="document_scanner=clamav"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_signing_key="jwt-test-key",
            integration_api_key="integration-test-key",
        )

    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_signing_key="jwt-test-key",
        integration_api_key="integration-test-key",
        document_scanner="clamav",
    )
    assert settings.document_scanner == "clamav"


def test_settings_rejects_gateway_output_limit_above_validated_ceiling() -> None:
    settings = Settings(_env_file=None)

    assert settings.vllm_max_tokens == 131072
    assert settings.course_generation_max_tokens == 65536
    assert settings.gemini_thinking_level == "high"
    assert settings.cv_jd_extraction_max_tokens == 8192


def test_settings_rejects_course_generation_budget_above_64k() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, course_generation_max_tokens=65537)


def test_course_generation_quality_validation_is_enabled_by_default_and_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Settings(_env_file=None).course_generation_quality_validation_enabled is True

    monkeypatch.setenv("COURSE_GENERATION_QUALITY_VALIDATION_ENABLED", "false")
    assert Settings(_env_file=None).course_generation_quality_validation_enabled is False


def test_settings_rejects_unknown_gemini_thinking_level() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gemini_thinking_level="extreme")


def test_settings_accepts_canonical_model_environment_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "vilao-external")
    monkeypatch.setenv("MODEL_BASE_URL", "https://api.vilao.ai/v1")
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-5")

    settings = Settings(_env_file=None)

    assert settings.model_provider == "vilao-external"
    assert str(settings.vllm_base_url) == "https://api.vilao.ai/v1"
    assert settings.vllm_model == "claude-sonnet-5"


def test_settings_rejects_extraction_budget_above_gateway_ceiling() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, vllm_max_tokens=131072, cv_jd_extraction_max_tokens=131073)


def test_openedx_provider_is_optional_and_bounded() -> None:
    settings = Settings(_env_file=None)

    assert settings.openedx_base_url == ""
    assert settings.openedx_access_token.get_secret_value() == ""
    assert settings.openedx_timeout_seconds == 10.0
    assert settings.openedx_max_pages == 2
    assert settings.openedx_page_size == 50
