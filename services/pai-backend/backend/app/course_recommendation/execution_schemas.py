"""Immutable persisted read contract for one recommendation execution."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.course_recommendation.engine import CourseRecommendationEngine
from app.course_recommendation.execution_snapshots import GovernanceSnapshot
from app.course_recommendation.schemas import (
    CourseRecommendationRequest,
    CourseRecommendationResult,
)


class RecommendationExecutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1, max_length=64)
    request_key: str = Field(min_length=1, max_length=128)
    request_fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    snapshot_schema_version: str = "1.0"
    algorithm_id: str = Field(min_length=1, max_length=128)
    algorithm_version: str = Field(min_length=1, max_length=64)
    result_kind: str = Field(min_length=1, max_length=64)
    target_ref: str = Field(min_length=1, max_length=512)
    source_learning_need_ref: str | None = Field(default=None, max_length=512)
    organization_ref: UUID
    actor_ref: UUID
    request_snapshot: CourseRecommendationRequest
    result_snapshot: CourseRecommendationResult
    governance_snapshot: GovernanceSnapshot
    created_at: datetime

    @model_validator(mode="after")
    def validate_server_owned_identity(self) -> RecommendationExecutionRecord:
        if self.snapshot_schema_version != "1.0":
            raise ValueError("recommendation_snapshot_version_unsupported")
        if (
            self.algorithm_id != CourseRecommendationEngine.algorithm_id
            or self.algorithm_version != CourseRecommendationEngine.algorithm_version
        ):
            raise ValueError("recommendation_algorithm_identity_invalid")
        expected_kind = (
            "recommendations" if self.result_snapshot.recommendations else "no_suitable_course"
        )
        if (
            self.result_kind != expected_kind
            or self.target_ref != self.result_snapshot.target_ref
            or self.target_ref != self.request_snapshot.recommendation_target.target_ref
            or self.source_learning_need_ref
            != self.request_snapshot.recommendation_target.source_learning_need_ref
        ):
            raise ValueError("recommendation_execution_snapshot_inconsistent")
        return self


class RecommendationExecutionCreateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution: RecommendationExecutionRecord
    created: bool
