from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.authorization.fixtures import REVIEWER_ID
from app.extraction.fixtures import FixtureDocumentSource
from app.extraction.models import ExtractionAuditEventRecord
from app.extraction.repository import SqlAlchemyExtractionRepository
from app.extraction.schemas import ReviewState
from app.shared.database import Base
from tests.test_extraction_repository import pending_profile, queued_job


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_repository_accepts_profile_and_appends_safe_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyExtractionRepository(session_factory, FixtureDocumentSource.default())
    await repository.enqueue(queued_job())
    await repository.mark_succeeded("job-1", pending_profile())

    accepted = await repository.accept_profile("profile-1", REVIEWER_ID, expected_version=1)

    assert accepted.review_state is ReviewState.ACCEPTED
    async with session_factory() as session:
        audit_events = list((await session.scalars(select(ExtractionAuditEventRecord))).all())
    assert len(audit_events) == 1
    assert audit_events[0].action == "EXTRACTION_PROFILE_ACCEPTED"
    assert "document" not in audit_events[0].audit_metadata


@pytest.mark.asyncio
async def test_sql_repository_rolls_back_acceptance_when_audit_write_fails(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = SqlAlchemyExtractionRepository(session_factory, FixtureDocumentSource.default())
    await repository.enqueue(queued_job())
    await repository.mark_succeeded("job-1", pending_profile())

    async def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(repository, "_append_audit", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await repository.accept_profile("profile-1", "reviewer-1", expected_version=1)

    stored = await repository.get_profile("profile-1")
    assert stored is not None
    assert stored.review_state is ReviewState.PENDING_REVIEW


@pytest.mark.asyncio
async def test_sql_repository_fails_closed_when_source_is_missing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    setup_repository = SqlAlchemyExtractionRepository(
        session_factory, FixtureDocumentSource.default()
    )
    await setup_repository.enqueue(queued_job())
    await setup_repository.mark_succeeded("job-1", pending_profile())
    repository = SqlAlchemyExtractionRepository(session_factory, FixtureDocumentSource([]))

    with pytest.raises(KeyError):
        await repository.accept_profile("profile-1", "reviewer-1", expected_version=1)

    stored = await setup_repository.get_profile("profile-1")
    assert stored is not None
    assert stored.review_state is ReviewState.PENDING_REVIEW
