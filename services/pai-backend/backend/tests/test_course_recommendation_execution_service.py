from __future__ import annotations

from uuid import uuid4

import pytest
import test_course_rec_3d6_end_to_end as fixtures
import test_governed_target_adapter as target_fixtures

from app.authorization.schemas import ActorContext, Role
from app.course_recommendation.engine import CourseRecommendationEngine
from app.course_recommendation.execution_schemas import (
    RecommendationExecutionCreateResult,
    RecommendationExecutionRecord,
)
from app.course_recommendation.execution_service import (
    CourseRecommendationExecutionService,
    RecommendationExecutionAccessDeniedError,
    RecommendationExecutionNotFoundError,
)
from app.course_recommendation.execution_snapshots import RecommendationSnapshotInconsistent
from app.course_recommendation.repository import RecommendationIdempotencyConflict


class MemoryRepository:
    def __init__(self) -> None:
        self.rows = {}
        self.run_count = 0

    @staticmethod
    def allocate_id() -> str:
        return f"crx_{uuid4().hex}"

    async def get_by_scope_key(self, *, organization_ref, actor_ref, request_key):
        return next(
            (
                row
                for row in self.rows.values()
                if row.organization_ref == organization_ref
                and row.actor_ref == actor_ref
                and row.request_key == request_key
            ),
            None,
        )

    async def create_or_get(self, execution: RecommendationExecutionRecord):
        existing = await self.get_by_scope_key(
            organization_ref=execution.organization_ref,
            actor_ref=execution.actor_ref,
            request_key=execution.request_key,
        )
        if existing:
            if existing.request_fingerprint != execution.request_fingerprint:
                raise RecommendationIdempotencyConflict("recommendation_idempotency_conflict")
            return RecommendationExecutionCreateResult(execution=existing, created=False)
        self.rows[execution.id] = execution
        return RecommendationExecutionCreateResult(execution=execution, created=True)

    async def get(self, execution_id):
        return self.rows.get(execution_id)


class CountingEngine(CourseRecommendationEngine):
    def recommend(self, request):
        self.calls = getattr(self, "calls", 0) + 1
        return super().recommend(request)


def _inputs(course=True):
    release = target_fixtures._active_release()
    target, _ = fixtures._target_projection((fixtures.CAPABILITY_COMMUNICATION,), release)
    courses = ()
    if course:
        _, projection, _, _ = fixtures._course_projection(
            course_ref="skillscommons:service-test",
            capability_refs=(fixtures.CAPABILITY_COMMUNICATION,),
            release=release,
        )
        courses = (projection,)
    return target, courses


def _actor(*, actor=None, org=None, roles=frozenset({Role.LEARNER})):
    return ActorContext(actor_id=actor or uuid4(), organization_id=org or uuid4(), roles=roles)


@pytest.mark.asyncio
async def test_executes_once_and_replays_immutable_snapshot() -> None:
    repository = MemoryRepository()
    engine = CountingEngine()
    service = CourseRecommendationExecutionService(repository=repository, engine=engine)
    actor = _actor()
    target, courses = _inputs()

    first = await service.execute(
        target_projection=target,
        course_projections=courses,
        max_results=5,
        request_key="same-key",
        actor=actor,
    )
    replay = await service.execute(
        target_projection=target,
        course_projections=courses,
        max_results=5,
        request_key="same-key",
        actor=actor,
    )

    assert first.created is True
    assert replay.created is False
    assert replay.execution.id == first.execution.id
    assert engine.calls == 1
    assert replay.execution.algorithm_id == CourseRecommendationEngine.algorithm_id
    historical = await service.get(first.execution.id, actor)
    assert historical == first.execution
    assert engine.calls == 1


@pytest.mark.asyncio
async def test_no_suitable_course_is_a_successful_persisted_result() -> None:
    repository = MemoryRepository()
    service = CourseRecommendationExecutionService(repository=repository)
    result = await service.execute(
        target_projection=_inputs(course=False)[0],
        course_projections=(),
        max_results=5,
        request_key="no-course",
        actor=_actor(),
    )

    assert result.created
    assert result.execution.result_snapshot.no_suitable_reason == "NO_SUITABLE_COURSE"
    assert result.execution.result_kind == "no_suitable_course"


