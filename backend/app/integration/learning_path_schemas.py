from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LearningPathCreateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    development_goal: str = Field(min_length=1, max_length=500)
    target_completion_date: date


class LearningPathProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    learning_path_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    status: Literal["draft", "active", "superseded", "failed"]
    source_type: Literal["capability_analysis"]
    candidate_reference: UUID
    capability_analysis_reference: str = Field(min_length=1)
    target_reference: str = Field(min_length=1)
    gap_references: list[str]
    evidence_references: list[str]
    recommendation_references: list[str]
    ready_for_review: bool
    is_stale: bool

