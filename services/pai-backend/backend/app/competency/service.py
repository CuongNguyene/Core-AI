from datetime import datetime
from uuid import UUID, uuid4

from app.assessment.repository import SqlAlchemyAssessmentRepository
from app.assessment.schemas import AssessmentDecision
from app.authorization.policy import CompetencyAuthorizationPolicy
from app.authorization.schemas import ActorContext
from app.competency.errors import AuthorizationDeniedError, CompetencyRecordNotFoundError
from app.competency.repository import SqlAlchemyCompetencyRepository
from app.competency.schemas import CompetencyDecision, CompetencyLevelStatus, CompetencyRecord


class CompetencyDecisionService:
    """Application-layer owner of explicit, policy-checked state transitions."""

    def __init__(
        self,
        repository: SqlAlchemyCompetencyRepository,
        assessment_repository: SqlAlchemyAssessmentRepository,
        policy: CompetencyAuthorizationPolicy,
    ) -> None:
        self._repository = repository
        self._assessment_repository = assessment_repository
        self._policy = policy

    async def mark_assessed(
        self,
        *,
        actor: ActorContext,
        record_id: UUID,
        assessment_decision_id: UUID,
        expected_version: int | None = None,
        valid_until: datetime,
        reassessment_due_at: datetime,
    ) -> CompetencyRecord:
        record = await self._repository.get_record(record_id)
        if record is None:
            raise CompetencyRecordNotFoundError(record_id)
        self._ensure_transition(record.status, CompetencyLevelStatus.ASSESSED)
        authorization = await self._policy.can_mark_assessed(
            actor=actor,
            organization_id=record.organization_id,
            competency_id=record.competency_id,
            assessment_decision_id=assessment_decision_id,
        )
        if not authorization.allowed:
            await self._repository.record_authorization_denied(
                record_id, actor_id=actor.actor_id, reason_code=authorization.reason_code
            )
            raise AuthorizationDeniedError(authorization.reason_code)
        decision = CompetencyDecision(
            id=uuid4(),
            subject_id=record.subject_id,
            organization_id=record.organization_id,
            competency_id=record.competency_id,
            assessment_submission_id=(await self._assessment(assessment_decision_id)).submission_id,
            evidence_ids=(await self._assessment(assessment_decision_id)).evidence_ids,
            rubric_version=(await self._assessment(assessment_decision_id)).rubric_version,
            policy_version=authorization.policy_version,
            previous_status=record.status,
            status=CompetencyLevelStatus.ASSESSED,
            decided_by=actor.actor_id,
            valid_until=valid_until,
            reassessment_due_at=reassessment_due_at,
        )
        return await self._repository.transition(
            record_id,
            expected_version=record.version if expected_version is None else expected_version,
            decision=decision,
        )

    async def verify(
        self,
        *,
        actor: ActorContext,
        record_id: UUID,
        assessment_decision_id: UUID,
        expected_version: int | None = None,
        valid_until: datetime,
        reassessment_due_at: datetime,
    ) -> CompetencyRecord:
        record = await self._repository.get_record(record_id)
        if record is None:
            raise CompetencyRecordNotFoundError(record_id)
        self._ensure_transition(record.status, CompetencyLevelStatus.VERIFIED)
        authorization = await self._policy.can_verify(
            actor=actor,
            subject_id=record.subject_id,
            organization_id=record.organization_id,
            competency_id=record.competency_id,
            assessment_decision_id=assessment_decision_id,
        )
        if not authorization.allowed:
            await self._repository.record_authorization_denied(
                record_id, actor_id=actor.actor_id, reason_code=authorization.reason_code
            )
            raise AuthorizationDeniedError(authorization.reason_code)
        assessment = await self._assessment(assessment_decision_id)
        decision = CompetencyDecision(
            id=uuid4(),
            subject_id=record.subject_id,
            organization_id=record.organization_id,
            competency_id=record.competency_id,
            assessment_submission_id=assessment.submission_id,
            evidence_ids=assessment.evidence_ids,
            rubric_version=assessment.rubric_version,
            policy_version=authorization.policy_version,
            previous_status=record.status,
            status=CompetencyLevelStatus.VERIFIED,
            decided_by=actor.actor_id,
            delegation_id=authorization.delegation_id,
            valid_until=valid_until,
            reassessment_due_at=reassessment_due_at,
        )
        return await self._repository.transition(
            record_id,
            expected_version=record.version if expected_version is None else expected_version,
            decision=decision,
        )

    async def request_verification(
        self,
        *,
        actor: ActorContext,
        record_id: UUID,
        assessment_decision_id: UUID,
        expected_version: int | None = None,
        valid_until: datetime,
        reassessment_due_at: datetime,
    ) -> CompetencyRecord:
        return await self._transition_status(
            actor=actor,
            record_id=record_id,
            assessment_decision_id=assessment_decision_id,
            target=CompetencyLevelStatus.PENDING_VERIFICATION,
            expected_version=expected_version,
            valid_until=valid_until,
            reassessment_due_at=reassessment_due_at,
        )

    async def return_for_review(
        self,
        *,
        actor: ActorContext,
        record_id: UUID,
        assessment_decision_id: UUID,
        expected_version: int | None = None,
        valid_until: datetime,
        reassessment_due_at: datetime,
    ) -> CompetencyRecord:
        return await self._transition_status(
            actor=actor,
            record_id=record_id,
            assessment_decision_id=assessment_decision_id,
            target=CompetencyLevelStatus.RETURNED_FOR_REVIEW,
            expected_version=expected_version,
            valid_until=valid_until,
            reassessment_due_at=reassessment_due_at,
        )

    async def require_reassessment(
        self,
        *,
        actor: ActorContext,
        record_id: UUID,
        assessment_decision_id: UUID,
        expected_version: int | None = None,
        valid_until: datetime,
        reassessment_due_at: datetime,
    ) -> CompetencyRecord:
        return await self._transition_status(
            actor=actor,
            record_id=record_id,
            assessment_decision_id=assessment_decision_id,
            target=CompetencyLevelStatus.REQUIRES_REASSESSMENT,
            expected_version=expected_version,
            valid_until=valid_until,
            reassessment_due_at=reassessment_due_at,
        )

    async def revoke_verification(
        self,
        *,
        actor: ActorContext,
        record_id: UUID,
        assessment_decision_id: UUID,
        expected_version: int | None = None,
        valid_until: datetime,
        reassessment_due_at: datetime,
    ) -> CompetencyRecord:
        return await self._transition_status(
            actor=actor,
            record_id=record_id,
            assessment_decision_id=assessment_decision_id,
            target=CompetencyLevelStatus.REVOKED,
            expected_version=expected_version,
            valid_until=valid_until,
            reassessment_due_at=reassessment_due_at,
        )

    async def _transition_status(
        self,
        *,
        actor: ActorContext,
        record_id: UUID,
        assessment_decision_id: UUID,
        target: CompetencyLevelStatus,
        expected_version: int | None,
        valid_until: datetime,
        reassessment_due_at: datetime,
    ) -> CompetencyRecord:
        record = await self._repository.get_record(record_id)
        if record is None:
            raise CompetencyRecordNotFoundError(record_id)
        self._ensure_transition(record.status, target)
        authorization = await self._policy.can_mark_assessed(
            actor=actor,
            organization_id=record.organization_id,
            competency_id=record.competency_id,
            assessment_decision_id=assessment_decision_id,
        )
        if not authorization.allowed:
            await self._repository.record_authorization_denied(
                record_id, actor_id=actor.actor_id, reason_code=authorization.reason_code
            )
            raise AuthorizationDeniedError(authorization.reason_code)
        assessment = await self._assessment(assessment_decision_id)
        decision = CompetencyDecision(
            id=uuid4(),
            subject_id=record.subject_id,
            organization_id=record.organization_id,
            competency_id=record.competency_id,
            assessment_submission_id=assessment.submission_id,
            evidence_ids=assessment.evidence_ids,
            rubric_version=assessment.rubric_version,
            policy_version=authorization.policy_version,
            previous_status=record.status,
            status=target,
            decided_by=actor.actor_id,
            valid_until=valid_until,
            reassessment_due_at=reassessment_due_at,
        )
        return await self._repository.transition(
            record_id,
            expected_version=record.version if expected_version is None else expected_version,
            decision=decision,
        )

    async def _assessment(self, decision_id: UUID) -> AssessmentDecision:
        decision = await self._assessment_repository.get_decision(decision_id)
        if decision is None:
            raise CompetencyRecordNotFoundError(decision_id)
        return decision

    @staticmethod
    def _ensure_transition(current: CompetencyLevelStatus, target: CompetencyLevelStatus) -> None:
        allowed = {
            CompetencyLevelStatus.UNKNOWN: {
                CompetencyLevelStatus.DECLARED,
                CompetencyLevelStatus.ASSESSED,
            },
            CompetencyLevelStatus.DECLARED: {CompetencyLevelStatus.ASSESSED},
            CompetencyLevelStatus.ASSESSED: {
                CompetencyLevelStatus.PENDING_VERIFICATION,
                CompetencyLevelStatus.VERIFIED,
                CompetencyLevelStatus.REQUIRES_REASSESSMENT,
            },
            CompetencyLevelStatus.PENDING_VERIFICATION: {
                CompetencyLevelStatus.VERIFIED,
                CompetencyLevelStatus.RETURNED_FOR_REVIEW,
            },
            CompetencyLevelStatus.RETURNED_FOR_REVIEW: {CompetencyLevelStatus.ASSESSED},
            CompetencyLevelStatus.VERIFIED: {
                CompetencyLevelStatus.REQUIRES_REASSESSMENT,
                CompetencyLevelStatus.REVOKED,
            },
            CompetencyLevelStatus.REQUIRES_REASSESSMENT: {
                CompetencyLevelStatus.ASSESSED,
                CompetencyLevelStatus.EXPIRED,
            },
        }
        if target not in allowed.get(current, set()):
            raise ValueError("invalid_competency_transition")
