from pydantic import BaseModel

from app.model_gateway.contracts import DataClassification, InferenceRequest
from app.model_gateway.errors import (
    ExternalProviderNotApprovedError,
    ExternalRoutingDisabledError,
    PrivacyDeniedError,
)
from app.privacy.contracts import PolicyDecision, PrivacyInspectionResult

LOCAL_PROVIDER_ID = "local-vllm"


class ProviderRoute(BaseModel):
    provider_id: str
    decision: str


class RoutingPolicy:
    def __init__(
        self,
        external_ai_enabled: bool,
        external_provider_id: str = "vilao-external",
        configured_provider_id: str = LOCAL_PROVIDER_ID,
        external_restricted_data_approved: bool = False,
    ) -> None:
        self._external_ai_enabled = external_ai_enabled
        self._external_provider_id = external_provider_id
        self._configured_provider_id = configured_provider_id
        self._external_restricted_data_approved = external_restricted_data_approved

    def route(
        self, request: InferenceRequest, privacy_result: PrivacyInspectionResult
    ) -> ProviderRoute:
        if privacy_result.decision in {PolicyDecision.DENY, PolicyDecision.REQUIRE_HUMAN_APPROVAL}:
            raise PrivacyDeniedError("Privacy policy did not allow inference")

        if request.data_classification is DataClassification.RESTRICTED:
            if request.requested_provider == self._external_provider_id or (
                request.requested_provider is None
                and self._configured_provider_id == self._external_provider_id
            ):
                if (
                    self._external_restricted_data_approved
                    and self._external_ai_enabled
                    and privacy_result.decision is PolicyDecision.ALLOW_LOCAL
                ):
                    return ProviderRoute(
                        provider_id=self._external_provider_id,
                        decision="approved_external_restricted",
                    )
                raise PrivacyDeniedError("Restricted data cannot route to an external provider")
            return ProviderRoute(provider_id=LOCAL_PROVIDER_ID, decision="restricted_local_only")

        if request.requested_provider in {None, LOCAL_PROVIDER_ID}:
            return ProviderRoute(provider_id=LOCAL_PROVIDER_ID, decision="local_default")

        if request.requested_provider == self._external_provider_id:
            if privacy_result.decision is not PolicyDecision.ALLOW_EXTERNAL_SANITIZED:
                raise PrivacyDeniedError("External inference requires sanitized privacy approval")
            if not self._external_ai_enabled:
                raise ExternalRoutingDisabledError("External model routing is disabled")
            return ProviderRoute(
                provider_id=self._external_provider_id,
                decision="approved_external_sanitized",
            )

        if not self._external_ai_enabled:
            raise ExternalRoutingDisabledError("External model routing is disabled")

        raise ExternalProviderNotApprovedError("No external provider is approved")