@pytest.mark.asyncio
async def test_multi_capability_execution_preserves_target_and_result_details() -> None:
    release = target_fixtures._active_release()
    target, _ = fixtures._target_projection(
        (fixtures.CAPABILITY_COMMUNICATION, fixtures.CAPABILITY_WRITING), release
    )
    _, course, _, _ = fixtures._course_projection(
        course_ref="skillscommons:multi-capability",
        capability_refs=(fixtures.CAPABILITY_COMMUNICATION, fixtures.CAPABILITY_WRITING),
        release=release,
    )
    service = CourseRecommendationExecutionService(repository=MemoryRepository())

    result = await service.execute(
        target_projection=target,
        course_projections=(course,),
        max_results=5,
        request_key="multi-capability",
        actor=_actor(),
    )

    recommendation = result.execution.result_snapshot.recommendations[0]
    assert set(result.execution.request_snapshot.recommendation_target.target_capability_refs) == {
        fixtures.CAPABILITY_COMMUNICATION,
        fixtures.CAPABILITY_WRITING,
    }
    assert set(recommendation.matched_target_capability_refs) == {
        fixtures.CAPABILITY_COMMUNICATION,
        fixtures.CAPABILITY_WRITING,
    }
    assert len(result.execution.governance_snapshot.target.definition_pins) == 2


@pytest.mark.asyncio
async def test_read_is_owner_scoped_except_existing_admin_role() -> None:
    repository = MemoryRepository()
    service = CourseRecommendationExecutionService(repository=repository)
    actor = _actor()
    result = await service.execute(
        target_projection=_inputs(course=False)[0],
        course_projections=(),
        max_results=5,
        request_key="read-scope",
        actor=actor,
    )

    with pytest.raises(RecommendationExecutionAccessDeniedError):
        await service.get(result.execution.id, _actor(actor=uuid4(), org=actor.organization_id))
    admin = _actor(actor=uuid4(), org=actor.organization_id, roles=frozenset({Role.ADMIN}))
    assert await service.get(result.execution.id, admin) == result.execution
    with pytest.raises(RecommendationExecutionNotFoundError):
        await service.get(
            result.execution.id, _actor(actor=uuid4(), org=uuid4(), roles=frozenset({Role.ADMIN}))
        )


@pytest.mark.asyncio
async def test_engine_failure_does_not_persist_partial_execution() -> None:
    class FailingEngine(CourseRecommendationEngine):
        def recommend(self, request):
            raise RuntimeError("engine failed")

    repository = MemoryRepository()
    service = CourseRecommendationExecutionService(repository=repository, engine=FailingEngine())
    target, courses = _inputs()
    with pytest.raises(RuntimeError, match="engine failed"):
        await service.execute(
            target_projection=target,
            course_projections=courses,
            max_results=5,
            request_key="failure",
            actor=_actor(),
        )
    assert repository.rows == {}


@pytest.mark.asyncio
async def test_persisted_request_result_and_provenance_are_bounded() -> None:
    repository = MemoryRepository()
    service = CourseRecommendationExecutionService(repository=repository)
    target, courses = _inputs()
    projection = courses[0]
    candidate = projection.normalized_candidate
    assert candidate is not None
    provenance = candidate.provenance[0].model_copy(update={"evidence_text": "x" * 550_000})
    oversized_candidate = candidate.model_copy(update={"provenance": [provenance]})
    oversized_projection = projection.model_copy(
        update={"normalized_candidate": oversized_candidate}
    )

    with pytest.raises(RecommendationSnapshotInconsistent, match="snapshot_size_exceeded"):
        await service.execute(
            target_projection=target,
            course_projections=(oversized_projection,),
            max_results=5,
            request_key="oversized",
            actor=_actor(),
        )
    assert repository.rows == {}
