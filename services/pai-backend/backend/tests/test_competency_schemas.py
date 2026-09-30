from datetime import UTC, datetime
from uuid import uuid4

from app.competency.schemas import CompetencyDecision, CompetencyLevelStatus


def test_competency_state_includes_verification_review_states() -> None:
    assert CompetencyLevelStatus.PENDING_VERIFICATION.value == "pending_verification"
    assert CompetencyLevelStatus.RETURNED_FOR_REVIEW.value == "returned_for_review"


def test_competency_decision_requires_versioned_rubric_and_evidence() -> None:
    decision = CompetencyDecision(
        id=uuid4(),
        subject_id=uuid4(),
        competency_id="python",
        assessment_submission_id=uuid4(),
        evidence_ids=[uuid4()],
        rubric_version="1.0",
        policy_version="assessment-v1",
        status=CompetencyLevelStatus.ASSESSED,
        valid_until=datetime(2027, 1, 1, tzinfo=UTC),
        reassessment_due_at=datetime(2026, 12, 1, tzinfo=UTC),
    )

    assert decision.status is CompetencyLevelStatus.ASSESSED
