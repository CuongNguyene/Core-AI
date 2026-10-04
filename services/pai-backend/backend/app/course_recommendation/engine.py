"""Pure, deterministic, explainable course recommendation engine."""

from __future__ import annotations

from dataclasses import dataclass

from app.course_catalog.schemas import CourseAvailability, CourseProfileStatus
from app.course_recommendation.schemas import (
    CandidateRejectionReason,
    CourseRecommendationCandidate,
    CourseRecommendationItem,
    CourseRecommendationRequest,
    CourseRecommendationResult,
    CoverageDecision,
    CoverageStatus,
    DecisionDetails,
    LevelCompatibility,
    PrerequisiteDecision,
    PrerequisiteStatus,
    RecommendationTarget,
    RecommendationTrace,
)


@dataclass(frozen=True)
class _EvaluatedCandidate:
    candidate: CourseRecommendationCandidate
    coverage: CoverageDecision
    prerequisite: PrerequisiteDecision
    level: LevelCompatibility
    warnings: tuple[str, ...]

    @property
    def rank_key(self) -> tuple[int, int, int, int, int, str]:
        coverage_rank = {
            CoverageStatus.FULL_COVERAGE: 2,
            CoverageStatus.PARTIAL_COVERAGE: 1,
            CoverageStatus.NO_COVERAGE: 0,
        }[self.coverage.status]
        prerequisite_rank = {
            PrerequisiteStatus.SATISFIED: 2,
            PrerequisiteStatus.NOT_APPLICABLE: 1,
            PrerequisiteStatus.UNKNOWN: 0,
            PrerequisiteStatus.UNSATISFIED: -1,
        }[self.prerequisite.status]
        level_rank = {
            LevelCompatibility.EXACT: 2,
            LevelCompatibility.COMPATIBLE: 1,
            LevelCompatibility.UNKNOWN: 0,
            LevelCompatibility.DIFFERENT: 0,
            LevelCompatibility.NOT_APPLICABLE: 0,
        }[self.level]
        availability_rank = (
            1 if self.candidate.course.availability is CourseAvailability.AVAILABLE else 0
        )
        return (
            -coverage_rank,
            -len(self.coverage.matched_target_capability_refs),
            -prerequisite_rank,
            -level_rank,
            -availability_rank,
            self.candidate.course.course_ref,
        )


