from uuid import uuid4

import pytest

from app.assessment.schemas import AssessmentSubmission, Rubric, RubricCriterion
from app.assessment.scorer import MockAssessmentScorer


@pytest.mark.asyncio
async def test_mock_scorer_returns_proposal_not_competency_decision() -> None:
    submission = AssessmentSubmission(
        id=uuid4(),
        template_id=uuid4(),
        template_version="1.0",
        subject_id=uuid4(),
        artifact_reference="fixture:submission-1",
        evidence_ids=[uuid4()],
    )
    rubric = Rubric(
        id=uuid4(), version="1.0", criteria=[RubricCriterion(id="c", description="C", max_score=5)]
    )

    proposal = await MockAssessmentScorer().score(submission, rubric)

    assert proposal.submission_id == submission.id
    assert proposal.human_review_required is True
    assert not hasattr(proposal, "competency_status")
