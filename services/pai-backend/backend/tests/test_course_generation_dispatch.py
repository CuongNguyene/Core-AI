from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.content_generation.models import CourseGenerationDispatchRecord
from app.course_generation.dispatch import (
    CourseGenerationDispatch,
    CourseGenerationDispatchStatus,
    SqlAlchemyCourseGenerationDispatchRepository,
)
from app.shared.database import Base


@pytest.mark.asyncio
async def test_dispatch_claim_is_exclusive_and_expired_lease_can_be_reclaimed() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                Base.metadata.create_all, tables=[CourseGenerationDispatchRecord.__table__]
            )
        repository = SqlAlchemyCourseGenerationDispatchRepository(
            async_sessionmaker(engine, expire_on_commit=False)
        )
        now = datetime(2026, 9, 25, tzinfo=UTC)
        await repository.create(
            CourseGenerationDispatch(plan_ref="plan-1", actor_id=uuid4(), queued_at=now)
        )

        first = await repository.claim("plan-1", now=now, lease_seconds=30)
        assert first is not None
        assert first.status is CourseGenerationDispatchStatus.RUNNING
        assert await repository.claim("plan-1", now=now + timedelta(seconds=1)) is None

        recovered = await repository.claim("plan-1", now=now + timedelta(seconds=31))
        assert recovered is not None
        assert recovered.attempt_count == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_requeue_persists_the_requested_execution_scope() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                Base.metadata.create_all, tables=[CourseGenerationDispatchRecord.__table__]
            )
        repository = SqlAlchemyCourseGenerationDispatchRepository(
            async_sessionmaker(engine, expire_on_commit=False)
        )
        now = datetime(2026, 9, 25, tzinfo=UTC)
        await repository.create(
            CourseGenerationDispatch(
                plan_ref="plan-2",
                actor_id=uuid4(),
                task_statuses=("PENDING",),
                assemble_result=True,
                queued_at=now,
            )
        )

        await repository.requeue(
            "plan-2", task_statuses=("FAILED",), assemble_result=False, now=now
        )
        claimed = await repository.claim("plan-2", now=now)

        assert claimed is not None
        assert claimed.task_statuses == ("FAILED",)
        assert claimed.assemble_result is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reconcile_lists_old_queued_and_expired_running_dispatches() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                Base.metadata.create_all, tables=[CourseGenerationDispatchRecord.__table__]
            )
        repository = SqlAlchemyCourseGenerationDispatchRepository(
            async_sessionmaker(engine, expire_on_commit=False)
        )
        now = datetime(2026, 9, 25, tzinfo=UTC)
        await repository.create(
            CourseGenerationDispatch(plan_ref="queued", actor_id=uuid4(), queued_at=now)
        )
        await repository.create(
            CourseGenerationDispatch(plan_ref="running", actor_id=uuid4(), queued_at=now)
        )
        assert await repository.claim("running", now=now, lease_seconds=30) is not None

        stale = await repository.list_reconcilable(now=now + timedelta(seconds=61))

        assert {dispatch.plan_ref for dispatch in stale} == {"queued", "running"}
    finally:
        await engine.dispose()
