"""Pure deterministic course recommendation domain service."""

from app.course_recommendation.engine import CourseRecommendationEngine
from app.course_recommendation.schemas import (
    CandidateRejectionReason,
    CourseRecommendationCandidate,
    CourseRecommendationItem,
    CourseRecommendationRequest,
    CourseRecommendationResult,
    CoverageStatus,
    LevelCompatibility,
    PrerequisiteStatus,
    RecommendationTarget,
    candidate_from_profile,
)

__all__ = [
    "CandidateRejectionReason",
    "CourseRecommendationCandidate",
    "CourseRecommendationEngine",
    "CourseRecommendationItem",
    "CourseRecommendationRequest",
    "CourseRecommendationResult",
    "CoverageStatus",
    "LevelCompatibility",
    "PrerequisiteStatus",
    "RecommendationTarget",
    "candidate_from_profile",
]
