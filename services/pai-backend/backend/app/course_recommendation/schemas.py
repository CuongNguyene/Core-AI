"""Recommendation contracts built from governed course semantic facts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.course_catalog.schemas import (
    CourseAvailability,
    CourseCapabilityProfile,
    CourseProfileStatus,
    CourseProvenance,
    CourseSourceType,
    NormalizedCourseCandidate,
)


class CoverageStatus(StrEnum):
    FULL_COVERAGE = "FULL_COVERAGE"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    NO_COVERAGE = "NO_COVERAGE"


class PrerequisiteStatus(StrEnum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class LevelCompatibility(StrEnum):
    EXACT = "EXACT"
    COMPATIBLE = "COMPATIBLE"
    DIFFERENT = "DIFFERENT"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CandidateRejectionReason(StrEnum):
    PROFILE_NOT_ACTIVE = "PROFILE_NOT_ACTIVE"
    NO_SEMANTIC_CAPABILITIES = "NO_SEMANTIC_CAPABILITIES"
    NO_CAPABILITY_MATCH = "NO_CAPABILITY_MATCH"
    COURSE_UNAVAILABLE = "COURSE_UNAVAILABLE"
    PREREQUISITE_UNSATISFIED = "PREREQUISITE_UNSATISFIED"
    INVALID_CANDIDATE = "INVALID_CANDIDATE"


class RecommendationPrerequisiteContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    known_capability_refs: list[str] = Field(default_factory=list)
    known_capability_levels: dict[str, str] = Field(default_factory=dict)
    completed_course_refs: list[str] = Field(default_factory=list)
    provider_conditions: dict[str, bool] = Field(default_factory=dict)


class RecommendationTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    target_ref: str = Field(min_length=1)
    target_capability_refs: list[str] = Field(default_factory=list)
    target_level: str | None = Field(default=None, min_length=1)
    source_learning_need_ref: str | None = Field(default=None, min_length=1)
    source_learning_path_ref: str | None = Field(default=None, min_length=1)
    source_path_step_ref: str | None = Field(default=None, min_length=1)
    source_gap_refs: list[str] = Field(default_factory=list)
    source_role_requirement_refs: list[str] = Field(default_factory=list)
    prerequisite_context: RecommendationPrerequisiteContext = Field(
        default_factory=RecommendationPrerequisiteContext
    )

    @model_validator(mode="after")
    def validate_capability_refs(self) -> RecommendationTarget:
        if len(self.target_capability_refs) != len(set(self.target_capability_refs)):
            raise ValueError("target capability refs must be unique")
        return self


class CourseRecommendationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    course: NormalizedCourseCandidate
    profile_status: CourseProfileStatus


class CourseRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    recommendation_target: RecommendationTarget
    candidates: list[CourseRecommendationCandidate] = Field(default_factory=list)
    max_results: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_unique_courses(self) -> CourseRecommendationRequest:
        refs = [item.course.course_ref for item in self.candidates]
        if len(refs) != len(set(refs)):
            raise ValueError("candidate course_ref values must be unique")
        return self


class CoverageDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: CoverageStatus
    matched_target_capability_refs: list[str] = Field(default_factory=list)
    missing_target_capability_refs: list[str] = Field(default_factory=list)


class PrerequisiteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: PrerequisiteStatus
    evaluated_refs: list[str] = Field(default_factory=list)
    unknown_refs: list[str] = Field(default_factory=list)


class DecisionDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    coverage: CoverageDecision
    prerequisites: PrerequisiteDecision
    target_level: LevelCompatibility
    availability: CourseAvailability


class CourseRecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    rank: int = Field(ge=1)
    course_ref: str = Field(min_length=1)
    source_type: CourseSourceType
    provider_ref: str | None = None
    matched_target_capability_refs: list[str] = Field(default_factory=list)
    missing_target_capability_refs: list[str] = Field(default_factory=list)
    coverage_status: CoverageStatus
    prerequisite_status: PrerequisiteStatus
    level_status: LevelCompatibility
    availability: CourseAvailability
    decision_details: DecisionDetails
    warnings: list[str] = Field(default_factory=list)
    provenance: list[CourseProvenance] = Field(min_length=1)


class RecommendationTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    target_ref: str = Field(min_length=1)
    learning_need_ref: str | None = None
    learning_path_ref: str | None = None
    path_step_ref: str | None = None
    gap_refs: list[str] = Field(default_factory=list)
    role_requirement_refs: list[str] = Field(default_factory=list)


class CourseRecommendationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    target_ref: str = Field(min_length=1)
    algorithm_id: str = "deterministic_course_recommendation"
    algorithm_version: str = "0.1"
    recommendations: list[CourseRecommendationItem] = Field(default_factory=list)
    rejected_summary: dict[str, int] = Field(default_factory=dict)
    no_suitable_reason: str | None = None
    provenance: RecommendationTrace


def candidate_from_profile(
    profile: CourseCapabilityProfile,
) -> CourseRecommendationCandidate:
    """Project an ACTIVE/DRAFT/DEPRECATED profile into the engine input."""
    return CourseRecommendationCandidate(
        course=profile.to_normalized_candidate(),
        profile_status=profile.status,
    )
