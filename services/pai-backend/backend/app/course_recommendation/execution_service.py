from __future__ import annotations

from datetime import UTC, datetime

from app.authorization.schemas import ActorContext, Role
from app.capability_governance.course_projection import GovernedCourseProjectionResult
from app.capability_governance.target_adapter import GovernedRecommendationTargetProjection
from app.course_recommendation.engine import CourseRecommendationEngine
from app.course_recommendation.execution_schemas import (
    RecommendationExecutionCreateResult,
    RecommendationExecutionRecord,
)
from app.course_recommendation.execution_snapshots import (
    GovernanceSnapshot,
    build_execution_snapshots,
    request_fingerprint,
    validate_execution_snapshot_size,
)
from app.course_recommendation.repository import (
    CourseRecommendationExecutionRepository,
    RecommendationIdempotencyConflict,
)
from app.course_recommendation.schemas import (
    CourseRecommendationRequest,
    CourseRecommendationResult,
)


class RecommendationExecutionNotFoundError(LookupError):
    pass


class RecommendationExecutionAccessDeniedError(PermissionError):
    pass


class CourseRecommendationExecutionService:
    def __init__(
        self,
        *,
        repository: CourseRecommendationExecutionRepository,
        engine: CourseRecommendationEngine | None = None,
    ) -> None:
        self._repository = repository
        self._engine = engine or CourseRecommendationEngine()

    async def execute(
        self,
        *,
        target_projection: GovernedRecommendationTargetProjection,
        course_projections: tuple[GovernedCourseProjectionResult, ...],
        max_results: int,
        request_key: str,
        actor: ActorContext,
    ) -> RecommendationExecutionCreateResult:
        request, governance = build_execution_snapshots(
            target_projection, course_projections, max_results=max_results
        )
        fingerprint = request_fingerprint(request, governance)
        existing = await self._repository.get_by_scope_key(
            organization_ref=actor.organization_id,
            actor_ref=actor.actor_id,
            request_key=request_key,
        )
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise RecommendationIdempotencyConflict("recommendation_idempotency_conflict")
            return RecommendationExecutionCreateResult(execution=existing, created=False)

        # Engine execution is pure and occurs before any insert, so failures cannot leave partial rows.
        result = self._engine.recommend(request)
        validate_execution_snapshot_size(request, result, governance)
        execution = self._record(
            request=request,
            governance=governance,
            result=result,
            request_key=request_key,
            fingerprint=fingerprint,
            actor=actor,
        )
        return await self._repository.create_or_get(execution)

    async def get(self, execution_id: str, actor: ActorContext) -> RecommendationExecutionRecord:
        record = await self._repository.get(execution_id)
        if record is None or record.organization_ref != actor.organization_id:
            raise RecommendationExecutionNotFoundError("recommendation_not_found")
        if record.actor_ref != actor.actor_id and Role.ADMIN not in actor.roles:
            raise RecommendationExecutionAccessDeniedError("recommendation_access_denied")
        return record

    def _record(
        self,
        *,
        request: CourseRecommendationRequest,
        governance: GovernanceSnapshot,
        result: CourseRecommendationResult,
        request_key: str,
        fingerprint: str,
        actor: ActorContext,
    ) -> RecommendationExecutionRecord:
        return RecommendationExecutionRecord(
            id=self._repository.allocate_id(),
            request_key=request_key,
            request_fingerprint=fingerprint,
            algorithm_id=CourseRecommendationEngine.algorithm_id,
            algorithm_version=CourseRecommendationEngine.algorithm_version,
            result_kind=("recommendations" if result.recommendations else "no_suitable_course"),
            target_ref=request.recommendation_target.target_ref,
            source_learning_need_ref=request.recommendation_target.source_learning_need_ref,
            organization_ref=actor.organization_id,
            actor_ref=actor.actor_id,
            request_snapshot=request,
            result_snapshot=result,
            governance_snapshot=governance,
            created_at=datetime.now(UTC),
        )
