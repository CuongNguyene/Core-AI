from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.capability_analysis.schemas import PreliminaryPriority
from app.instructional_blueprint.schemas import InstructionalBlueprint
from app.learning_need_profile.schemas import (
    LearnerContext,
    LearningNeedCompetency,
    LearningNeedCurrentState,
    LearningNeedGap,
    LearningNeedTargetState,
)


class LearningNeedProfileProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    candidate_reference: UUID
    target_reference: str = Field(min_length=1)
    learner_context: LearnerContext
    competency: LearningNeedCompetency
    current_state: LearningNeedCurrentState
    target_state: LearningNeedTargetState
    gap: LearningNeedGap
    missing_knowledge: list[str]
    priority: PreliminaryPriority
    confidence: float | None = None
    source_gap_refs: list[str] = Field(min_length=1)
    evidence_references: list[str]


class LearningObjectiveProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    learning_need_ref: str = Field(min_length=1)
    statement: str | None = None
    bloom_level: str | None = None
    evidence_required: list[str] | None = None
    competency_id: str = Field(min_length=1)
    current_level: int | None = None
    target_level: int | None = Field(default=None, ge=1, le=5)
    measurable_outcome: str = Field(min_length=1)
    gap_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)


class InstructionalBlueprintProjection(InstructionalBlueprint):
    """Typed API projection of the content-free instructional blueprint."""
