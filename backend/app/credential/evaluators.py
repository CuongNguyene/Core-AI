from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.competency.schemas import CompetencyDecision, CompetencyLevelStatus, CompetencyRecord
from app.credential.providers import (
    CompletionAssertion,
    CourseCompletionAssertionProvider,
    LearningOutcomeAssertion,
    LearningOutcomeAssertionProvider,
)
from app.credential.schemas import (
    CredentialPolicy,
    EligibilityDecision,
    EligibilityStatus,
)


@dataclass(frozen=True)
class CredentialEvaluationInput:
    policy: CredentialPolicy
    subject_id: UUID
    organization_id: UUID
    source_reference_id: str | None


class CredentialEligibilityEvaluator(Protocol):
    async def evaluate(self, request: CredentialEvaluationInput) -> EligibilityDecision: ...


class CompletionCredentialEvaluator:
    def __init__(self, provider: CourseCompletionAssertionProvider) -> None:
        self._provider = provider

    async def evaluate(self, request: CredentialEvaluationInput) -> EligibilityDecision:
        assertion = await self._provider.get(request.source_reference_id or "")
        if assertion is None:
            return EligibilityDecision(
                policy_id=request.policy.policy_id,
                policy_version=request.policy.version,
                subject_id=request.subject_id,
                organization_id=request.organization_id,
                status=EligibilityStatus.NOT_EVALUABLE,
                reason_code="AUTHORITATIVE_COMPLETION_ASSERTION_UNAVAILABLE",
                evaluator_version="completion-evaluator-v1",
            )
        if not isinstance(assertion, CompletionAssertion):
            return EligibilityDecision(
                policy_id=request.policy.policy_id,
                policy_version=request.policy.version,
                subject_id=request.subject_id,
                organization_id=request.organization_id,
                status=EligibilityStatus.REQUIRES_REVIEW,
                reason_code="COMPLETION_ASSERTION_SCHEMA_INVALID",
                evaluator_version="completion-evaluator-v1",
            )
        return EligibilityDecision(
            policy_id=request.policy.policy_id,
            policy_version=request.policy.version,
            subject_id=request.subject_id,
            organization_id=request.organization_id,
            status=(
                EligibilityStatus.ELIGIBLE
                if assertion.learner_id == request.subject_id
                and assertion.organization_id == request.organization_id
                and assertion.completed
                else EligibilityStatus.INELIGIBLE
            ),
            reason_code=(
                "COMPLETION_POLICY_ELIGIBLE"
                if assertion.learner_id == request.subject_id
                and assertion.organization_id == request.organization_id
                and assertion.completed
                else "COMPLETION_ASSERTION_NOT_ELIGIBLE"
            ),
            evaluator_version="completion-evaluator-v1",
        )


class LearningAchievementCredentialEvaluator:
    def __init__(self, provider: LearningOutcomeAssertionProvider) -> None:
        self._provider = provider

    async def evaluate(self, request: CredentialEvaluationInput) -> EligibilityDecision:
        assertion = await self._provider.get(request.source_reference_id or "")
        if assertion is None:
            return EligibilityDecision(
                policy_id=request.policy.policy_id,
                policy_version=request.policy.version,
                subject_id=request.subject_id,
                organization_id=request.organization_id,
                status=EligibilityStatus.NOT_EVALUABLE,
                reason_code="AUTHORITATIVE_LEARNING_OUTCOME_ASSERTION_UNAVAILABLE",
                evaluator_version="learning-achievement-evaluator-v1",
            )
        eligible = (
            isinstance(assertion, LearningOutcomeAssertion)
            and assertion.learner_id == request.subject_id
            and assertion.organization_id == request.organization_id
            and assertion.passed
        )
        return EligibilityDecision(
            policy_id=request.policy.policy_id,
            policy_version=request.policy.version,
            subject_id=request.subject_id,
            organization_id=request.organization_id,
            status=EligibilityStatus.ELIGIBLE if eligible else EligibilityStatus.INELIGIBLE,
            reason_code="LEARNING_OUTCOME_POLICY_ELIGIBLE"
            if eligible
            else "LEARNING_OUTCOME_ASSERTION_NOT_ELIGIBLE",
            evaluator_version="learning-achievement-evaluator-v1",
        )


class CompetencyReader(Protocol):
    async def get_record(self, record_id: UUID) -> CompetencyRecord | None: ...

    async def get_decision(self, decision_id: UUID) -> CompetencyDecision | None: ...


class CompetencyCredentialEvaluator:
    def __init__(self, reader: CompetencyReader) -> None:
        self._reader = reader

    async def evaluate(self, request: CredentialEvaluationInput) -> EligibilityDecision:
        try:
            record_id = UUID(request.source_reference_id or "")
        except ValueError:
            return self._decision(
                request, EligibilityStatus.INELIGIBLE, "COMPETENCY_REFERENCE_INVALID"
            )
        record = await self._reader.get_record(record_id)
        if record is None or record.subject_id != request.subject_id:
            return self._decision(request, EligibilityStatus.INELIGIBLE, "COMPETENCY_NOT_FOUND")
        if record.organization_id != request.organization_id:
            return self._decision(request, EligibilityStatus.INELIGIBLE, "ORGANIZATION_MISMATCH")
        if record.status is not CompetencyLevelStatus.VERIFIED:
            return self._decision(request, EligibilityStatus.INELIGIBLE, "COMPETENCY_NOT_VERIFIED")
        if record.valid_until is None or record.valid_until <= datetime.now(UTC):
            return self._decision(request, EligibilityStatus.INELIGIBLE, "COMPETENCY_EXPIRED")
        if request.policy.competency_id and request.policy.competency_id != record.competency_id:
            return self._decision(
                request, EligibilityStatus.INELIGIBLE, "COMPETENCY_POLICY_MISMATCH"
            )
        if request.policy.minimum_level and (record.level or 0) < request.policy.minimum_level:
            return self._decision(
                request, EligibilityStatus.INELIGIBLE, "COMPETENCY_LEVEL_INSUFFICIENT"
            )
        if record.last_decision_id is None:
            return self._decision(
                request, EligibilityStatus.REQUIRES_REVIEW, "COMPETENCY_DECISION_MISSING"
            )
        decision = await self._reader.get_decision(record.last_decision_id)
        if (
            decision is None
            or not getattr(decision, "evidence_ids", None)
            or not getattr(decision, "rubric_version", None)
        ):
            return self._decision(
                request, EligibilityStatus.REQUIRES_REVIEW, "COMPETENCY_REFERENCES_INVALID"
            )
        return self._decision(request, EligibilityStatus.ELIGIBLE, "COMPETENCY_POLICY_ELIGIBLE")

    @staticmethod
    def _decision(
        request: CredentialEvaluationInput, status: EligibilityStatus, reason_code: str
    ) -> EligibilityDecision:
        return EligibilityDecision(
            policy_id=request.policy.policy_id,
            policy_version=request.policy.version,
            subject_id=request.subject_id,
            organization_id=request.organization_id,
            status=status,
            reason_code=reason_code,
            evaluator_version="competency-evaluator-v1",
        )
