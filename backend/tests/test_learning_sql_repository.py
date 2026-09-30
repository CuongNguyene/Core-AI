from datetime import UTC

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.learning.repository import SqlAlchemyLearningPathRepository
from app.learning.schemas import LearningPathSourceType, LearningPathStatus
from app.shared.database import Base
from tests.test_learning_repository import path_fixture


@pytest.mark.asyncio
async def test_sql_repository_round_trips_versioned_snapshot() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    repository = SqlAlchemyLearningPathRepository(
        async_sessionmaker(engine, expire_on_commit=False)
    )
    path = path_fixture()

    stored = await repository.create(path)
    loaded = await repository.get(path.id)

    assert stored == path
    assert loaded is not None
    assert loaded.model_dump(exclude={"created_at"}) == path.model_dump(exclude={"created_at"})
    assert loaded.created_at.replace(tzinfo=UTC) == path.created_at
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_repository_persists_review_and_approval_metadata() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    repository = SqlAlchemyLearningPathRepository(
        async_sessionmaker(engine, expire_on_commit=False)
    )
    path = path_fixture().model_copy(
        update={
            "id": "capability-path-1",
            "status": LearningPathStatus.DRAFT,
            "source_type": LearningPathSourceType.CAPABILITY_ANALYSIS,
            "capability_analysis_id": "analysis-1",
            "capability_analysis_version": 1,
            "source_profile_id": "profile-1",
            "source_profile_version": 1,
            "source_target_id": "role-1",
            "source_target_version": "1.0",
        },
        deep=True,
    )
    await repository.create(path)
    reviewed = await repository.review(path.id, path.created_by, expected_version=1)
    approved = await repository.approve(path.id, path.created_by, expected_version=1)

    assert reviewed.reviewed is True
    assert reviewed.reviewed_version == 1
    assert approved.status.value == "active"
    assert approved.approved_version == 1
    await engine.dispose()
