from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.capability_analysis.integration_seed import (
    SENTINEL_REQUIREMENT_ID,
    seed_real_cv_capability_target,
)
from app.extraction.models import ExtractionJobRecord, ExtractionProfileRecord
from app.matching.models import RoleCompetencyProfileRecord
from app.shared.database import Base


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_creates_accepted_jd_and_active_target_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first = await seed_real_cv_capability_target(session_factory)
    second = await seed_real_cv_capability_target(session_factory)

    assert second == first
    assert first.target_profile_id == "seed-real-cv-capability-target"
    async with session_factory() as session:
        job = await session.get(ExtractionJobRecord, "seed-real-cv-capability-jd-job")
        source = await session.get(ExtractionProfileRecord, first.source_jd_profile_id)
        target = await session.scalar(
            select(RoleCompetencyProfileRecord).where(
                RoleCompetencyProfileRecord.id == first.target_profile_id,
                RoleCompetencyProfileRecord.version == first.target_profile_version,
            )
        )

    assert job is not None
    assert job.status == "succeeded"
    assert source is not None
    assert source.review_state == "accepted"
    assert source.document_kind == "jd"
    assert target is not None
    assert target.status == "active"
    assert any(item["id"] == SENTINEL_REQUIREMENT_ID for item in target.requirements)


@pytest.mark.asyncio
async def test_seed_rejects_conflicting_target_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await seed_real_cv_capability_target(session_factory)
    async with session_factory() as session, session.begin():
        target = await session.scalar(
            select(RoleCompetencyProfileRecord).where(
                RoleCompetencyProfileRecord.id == "seed-real-cv-capability-target"
            )
        )
        assert target is not None
        target.requirements = []

    with pytest.raises(ValueError, match="seed target conflict"):
        await seed_real_cv_capability_target(session_factory)
