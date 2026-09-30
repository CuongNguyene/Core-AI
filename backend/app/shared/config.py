from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "PAI Platform"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, gt=0, le=65535)
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://pai:pai@localhost:5432/pai"
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_url: str = "redis://localhost:6379/0"
    redis_queue_url: str = "redis://localhost:6379/1"
    redis_password: SecretStr = SecretStr("")

    pai_base_path: str = ""
    jwt_signing_key: SecretStr = SecretStr("")
    jwt_issuer: str = "pai-platform"
    jwt_audience: str = "pai-platform"
    jwt_access_token_minutes: int = Field(default=30, gt=0, le=1440)
    pai_bootstrap_admin_password: SecretStr = SecretStr("")
    integration_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "PAI_INTEGRATION_API_KEY", "INTEGRATION_API_KEY", "integration_api_key"
        ),
    )
    actor_context_public_keys_json: str = "{}"
    lms_identity_context_url: str = "http://lms-backend:3000/api/organization/users"
    lms_identity_context_token: SecretStr = SecretStr("")

    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_access_key: str = "minio"
    object_storage_secret_key: SecretStr = SecretStr("miniosecret")
    object_storage_bucket: str = "pai-documents"
    object_storage_secure: bool = False
    document_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    document_retention_days: int = Field(default=30, gt=0)
    document_scanner: Literal["development", "clamav"] = "development"
    clamav_host: str = "localhost"
    clamav_port: int = Field(default=3310, gt=0, le=65535)
    clamav_timeout_seconds: float = Field(default=10.0, gt=0, le=120)

    model_provider: str = Field(
        default="local-vllm",
        validation_alias=AliasChoices("MODEL_PROVIDER", "model_provider"),
    )
    vllm_base_url: str = Field(
        default="http://localhost:8001/v1",
        validation_alias=AliasChoices("MODEL_BASE_URL", "VLLM_BASE_URL", "vllm_base_url"),
    )
    vllm_api_key: SecretStr = Field(
        default=SecretStr("local-token"),
        validation_alias=AliasChoices("MODEL_API_KEY", "VLLM_API_KEY", "vllm_api_key"),
    )
    vllm_model: str = Field(
        default="replace-with-approved-model",
        validation_alias=AliasChoices("MODEL_NAME", "VLLM_MODEL", "vllm_model"),
    )
    gemini_thinking_level: Literal["minimal", "low", "medium", "high"] = Field(
        default="high",
        validation_alias=AliasChoices("GEMINI_THINKING_LEVEL", "gemini_thinking_level"),
    )
    vllm_timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        validation_alias=AliasChoices(
            "MODEL_TIMEOUT_SECONDS", "VLLM_TIMEOUT_SECONDS", "vllm_timeout_seconds"
        ),
    )
    generation_timeout_seconds: float = Field(
        default=660.0,
        gt=0,
        validation_alias=AliasChoices("GENERATION_TIMEOUT_SECONDS", "generation_timeout_seconds"),
    )
    vllm_max_tokens: int = Field(
        default=131072,
        gt=0,
        le=131072,
        validation_alias=AliasChoices("MODEL_MAX_TOKENS", "VLLM_MAX_TOKENS", "vllm_max_tokens"),
    )
    course_generation_max_tokens: int = Field(
        default=65536,
        gt=0,
        le=65536,
        validation_alias=AliasChoices(
            "COURSE_GENERATION_MAX_TOKENS", "course_generation_max_tokens"
        ),
    )
    course_generation_quality_validation_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "COURSE_GENERATION_QUALITY_VALIDATION_ENABLED",
            "course_generation_quality_validation_enabled",
        ),
    )
    cv_jd_extraction_max_tokens: int = Field(default=8192, gt=0, le=131072)
    evidence_graph_runtime_enabled: bool = False
    cv_extraction_pipeline: Literal["legacy_v2", "two_stage"] = Field(
        default="legacy_v2",
        validation_alias=AliasChoices("CV_EXTRACTION_PIPELINE", "cv_extraction_pipeline"),
    )
    cv_two_stage_capability_mode: Literal["bounded", "discovery"] = Field(
        default="bounded",
        validation_alias=AliasChoices(
            "CV_TWO_STAGE_CAPABILITY_MODE", "cv_two_stage_capability_mode"
        ),
    )
    jd_extraction_mode: Literal["legacy_full", "requirement_v2"] = Field(
        default="legacy_full",
        validation_alias=AliasChoices("JD_EXTRACTION_MODE", "jd_extraction_mode"),
    )
    extraction_forensics_enabled: bool = False
    extraction_forensics_dir: str = "/tmp/pai-extraction-forensics"
    vllm_max_retries: int = Field(
        default=1,
        ge=0,
        le=3,
        validation_alias=AliasChoices("MODEL_MAX_RETRIES", "VLLM_MAX_RETRIES", "vllm_max_retries"),
    )
    model_retry_base_delay_seconds: float = Field(
        default=1.0,
        gt=0,
        le=30,
        validation_alias=AliasChoices(
            "MODEL_RETRY_BASE_DELAY_SECONDS", "model_retry_base_delay_seconds"
        ),
    )
    extraction_job_stale_seconds: int = Field(
        default=900,
        ge=60,
        le=86400,
        validation_alias=AliasChoices(
            "EXTRACTION_JOB_STALE_SECONDS", "extraction_job_stale_seconds"
        ),
    )
    extraction_job_heartbeat_seconds: float = Field(
        default=15.0,
        gt=0,
        le=300,
        validation_alias=AliasChoices(
            "EXTRACTION_JOB_HEARTBEAT_SECONDS", "extraction_job_heartbeat_seconds"
        ),
    )
    structured_output_repair_retries: int = Field(default=1, ge=0, le=1)
    privacy_policy_version: str = "privacy-v1"

    external_ai_enabled: bool = False
    external_restricted_data_approved: bool = False
    external_ai_provider: str = ""
    external_ai_api_key: SecretStr = SecretStr("")
    pii_external_default_deny: bool = True

    @model_validator(mode="after")
    def validate_integration_secrets(self) -> "Settings":
        if self.app_env in {"integration", "production"}:
            if not self.jwt_signing_key.get_secret_value():
                raise ValueError("jwt_signing_key is required outside development")
            if not self.integration_api_key.get_secret_value():
                raise ValueError("integration_api_key is required outside development")
            if self.pai_base_path and not self.pai_base_path.startswith("/"):
                raise ValueError("pai_base_path must start with /")
        if self.app_env == "production" and self.document_scanner != "clamav":
            raise ValueError("document_scanner=clamav is required in production")
        if self.cv_jd_extraction_max_tokens > self.vllm_max_tokens:
            raise ValueError("cv_jd_extraction_max_tokens must not exceed vllm_max_tokens")
        if self.course_generation_max_tokens > self.vllm_max_tokens:
            raise ValueError("course_generation_max_tokens must not exceed vllm_max_tokens")
        return self
