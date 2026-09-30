from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from app.authorization.schemas import ActorContext
from app.credential.evaluators import CredentialEligibilityEvaluator, CredentialEvaluationInput
from app.credential.policy import CredentialAuthorizationPolicy
from app.credential.repository import InMemoryCredentialRepository, SqlAlchemyCredentialRepository
from app.credential.schemas import (
    Credential,
    CredentialPolicy,
    CredentialRequest,
    CredentialRequestStatus,
    CredentialStatus,
    CredentialType,
    CredentialVerification,
)


class CredentialPolicyRegistry:
    def __init__(self, policies: list[CredentialPolicy]) -> None:
        self._policies = {(item.policy_id, item.version): item for item in policies}

    def get_active(self, policy_id: str, version: str) -> CredentialPolicy | None:
        policy = self._policies.get((policy_id, version))
        if policy is None or policy.status.value != "active":
            return None
        return policy


CredentialRepository = InMemoryCredentialRepository | SqlAlchemyCredentialRepository


class CredentialService:
    def __init__(
        self,
        *,
        repository: CredentialRepository,
        registry: CredentialPolicyRegistry,
        evaluators: Mapping[CredentialType, CredentialEligibilityEvaluator],
        authorization: CredentialAuthorizationPolicy,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._evaluators = evaluators
        self._authorization = authorization

    async def evaluate_and_request(
        self,
        *,
        actor: ActorContext,
        policy_id: str,
        policy_version: str,
        source_reference_id: str | None,
        correlation_id: UUID,
    ) -> CredentialRequest:
        policy = self._registry.get_active(policy_id, policy_version)
        if policy is None:
            raise ValueError("credential_policy_not_active")
        if actor.organization_id != policy.organization_id:
            raise PermissionError("organization_mismatch")
        evaluator = self._evaluators.get(policy.credential_type)
        if evaluator is None:
            raise ValueError("credential_evaluator_unavailable")
        decision = await evaluator.evaluate(
            CredentialEvaluationInput(
                policy=policy,
                subject_id=actor.actor_id,
                organization_id=actor.organization_id,
                source_reference_id=source_reference_id,
            )
        )
        return await self._repository.create_request(
            policy=policy,
            subject_id=actor.actor_id,
            source_reference_id=source_reference_id,
            evaluation=decision,
            requested_by=actor.actor_id,
            correlation_id=correlation_id,
        )

    async def approve(
        self, *, actor: ActorContext, request_id: UUID, expected_version: int
    ) -> CredentialRequest:
        request = await self._require_request(request_id)
        authorization = await self._authorization.can_approve(
            actor=actor,
            organization_id=request.organization_id,
            policy_id=request.policy_id,
            requester_id=request.requested_by,
        )
        if not authorization.allowed:
            raise PermissionError(authorization.reason_code)
        return await self._repository.transition_request(
            request_id,
            expected_version=expected_version,
            target=CredentialRequestStatus.APPROVED,
            actor_id=actor.actor_id,
        )

    async def reject(
        self, *, actor: ActorContext, request_id: UUID, expected_version: int
    ) -> CredentialRequest:
        request = await self._require_request(request_id)
        authorization = await self._authorization.can_approve(
            actor=actor,
            organization_id=request.organization_id,
            policy_id=request.policy_id,
            requester_id=request.requested_by,
        )
        if not authorization.allowed:
            raise PermissionError(authorization.reason_code)
        return await self._repository.transition_request(
            request_id,
            expected_version=expected_version,
            target=CredentialRequestStatus.REJECTED,
            actor_id=actor.actor_id,
        )

    async def issue(
        self, *, actor: ActorContext, request_id: UUID, expected_version: int
    ) -> Credential:
        request = await self._require_request(request_id)
        if request.status is not CredentialRequestStatus.APPROVED:
            raise ValueError("credential_approval_required")
        authorization = await self._authorization.can_issue(
            actor=actor,
            organization_id=request.organization_id,
            policy_id=request.policy_id,
            requester_id=request.requested_by,
        )
        if not authorization.allowed:
            raise PermissionError(authorization.reason_code)
        policy = self._registry.get_active(request.policy_id, request.policy_version)
        if policy is None:
            raise ValueError("credential_policy_not_active")
        return await self._repository.issue_approved(
            request_id,
            expected_version=expected_version,
            actor_id=actor.actor_id,
            valid_for_days=policy.valid_for_days,
            allow_duplicate_active=policy.allow_duplicate_active,
        )

    async def revoke(
        self, *, actor: ActorContext, credential_id: UUID, expected_version: int
    ) -> Credential:
        credential = await self._repository.get_credential(credential_id)
        if credential is None:
            raise KeyError(credential_id)
        if credential.version != expected_version:
            raise ValueError("version_conflict")
        authorization = await self._authorization.can_revoke(
            actor=actor, organization_id=credential.organization_id, policy_id=credential.policy_id
        )
        if not authorization.allowed:
            raise PermissionError(authorization.reason_code)
        return await self._repository.revoke_or_expire(
            credential_id, target=CredentialStatus.REVOKED, actor_id=actor.actor_id
        )

    async def expire_if_due(
        self, *, actor: ActorContext, credential_id: UUID, expected_version: int
    ) -> Credential:
        credential = await self._repository.get_credential(credential_id)
        if credential is None:
            raise KeyError(credential_id)
        if credential.version != expected_version:
            raise ValueError("version_conflict")
        authorization = await self._authorization.can_revoke(
            actor=actor, organization_id=credential.organization_id, policy_id=credential.policy_id
        )
        if not authorization.allowed:
            raise PermissionError(authorization.reason_code)
        return await self._repository.revoke_or_expire(
            credential_id, target=CredentialStatus.EXPIRED, actor_id=actor.actor_id
        )

    async def verify_public(self, credential_id: UUID) -> CredentialVerification:
        credential = await self._repository.get_credential(credential_id)
        if credential is None:
            return CredentialVerification(credential_id=credential_id, valid=False)
        status = credential.status
        if status is CredentialStatus.ISSUED and credential.valid_until <= datetime.now(UTC):
            status = CredentialStatus.EXPIRED
        return CredentialVerification(
            credential_id=credential.id,
            credential_type=credential.credential_type,
            status=status,
            valid=status is CredentialStatus.ISSUED,
            policy_id=credential.policy_id,
            policy_version=credential.policy_version,
            organization_id=credential.organization_id,
        )

    async def _require_request(self, request_id: UUID) -> CredentialRequest:
        request = await self._repository.get_request(request_id)
        if request is None:
            raise KeyError(request_id)
        return request
