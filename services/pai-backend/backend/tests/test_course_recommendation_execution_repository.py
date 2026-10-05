from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import test_course_rec_3d6_end_to_end as fixtures
import test_governed_target_adapter as target_fixtures
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.course_recommendation.engine import CourseRecommendationEngine
from app.course_recommendation.execution_schemas import RecommendationExecutionRecord
from app.course_recommendation.execution_snapshots import (
    build_execution_snapshots,
    request_fingerprint,
)
from app.course_recommendation.models import CourseRecommendationExecutionRecord as ORMRecord
from app.course_recommendation.repository import (
    RecommendationIdempotencyConflict,
    SqlAlchemyCourseRecommendationExecutionRepository,
)
from app.shared.database import Base


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _execution(*, key: str = "req-1", org=None, actor=None) -> RecommendationExecutionRecord:
    release = target_fixtures._active_release()
    target, _ = fixtures._target_projection((fixtures.CAPABILITY_COMMUNICATION,), release)
    _, course, _, _ = fixtures._course_projection(
        course_ref="skillscommons:course-repository",
        capability_refs=(fixtures.CAPABILITY_COMMUNICATION,),
        release=release,
    )
    request, governance = build_execution_snapshots(target, (course,))
    result = CourseRecommendationEngine().recommend(request)
    return RecommendationExecutionRecord(
        id="crx_test_1",
        request_key=key,
        request_fingerprint=request_fingerprint(request, governance),
        algorithm_id=result.algorithm_id,
        algorithm_version=result.algorithm_version,
        result_kind="recommendations" if result.recommendations else "no_suitable_course",
        target_ref=result.target_ref,
        source_learning_need_ref=request.recommendation_target.source_learning_need_ref,
        organization_ref=org or uuid4(),
        actor_ref=actor or uuid4(),
        request_snapshot=request,
        result_snapshot=result,
        governance_snapshot=governance,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_create_read_and_idempotency_scope(session_factory) -> None:
    repository = SqlAlchemyCourseRecommendationExecutionRepository(session_factory)
    original = _execution()

    created = await repository.create_or_get(original)
    replay = await repository.create_or_get(original.model_copy(update={"id": "crx_other"}))
    loaded = await repository.get(original.id)

    assert created.created is True
    assert replay.created is False
    assert replay.execution.id == original.id
    assert loaded == original
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ORMRecord)) == 1


@pytest.mark.asyncio
async def test_same_scope_key_with_changed_fingerprint_conflicts(session_factory) -> None:
    repository = SqlAlchemyCourseRecommendationExecutionRepository(session_factory)
    original = _execution()
    await repository.create_or_get(original)
    changed = original.model_copy(
        update={"id": "crx_other", "request_fingerprint": "sha256:" + "0" * 64}
    )

    with pytest.raises(RecommendationIdempotencyConflict):
        await repository.create_or_get(changed)


@pytest.mark.asyncio
async def test_same_key_in_different_actor_scope_is_independent(session_factory) -> None:
    repository = SqlAlchemyCourseRecommendationExecutionRepository(session_factory)
    original = _execution()
    await repository.create_or_get(original)
    other_actor = original.model_copy(update={"id": "crx_actor_2", "actor_ref": uuid4()})

    result = await repository.create_or_get(other_actor)

    assert result.created is True
    assert result.execution.id == "crx_actor_2"
