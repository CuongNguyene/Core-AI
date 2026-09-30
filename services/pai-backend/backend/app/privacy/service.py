from typing import Protocol

from pydantic import BaseModel, Field

from app.model_gateway.contracts import DataClassification
from app.privacy.contracts import (
    PolicyDecision,
    PrivacyInspectionRequest,
    PrivacyInspectionResult,
)


class PIIInspection(BaseModel):
    detected_entity_types: list[str] = Field(default_factory=list)


class PIIInspector(Protocol):
    async def inspect(self, payload: dict[str, object]) -> PIIInspection: ...


class LocalPIIInspector:
    """Development placeholder; production must provide a real detector."""

    async def inspect(self, payload: dict[str, object]) -> PIIInspection:
        del payload
        return PIIInspection()


class PrivacyService:
    """Conservative privacy decision point for internal inference requests."""

    def __init__(
        self,
        inspector: PIIInspector,
        policy_version: str,
        external_public_data_enabled: bool = False,
    ) -> None:
        self._inspector = inspector
        self._policy_version = policy_version
        self._external_public_data_enabled = external_public_data_enabled

    async def inspect(self, request: PrivacyInspectionRequest) -> PrivacyInspectionResult:
        try:
            inspection = await self._inspector.inspect(request.payload)
        except Exception:
            return PrivacyInspectionResult(
                decision=PolicyDecision.DENY,
                detected_entity_types=[],
                policy_version=self._policy_version,
                reasons=["pii_inspection_failed"],
            )

        if (
            self._external_public_data_enabled
            and request.data_classification is DataClassification.PUBLIC
            and request.requested_provider is not None
        ):
            return PrivacyInspectionResult(
                decision=PolicyDecision.ALLOW_EXTERNAL_SANITIZED,
                sanitized_payload=dict(request.payload),
                detected_entity_types=inspection.detected_entity_types,
                policy_version=self._policy_version,
                reasons=["public_payload_inspected_for_external_processing"],
            )

        return PrivacyInspectionResult(
            decision=PolicyDecision.ALLOW_LOCAL,
            detected_entity_types=inspection.detected_entity_types,
            policy_version=self._policy_version,
            reasons=["local_processing_only"],
        )
