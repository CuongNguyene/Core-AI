from typing import Protocol, cast

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import Select

from .brief_revision_schemas import AuthoringBriefRevision
from .models import AuthoringBriefRevisionRecord


def latest_revision_statement(
    request_id: str,
) -> Select[tuple[AuthoringBriefRevisionRecord]]:
    return (
        select(AuthoringBriefRevisionRecord)
        .where(AuthoringBriefRevisionRecord.request_id == request_id)
        .order_by(desc(AuthoringBriefRevisionRecord.version))
        .limit(1)
    )


class AuthoringBriefRevisionRepository(Protocol):
    async def create(self, revision: AuthoringBriefRevision) -> AuthoringBriefRevision: ...
    async def get(self, revision_id: str) -> AuthoringBriefRevision | None: ...
    async def list(self, request_id: str) -> list[AuthoringBriefRevision]: ...
    async def latest(self, request_id: str) -> AuthoringBriefRevision | None: ...
    async def update(self, revision: AuthoringBriefRevision) -> AuthoringBriefRevision: ...


class InMemoryAuthoringBriefRevisionRepository:
    def __init__(self) -> None:
        self._revisions: dict[str, AuthoringBriefRevision] = {}

    async def create(self, revision: AuthoringBriefRevision) -> AuthoringBriefRevision:
        if revision.id in self._revisions:
            raise ValueError("authoring_revision_immutable")
        self._revisions[revision.id] = revision.model_copy(deep=True)
        return revision.model_copy(deep=True)

    async def get(self, revision_id: str) -> AuthoringBriefRevision | None:
        revision = self._revisions.get(revision_id)
        return revision.model_copy(deep=True) if revision else None

    async def list(self, request_id: str) -> list[AuthoringBriefRevision]:
        return [
            item.model_copy(deep=True)
            for item in sorted(
                (item for item in self._revisions.values() if item.request_id == request_id),
                key=lambda item: item.version,
                reverse=True,
            )
        ]

    async def latest(self, request_id: str) -> AuthoringBriefRevision | None:
        revisions = await self.list(request_id)
        return revisions[0] if revisions else None

    async def update(self, revision: AuthoringBriefRevision) -> AuthoringBriefRevision:
        if revision.id not in self._revisions:
            raise KeyError(revision.id)
        self._revisions[revision.id] = revision.model_copy(deep=True)
        return revision.model_copy(deep=True)


class SqlAlchemyAuthoringBriefRevisionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, revision: AuthoringBriefRevision) -> AuthoringBriefRevision:
        async with self._session_factory() as session, session.begin():
            if await session.get(AuthoringBriefRevisionRecord, revision.id) is not None:
                raise ValueError("authoring_revision_immutable")
            session.add(AuthoringBriefRevisionRecord.from_domain(revision))
        return revision.model_copy(deep=True)

    async def get(self, revision_id: str) -> AuthoringBriefRevision | None:
        async with self._session_factory() as session:
            record = cast(
                AuthoringBriefRevisionRecord | None,
                await session.get(AuthoringBriefRevisionRecord, revision_id),
            )
            return record.to_domain() if record else None

    async def list(self, request_id: str) -> list[AuthoringBriefRevision]:
        async with self._session_factory() as session:
            records = (await session.scalars(
                select(AuthoringBriefRevisionRecord)
                .where(AuthoringBriefRevisionRecord.request_id == request_id)
                .order_by(desc(AuthoringBriefRevisionRecord.version))
            )).all()
            return [record.to_domain() for record in records]

    async def latest(self, request_id: str) -> AuthoringBriefRevision | None:
        async with self._session_factory() as session:
            record = await session.scalar(latest_revision_statement(request_id))
            return record.to_domain() if record else None

    async def update(self, revision: AuthoringBriefRevision) -> AuthoringBriefRevision:
        async with self._session_factory() as session, session.begin():
            record = cast(
                AuthoringBriefRevisionRecord | None,
                await session.get(AuthoringBriefRevisionRecord, revision.id),
            )
            if record is None:
                raise KeyError(revision.id)
            record.apply_domain(revision)
        return revision.model_copy(deep=True)
