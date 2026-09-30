from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssessmentTaskType(StrEnum):
    QUIZ = "quiz"
    PRACTICAL = "practical"
    CASE = "case"


class RiskClassification(StrEnum):
    LOW_RISK = "low_risk"
    HIGH_RISK = "high_risk"


class RubricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    max_score: float = Field(gt=0)


class Rubric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    version: str = Field(min_length=1)
    criteria: list[RubricCriterion] = Field(min_length=1)


class AssessmentTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    task_type: AssessmentTaskType
    prompt_reference: str = Field(min_length=1)


class AssessmentTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    version: str = Field(min_length=1)
    competency_id: str = Field(min_length=1)
    rubric: Rubric
    policy_version: str = Field(min_length=1)
    risk_classification: RiskClassification
    validity_days: int = Field(gt=0)
    reassessment_lead_days: int = Field(ge=0)
    tasks: list[AssessmentTask] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_reassessment_window(self) -> "AssessmentTemplate":
        if self.reassessment_lead_days >= self.validity_days:
            raise ValueError("Reassessment lead must be shorter than validity")
        return self


class AssessmentSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    template_id: UUID
    template_version: str = Field(min_length=1)
    subject_id: UUID
    artifact_reference: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(min_length=1)


class ScoreProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    submission_id: UUID
    rubric_id: UUID
    rubric_version: str = Field(min_length=1)
    criterion_scores: dict[str, float]
    human_review_required: Literal[True] = True


class SMEReview(BaseModel):
    """Human review of a proposal; it is not a competency decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    submission_id: UUID
    score_proposal_id: UUID
    reviewer_id: UUID
    rubric_version: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(min_length=1)
    decision_rationale_reference: str = Field(min_length=1)
    human_review_completed: Literal[True] = True


class AssessmentDecision(BaseModel):
    """SME decision based on a reviewed submission, not a competency transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    submission_id: UUID
    subject_id: UUID | None = None
    score_proposal_id: UUID
    review_id: UUID
    assessor_id: UUID
    rubric_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(min_length=1)
    risk_classification: RiskClassification
    decided_at: datetime
