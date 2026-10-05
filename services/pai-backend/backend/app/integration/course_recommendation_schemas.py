import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.capability_governance.course_projection import GovernedCourseProjectionResult
from app.capability_governance.target_adapter import GovernedRecommendationTargetProjection


class CourseRecommendationExecutionCreateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_key: str = Field(min_length=1, max_length=128)
    target_projection: GovernedRecommendationTargetProjection
    course_projections: tuple[GovernedCourseProjectionResult, ...] = Field(max_length=200)
    max_results: int = Field(default=5, ge=1, le=20)

    @field_validator("target_projection", mode="before")
    @classmethod
    def parse_target_projection(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return GovernedRecommendationTargetProjection.model_validate_json(json.dumps(value))
        return value

    @field_validator("course_projections", mode="before")
    @classmethod
    def parse_course_projections(cls, value: Any) -> Any:
        if isinstance(value, list):
            return tuple(
                GovernedCourseProjectionResult.model_validate_json(json.dumps(item))
                for item in value
            )
        return value

    @field_validator("request_key")
    @classmethod
    def validate_request_key(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("request_key must be exact and non-blank")
        return value
