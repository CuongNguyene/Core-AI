from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.assessment.schemas import AssessmentDecision
from app.authorization.repository import (
    InMemoryDelegationRepository,
    SqlAlchemyDelegationRepository,
)
from app.authorization.schemas import (
    ActorContext,
    AuthorizationDecision,
    DelegationStatus,
    Role,
)


class DelegationReader(Protocol):
    async def active_for_user(self, user_id: UUID) -> tuple[object, ...]: ...


class AssessmentDecisionReader(Protocol):
    async def get_decision(self, decision_id: UUID) -> AssessmentDecision | None: ...


class CompetencyAuthorizationPolicy:
    def __init__(
        self,
        subject_repository: object | None,
        delegation_repository: InMemoryDelegationRepository | SqlAlchemyDelegationRepository,
        assessment_repository: AssessmentDecisionReader,
        *,
        policy_version: str = "competency-policy-v1",
    ) -> None:
        self._subject_repository = subject_repository
        self._delegation_repository = delegation_repository
        self._assessment_repository = assessment_repository
        self.policy_version = policy_version

    async def can_mark_assessed(
        self,
        *,
        actor: ActorContext,
        organization_id: UUID,
        competency_id: str,
        assessment_decision_id: UUID,
    ) -> AuthorizationDecision:
        if actor.organization_id != organization_id:
            return self._deny("organization_mismatch")
        if Role.SME not in actor.roles:
            return self._deny("sme_role_required")
        decision = await self._assessment_repository.get_decision(assessment_decision_id)
        if decision is None:
            return self._deny("assessment_decision_not_found")
        if decision.risk_classification is None or not competency_id:
            return self._deny("assessment_context_invalid")
        return AuthorizationDecision(
            allowed=True,
            reason_code="assessed_allowed",
            policy_version=self.policy_version,
            matched_role=Role.SME,
        )

    async def can_verify(
        self,
        *,
        actor: ActorContext,
        subject_id: UUID,
        organization_id: UUID,
        competency_id: str,
        assessment_decision_id: UUID,
    ) -> AuthorizationDecision:
        if actor.organization_id != organization_id:
            return self._deny("organization_mismatch")
        if Role.SME not in actor.roles:
            return self._deny("sme_role_required")
        if actor.actor_id == subject_id:
            return self._deny("self_verification_forbidden")
        decision = await self._assessment_repository.get_decision(assessment_decision_id)
        if decision is None:
            return self._deny("assessment_decision_not_found")
        if (
            decision.risk_classification is not None
            and decision.risk_classification.value == "high_risk"
            and decision.assessor_id == actor.actor_id
        ):
            return self._deny("four_eyes_required")
        delegations = await self._delegation_repository.active_for_user(actor.actor_id)
        now = datetime.now(UTC)
        for item in delegations:
            if getattr(item, "permission", None) != "competency.verify":
                continue
            if getattr(item, "status", None) is not DelegationStatus.ACTIVE:
                continue
            if item.organization_id != organization_id:
                continue
            if competency_id not in item.competency_scope:
                return self._deny("verification_scope_mismatch")
            if not item.valid_from <= now <= item.valid_until:
                continue
            return AuthorizationDecision(
                allowed=True,
                reason_code="verification_allowed",
                policy_version=self.policy_version,
                matched_role=Role.SME,
                delegation_id=item.id,
                scope_match=True,
            )
        return self._deny("verification_delegation_required")

    def _deny(self, reason_code: str) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=False,
            reason_code=reason_code,
            policy_version=self.policy_version,
        )
