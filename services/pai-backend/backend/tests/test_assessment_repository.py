from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.assessment.models import AssessmentAuditEventRecord
from app.assessment.repository import SqlAlchemyAssessmentRepository
from app.assessment.schemas import (
    AssessmentDecision,
    AssessmentSubmission,
    AssessmentTask,
    AssessmentTaskType,
    AssessmentTemplate,
    RiskClassification,
    Rubric,
    RubricCriterion,
    ScoreProposal,
    SMEReview,
)
from app.shared.database import Base


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def template() -> AssessmentTemplate:
    rubric = Rubric(
        id=uuid4(),
        version="1.0",
        criteria=[RubricCriterion(id="correctness", description="Correctness", max_score=5)],
    )
    return AssessmentTemplate(
        id=uuid4(),
        version="1.0",
        competency_id="python",
        rubric=rubric,
        policy_version="assessment-v1",
        risk_classification=RiskClassification.LOW_RISK,
        validity_days=365,
        reassessment_lead_days=30,
        tasks=[
            AssessmentTask(
                id="practical-1",
                task_type=AssessmentTaskType.PRACTICAL,
                prompt_reference="fixture:practical-1",
            )
        ],
    )


@pytest.mark.asyncio
async def test_repository_persists_assessment_decision_and_safe_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyAssessmentRepository(session_factory)
    saved_template = template()
    submission = AssessmentSubmission(
        id=uuid4(),
        template_id=saved_template.id,
        template_version=saved_template.version,
        subject_id=uuid4(),
        artifact_reference="storage:private-submission-1",
        evidence_ids=[uuid4()],
    )
    proposal = ScoreProposal(
        id=uuid4(),
        submission_id=submission.id,
        rubric_id=saved_template.rubric.id,
        rubric_version=saved_template.rubric.version,
        criterion_scores={"correctness": 5},
    )
    review = SMEReview(
        id=uuid4(),
        submission_id=submission.id,
        score_proposal_id=proposal.id,
        reviewer_id=uuid4(),
        rubric_version=saved_template.rubric.version,
        evidence_ids=submission.evidence_ids,
        decision_rationale_reference="storage:private-review-1",
    )
    decision = AssessmentDecision(
        id=uuid4(),
        submission_id=submission.id,
        score_proposal_id=proposal.id,
        review_id=review.id,
        assessor_id=review.reviewer_id,
        rubric_version=saved_template.rubric.version,
        policy_version=saved_template.policy_version,
        evidence_ids=submission.evidence_ids,
        risk_classification=saved_template.risk_classification,
        decided_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    await repository.save_template(saved_template)
    await repository.submit(submission)
    await repository.record_score_proposal(proposal)
    await repository.record_sme_review(review)
    persisted = await repository.create_decision(decision)

    assert persisted == decision
    async with session_factory() as session:
        events = list((await session.scalars(select(AssessmentAuditEventRecord))).all())
    assert len(events) == 1
    assert events[0].action == "ASSESSMENT_DECISION_CREATED"
    assert "artifact_reference" not in events[0].audit_metadata
    assert "decision_rationale_reference" not in events[0].audit_metadata
