from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class InferencePurpose(StrEnum):
    CV_EXTRACTION = "cv_extraction"
    JD_EXTRACTION = "jd_extraction"
    COMPETENCY_MAPPING = "competency_mapping"
    LEARNING_CONTENT_GENERATION = "learning_content_generation"
    ASSESSMENT_GENERATION = "assessment_generation"
    CURRICULUM_PLANNING = "curriculum_planning"
    AUTHORING_CONVERSATION = "authoring_conversation"


class OutputContract(BaseModel):
    schema_id: str
    schema_version: str
    strict: bool = True


class ModelUsage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class DocumentInput(BaseModel):
    """Opaque provider input; bytes never enter prompt/privacy diagnostics."""

    media_type: str = Field(min_length=1)
    content: bytes = Field(min_length=1)
    filename: str | None = None


class InferenceAuditMetadata(BaseModel):
    provider: str
    model: str
    model_revision: str | None = None
    prompt_template_id: str
    prompt_template_version: str
    output_schema_id: str | None = None
    output_schema_version: str | None = None
    policy_version: str
    correlation_id: str
    routing_decision: str
    attempt_count: int = Field(ge=1)
    latency_ms: int = Field(ge=0)
    usage: ModelUsage
    outcome: str
    finish_reason: str | None = None
    protocol: str = "unknown"
    deployment_type: str = "unknown"
    endpoint_origin: str | None = None
    data_boundary: str = "unknown"


class InferenceRequest(BaseModel):
    purpose: InferencePurpose
    data_classification: DataClassification
    prompt_template_id: str
    prompt_template_version: str
    payload: dict[str, object]
    document: DocumentInput | None = None
    output_contract: OutputContract | None = None
    requested_provider: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    output_token_budget: int | None = Field(default=None, gt=0)
    correlation_id: str


class TextInferenceResponse(BaseModel):
    content: str
    audit: InferenceAuditMetadata


class StructuredInferenceResponse[T: BaseModel](BaseModel):
    parsed: T
    audit: InferenceAuditMetadata


class ModelGateway(Protocol):
    async def infer_text(self, request: InferenceRequest) -> TextInferenceResponse: ...

    async def infer_structured(
        self, request: InferenceRequest, output_schema: type[T]
    ) -> StructuredInferenceResponse[T]: ...
