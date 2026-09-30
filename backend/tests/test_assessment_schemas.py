from uuid import uuid4

import pytest

from app.assessment.schemas import (
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


def test_template_requires_versioned_rubric_and_placeholder_task() -> None:
    rubric = Rubric(
        id=uuid4(),
        version="1.0",
        criteria=[RubricCriterion(id="correctness", description="Correctness", max_score=5)],
    )
    template = AssessmentTemplate(
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
                id="quiz-1", task_type=AssessmentTaskType.QUIZ, prompt_reference="fixture:quiz-1"
            )
        ],
    )

    assert template.rubric.version == "1.0"
    assert template.tasks[0].task_type is AssessmentTaskType.QUIZ


def test_template_rejects_missing_task_or_invalid_reassessment_policy() -> None:
    with pytest.raises(ValueError):
        AssessmentTemplate(
            id=uuid4(),
            version="1.0",
            competency_id="python",
            rubric=Rubric(
                id=uuid4(),
                version="1.0",
                criteria=[RubricCriterion(id="c", description="C", max_score=1)],
            ),
            policy_version="assessment-v1",
            risk_classification=RiskClassification.LOW_RISK,
            validity_days=30,
            reassessment_lead_days=30,
            tasks=[],
        )


def test_sme_review_is_separate_from_the_score_proposal() -> None:
    submission_id = uuid4()
    proposal = ScoreProposal(
        id=uuid4(),
        submission_id=submission_id,
        rubric_id=uuid4(),
        rubric_version="1.0",
        criterion_scores={"correctness": 5},
    )
    review = SMEReview(
        id=uuid4(),
        submission_id=submission_id,
        score_proposal_id=proposal.id,
        reviewer_id=uuid4(),
        rubric_version="1.0",
        evidence_ids=[uuid4()],
        decision_rationale_reference="fixture:review-1",
    )

    assert review.human_review_completed is True
    assert not hasattr(AssessmentSubmission, "competency_status")
