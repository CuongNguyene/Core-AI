from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.competency.schemas import CompetencyDecision, CompetencyLevelStatus, CompetencyRecord
from app.credential.evaluators import (
    CompetencyCredentialEvaluator,
    CompletionCredentialEvaluator,
    CredentialEvaluationInput,
    LearningAchievementCredentialEvaluator,
)
from app.credential.providers import (
    CompletionAssertion,
    FakeCompletionAssertionProvider,
    FakeLearningOutcomeAssertionProvider,
    LearningOutcomeAssertion,
    UnavailableCompletionAssertionProvider,
    UnavailableLearningOutcomeAssertionProvider,
)
from app.credential.schemas import (
    CredentialPolicy,
    CredentialPolicyStatus,
    CredentialType,
    EligibilityStatus,
)


@pytest.mark.asyncio
async def test_completion_without_authoritative_provider_is_not_evaluable() -> None:
    policy = CredentialPolicy(
        policy_id="course-completion-v1",
        version="v1",
        credential_type=CredentialType.COMPLETION,
        status=CredentialPolicyStatus.ACTIVE,
        organization_id=uuid4(),
        valid_for_days=365,
        allow_duplicate_active=False,
        requires_distinct_approver_and_issuer=False,
    )

    result = await CompletionCredentialEvaluator(UnavailableCompletionAssertionProvider()).evaluate(
        CredentialEvaluationInput(
            policy=policy,
            subject_id=uuid4(),
            organization_id=policy.organization_id,
            source_reference_id="course-record-1",
        )
    )

    assert result.status is EligibilityStatus.NOT_EVALUABLE
    assert result.reason_code == "AUTHORITATIVE_COMPLETION_ASSERTION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_learning_achievement_without_authoritative_provider_is_not_evaluable() -> None:
    policy = CredentialPolicy(
        policy_id="learning-achievement-v1",
        version="v1",
        credential_type=CredentialType.LEARNING_ACHIEVEMENT,
        status=CredentialPolicyStatus.ACTIVE,
        organization_id=uuid4(),
        valid_for_days=365,
        allow_duplicate_active=False,
        requires_distinct_approver_and_issuer=False,
    )

    result = await LearningAchievementCredentialEvaluator(
        UnavailableLearningOutcomeAssertionProvider()
    ).evaluate(
        CredentialEvaluationInput(
            policy=policy,
            subject_id=uuid4(),
            organization_id=policy.organization_id,
            source_reference_id="outcome-record-1",
        )
    )

    assert result.status is EligibilityStatus.NOT_EVALUABLE
    assert result.reason_code == "AUTHORITATIVE_LEARNING_OUTCOME_ASSERTION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_fake_authoritative_completion_assertion_is_eligible() -> None:
    subject_id = uuid4()
    organization_id = uuid4()
    policy = CredentialPolicy(
        policy_id="course-completion-v1",
        version="v1",
        credential_type=CredentialType.COMPLETION,
        status=CredentialPolicyStatus.ACTIVE,
        organization_id=organization_id,
        valid_for_days=365,
        allow_duplicate_active=False,
        requires_distinct_approver_and_issuer=False,
    )
    evaluator = CompletionCredentialEvaluator(
        FakeCompletionAssertionProvider(
            {
                "completion-1": CompletionAssertion(
                    learner_id=subject_id,
                    organization_id=organization_id,
                    course_id="course-1",
                    course_version="v1",
                    completed=True,
                    source_system="test-lms",
                    source_record_id="record-1",
                )
            }
        )
    )

    result = await evaluator.evaluate(
        CredentialEvaluationInput(
            policy=policy,
            subject_id=subject_id,
            organization_id=organization_id,
            source_reference_id="completion-1",
        )
    )

    assert result.status is EligibilityStatus.ELIGIBLE


@pytest.mark.asyncio
async def test_fake_learning_outcome_assertion_is_eligible_only_when_passed() -> None:
    subject_id = uuid4()
    organization_id = uuid4()
    policy = CredentialPolicy(
        policy_id="achievement-v1",
        version="v1",
        credential_type=CredentialType.LEARNING_ACHIEVEMENT,
        status=CredentialPolicyStatus.ACTIVE,
        organization_id=organization_id,
        valid_for_days=365,
        allow_duplicate_active=False,
        requires_distinct_approver_and_issuer=False,
    )
    evaluator = LearningAchievementCredentialEvaluator(
        FakeLearningOutcomeAssertionProvider(
            {
                "outcome-1": LearningOutcomeAssertion(
                    learner_id=subject_id,
                    organization_id=organization_id,
                    learning_outcome_id="outcome-1",
                    course_version="v1",
                    assessment_id="assessment-1",
                    rubric_version="rubric-v1",
                    passed=True,
                )
            }
        )
    )

    result = await evaluator.evaluate(
        CredentialEvaluationInput(
            policy=policy,
            subject_id=subject_id,
            organization_id=organization_id,
            source_reference_id="outcome-1",
        )
    )

    assert result.status is EligibilityStatus.ELIGIBLE


class FakeCompetencyReader:
    def __init__(self, record: CompetencyRecord, decision: CompetencyDecision) -> None:
        self.record = record
        self.decision = decision

    async def get_record(self, record_id: object) -> CompetencyRecord | None:
        return self.record if record_id == self.record.id else None

    async def get_decision(self, decision_id: object) -> CompetencyDecision | None:
        return self.decision if decision_id == self.decision.id else None


@pytest.mark.asyncio
async def test_verified_competency_with_valid_decision_is_eligible() -> None:
    subject_id = uuid4()
    organization_id = uuid4()
    decision_id = uuid4()
    record = CompetencyRecord(
        id=uuid4(),
        subject_id=subject_id,
        organization_id=organization_id,
        competency_id="python",
        status=CompetencyLevelStatus.VERIFIED,
        level=3,
        version=2,
        last_decision_id=decision_id,
        valid_until=datetime.now(UTC) + timedelta(days=30),
        reassessment_due_at=datetime.now(UTC) + timedelta(days=15),
    )
    decision = CompetencyDecision(
        id=decision_id,
        subject_id=subject_id,
        organization_id=organization_id,
        competency_id="python",
        assessment_submission_id=uuid4(),
        evidence_ids=[uuid4()],
        rubric_version="rubric-v1",
        policy_version="competency-v1",
        previous_status=CompetencyLevelStatus.PENDING_VERIFICATION,
        status=CompetencyLevelStatus.VERIFIED,
        decided_by=uuid4(),
        delegation_id=uuid4(),
        valid_until=record.valid_until,
        reassessment_due_at=record.reassessment_due_at,
    )
    policy = CredentialPolicy(
        policy_id="python-level-3",
        version="v1",
        credential_type=CredentialType.COMPETENCY,
        status=CredentialPolicyStatus.ACTIVE,
        organization_id=organization_id,
        valid_for_days=365,
        allow_duplicate_active=False,
        requires_distinct_approver_and_issuer=True,
    )

    result = await CompetencyCredentialEvaluator(FakeCompetencyReader(record, decision)).evaluate(
        CredentialEvaluationInput(
            policy=policy,
            subject_id=subject_id,
            organization_id=organization_id,
            source_reference_id=str(record.id),
        )
    )

    assert result.status is EligibilityStatus.ELIGIBLE
