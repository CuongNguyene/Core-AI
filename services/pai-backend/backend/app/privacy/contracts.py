from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

from app.model_gateway.contracts import DataClassification, InferencePurpose


class PolicyDecision(StrEnum):
    ALLOW_LOCAL = "allow_local"
    ALLOW_EXTERNAL_SANITIZED = "allow_external_sanitized"
    DENY = "deny"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"


class PrivacyInspectionRequest(BaseModel):
    purpose: InferencePurpose
    data_classification: DataClassification
    payload: dict[str, object]
    requested_provider: str | None = None


class PrivacyInspectionResult(BaseModel):
    decision: PolicyDecision
    sanitized_payload: dict[str, object] | None = None
    detected_entity_types: list[str] = Field(default_factory=list)
    policy_version: str
    reasons: list[str] = Field(default_factory=list)


class PrivacyGateway(Protocol):
    async def inspect(self, request: PrivacyInspectionRequest) -> PrivacyInspectionResult: ...