class CourseRecommendationEngine:
    """Evaluate governed candidates for an explicit recommendation target."""

    algorithm_id = "deterministic_course_recommendation"
    algorithm_version = "0.1"

    def recommend(self, request: CourseRecommendationRequest) -> CourseRecommendationResult:
        target = request.recommendation_target
        rejected: dict[str, int] = {}
        evaluated: list[_EvaluatedCandidate] = []

        if not target.target_capability_refs:
            rejected["NO_TARGET_CAPABILITIES"] = len(request.candidates)
            return self._result(request, [], rejected, "NO_TARGET_CAPABILITIES")

        for candidate in sorted(request.candidates, key=lambda item: item.course.course_ref):
            reason = self._eligibility_reason(candidate, target)
            if reason is not None:
                rejected[reason.value] = rejected.get(reason.value, 0) + 1
                continue
            evaluation = self._evaluate(candidate, target)
            if evaluation.coverage.status is CoverageStatus.NO_COVERAGE:
                rejected[CandidateRejectionReason.NO_CAPABILITY_MATCH.value] = (
                    rejected.get(CandidateRejectionReason.NO_CAPABILITY_MATCH.value, 0) + 1
                )
                continue
            if evaluation.prerequisite.status is PrerequisiteStatus.UNSATISFIED:
                rejected[CandidateRejectionReason.PREREQUISITE_UNSATISFIED.value] = (
                    rejected.get(CandidateRejectionReason.PREREQUISITE_UNSATISFIED.value, 0) + 1
                )
                continue
            evaluated.append(evaluation)

        ordered = sorted(evaluated, key=lambda item: item.rank_key)
        selected = ordered[: request.max_results]
        recommendations = [self._item(item, rank) for rank, item in enumerate(selected, start=1)]
        no_suitable_reason = "NO_SUITABLE_COURSE" if not recommendations else None
        return self._result(request, recommendations, rejected, no_suitable_reason)

    def _eligibility_reason(
        self,
        candidate: CourseRecommendationCandidate,
        target: RecommendationTarget,
    ) -> CandidateRejectionReason | None:
        if candidate.profile_status is not CourseProfileStatus.ACTIVE:
            return CandidateRejectionReason.PROFILE_NOT_ACTIVE
        if not candidate.course.capabilities:
            return CandidateRejectionReason.NO_SEMANTIC_CAPABILITIES
        if candidate.course.availability is CourseAvailability.UNAVAILABLE:
            return CandidateRejectionReason.COURSE_UNAVAILABLE
        return None

    def _evaluate(
        self,
        candidate: CourseRecommendationCandidate,
        target: RecommendationTarget,
    ) -> _EvaluatedCandidate:
        target_refs = tuple(target.target_capability_refs)
        candidate_refs = {item.capability_ref for item in candidate.course.capabilities}
        matched = [ref for ref in target_refs if ref in candidate_refs]
        missing = [ref for ref in target_refs if ref not in candidate_refs]
        if not matched:
            coverage_status = CoverageStatus.NO_COVERAGE
        elif not missing:
            coverage_status = CoverageStatus.FULL_COVERAGE
        else:
            coverage_status = CoverageStatus.PARTIAL_COVERAGE
        coverage = CoverageDecision(
            status=coverage_status,
            matched_target_capability_refs=matched,
            missing_target_capability_refs=missing,
        )
        prerequisite = self._prerequisite_decision(candidate, target)
        level = self._level_compatibility(candidate.course.target_level, target.target_level)
        warnings: list[str] = []
        if candidate.course.availability is CourseAvailability.UNKNOWN:
            warnings.append("AVAILABILITY_UNKNOWN")
        if prerequisite.status is PrerequisiteStatus.UNKNOWN:
            warnings.append("PREREQUISITE_STATUS_UNKNOWN")
        if level in {LevelCompatibility.UNKNOWN, LevelCompatibility.DIFFERENT}:
            warnings.append(f"TARGET_LEVEL_{level.value}")
        return _EvaluatedCandidate(candidate, coverage, prerequisite, level, tuple(warnings))

    def _prerequisite_decision(
        self,
        candidate: CourseRecommendationCandidate,
        target: RecommendationTarget,
    ) -> PrerequisiteDecision:
        prerequisites = candidate.course.prerequisites
        if not prerequisites:
            return PrerequisiteDecision(status=PrerequisiteStatus.NOT_APPLICABLE)
        context = target.prerequisite_context
        statuses: list[PrerequisiteStatus] = []
        evaluated_refs: list[str] = []
        unknown_refs: list[str] = []
        for prerequisite in prerequisites:
            evaluated_refs.append(prerequisite.ref)
            status = PrerequisiteStatus.UNKNOWN
            if prerequisite.kind == "capability":
                if context.known_capability_refs:
                    status = (
                        PrerequisiteStatus.SATISFIED
                        if prerequisite.ref in context.known_capability_refs
                        else PrerequisiteStatus.UNSATISFIED
                    )
                if prerequisite.minimum_level:
                    known_level = context.known_capability_levels.get(prerequisite.ref)
                    status = (
                        (
                            PrerequisiteStatus.SATISFIED
                            if known_level == prerequisite.minimum_level
                            else PrerequisiteStatus.UNKNOWN
                        )
                        if known_level is not None
                        else PrerequisiteStatus.UNKNOWN
                    )
            elif prerequisite.kind == "course":
                if context.completed_course_refs:
                    status = (
                        PrerequisiteStatus.SATISFIED
                        if prerequisite.ref in context.completed_course_refs
                        else PrerequisiteStatus.UNSATISFIED
                    )
            elif prerequisite.kind == "provider_condition":
                if prerequisite.ref in context.provider_conditions:
                    status = (
                        PrerequisiteStatus.SATISFIED
                        if context.provider_conditions[prerequisite.ref]
                        else PrerequisiteStatus.UNSATISFIED
                    )
            if status is PrerequisiteStatus.UNKNOWN:
                unknown_refs.append(prerequisite.ref)
            statuses.append(status)
        if PrerequisiteStatus.UNSATISFIED in statuses:
            overall = PrerequisiteStatus.UNSATISFIED
        elif PrerequisiteStatus.UNKNOWN in statuses:
            overall = PrerequisiteStatus.UNKNOWN
        else:
            overall = PrerequisiteStatus.SATISFIED
        return PrerequisiteDecision(
            status=overall,
            evaluated_refs=evaluated_refs,
            unknown_refs=unknown_refs,
        )

    @staticmethod
    def _level_compatibility(
        candidate_level: str | None, target_level: str | None
    ) -> LevelCompatibility:
        if candidate_level is None and target_level is None:
            return LevelCompatibility.NOT_APPLICABLE
        if candidate_level is None or target_level is None:
            return LevelCompatibility.UNKNOWN
        if candidate_level == target_level:
            return LevelCompatibility.EXACT
        return LevelCompatibility.DIFFERENT

    def _item(self, evaluated: _EvaluatedCandidate, rank: int) -> CourseRecommendationItem:
        course = evaluated.candidate.course
        details = DecisionDetails(
            coverage=evaluated.coverage,
            prerequisites=evaluated.prerequisite,
            target_level=evaluated.level,
            availability=course.availability,
        )
        return CourseRecommendationItem(
            rank=rank,
            course_ref=course.course_ref,
            source_type=course.source_type,
            provider_ref=course.provider_ref,
            matched_target_capability_refs=evaluated.coverage.matched_target_capability_refs,
            missing_target_capability_refs=evaluated.coverage.missing_target_capability_refs,
            coverage_status=evaluated.coverage.status,
            prerequisite_status=evaluated.prerequisite.status,
            level_status=evaluated.level,
            availability=course.availability,
            decision_details=details,
            warnings=list(evaluated.warnings),
            provenance=list(course.provenance),
        )

    def _result(
        self,
        request: CourseRecommendationRequest,
        recommendations: list[CourseRecommendationItem],
        rejected: dict[str, int],
        no_suitable_reason: str | None,
    ) -> CourseRecommendationResult:
        target = request.recommendation_target
        return CourseRecommendationResult(
            target_ref=target.target_ref,
            algorithm_id=self.algorithm_id,
            algorithm_version=self.algorithm_version,
            recommendations=recommendations,
            rejected_summary=rejected,
            no_suitable_reason=no_suitable_reason,
            provenance=RecommendationTrace(
                target_ref=target.target_ref,
                learning_need_ref=target.source_learning_need_ref,
                learning_path_ref=target.source_learning_path_ref,
                path_step_ref=target.source_path_step_ref,
                gap_refs=list(target.source_gap_refs),
                role_requirement_refs=list(target.source_role_requirement_refs),
            ),
        )
