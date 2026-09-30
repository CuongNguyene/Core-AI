from datetime import UTC, datetime
from uuid import UUID

from app.authorization.repository import (
    InMemoryDelegationRepository,
    SqlAlchemyDelegationRepository,
)
from app.authorization.schemas import ActorContext, AuthorizationDecision, DelegationStatus


class CredentialAuthorizationPolicy:
    def __init__(
        self,
        delegation_repository: InMemoryDelegationRepository | SqlAlchemyDelegationRepository,
        *,
        policy_version: str = "credential-authorization-v1",
    ) -> None:
        self._delegation_repository = delegation_repository
        self.policy_version = policy_version

    async def can_approve(
        self, *, actor: ActorContext, organization_id: UUID, policy_id: str, requester_id: UUID
    ) -> AuthorizationDecision:
        return await self._can(
            actor=actor,
            organization_id=organization_id,
            policy_id=policy_id,
            requester_id=requester_id,
            permission="credential.approve",
            self_forbidden=True,
        )

    async def can_issue(
        self, *, actor: ActorContext, organization_id: UUID, policy_id: str, requester_id: UUID
    ) -> AuthorizationDecision:
        return await self._can(
            actor=actor,
            organization_id=organization_id,
            policy_id=policy_id,
            requester_id=requester_id,
            permission="credential.issue",
            self_forbidden=True,
        )

    async def can_revoke(
        self, *, actor: ActorContext, organization_id: UUID, policy_id: str
    ) -> AuthorizationDecision:
        return await self._can(
            actor=actor,
            organization_id=organization_id,
            policy_id=policy_id,
            requester_id=None,
            permission="credential.revoke",
            self_forbidden=False,
        )

    async def _can(
        self,
        *,
        actor: ActorContext,
        organization_id: UUID,
        policy_id: str,
        requester_id: UUID | None,
        permission: str,
        self_forbidden: bool,
    ) -> AuthorizationDecision:
        if actor.organization_id != organization_id:
            return self._deny("organization_mismatch")
        if self_forbidden and requester_id == actor.actor_id:
            return self._deny("self_credential_action_forbidden")
        for delegation in await self._delegation_repository.active_for_user(actor.actor_id):
            if getattr(delegation, "permission", None) != permission:
                continue
            if getattr(delegation, "status", None) is not DelegationStatus.ACTIVE:
                continue
            if delegation.organization_id != organization_id:
                continue
            if policy_id not in delegation.competency_scope:
                continue
            now = datetime.now(UTC)
            if not delegation.valid_from <= now <= delegation.valid_until:
                continue
            return AuthorizationDecision(
                allowed=True,
                reason_code=f"{permission.replace('.', '_')}_allowed",
                policy_version=self.policy_version,
                delegation_id=delegation.id,
                scope_match=True,
            )
        return self._deny("credential_delegation_required")

    def _deny(self, reason_code: str) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=False,
            reason_code=reason_code,
            policy_version=self.policy_version,
        )
