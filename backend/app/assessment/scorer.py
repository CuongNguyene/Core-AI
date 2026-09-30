from typing import Protocol
from uuid import uuid4

from app.assessment.schemas import AssessmentSubmission, Rubric, ScoreProposal


class AssessmentScorer(Protocol):
    async def score(self, submission: AssessmentSubmission, rubric: Rubric) -> ScoreProposal: ...


class MockAssessmentScorer:
    """Deterministic test scorer; it never creates a competency decision."""

    async def score(self, submission: AssessmentSubmission, rubric: Rubric) -> ScoreProposal:
        return ScoreProposal(
            id=uuid4(),
            submission_id=submission.id,
            rubric_id=rubric.id,
            rubric_version=rubric.version,
            criterion_scores={criterion.id: 0.0 for criterion in rubric.criteria},
        )
