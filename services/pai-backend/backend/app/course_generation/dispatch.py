from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.content_generation.models import CourseGenerationDispatchRecord


class CourseGenerationDispatchStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class CourseGenerationDispatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    plan_ref: str = Field(min_length=1)
    actor_id: UUID
    task_statuses: tuple[str, ...] = Field(default=("PENDING",), min_length=1)
    assemble_result: bool = True
    status: CourseGenerationDispatchStatus = CourseGenerationDispatchStatus.QUEUED
    attempt_count: int = Field(default=0, ge=0)
    lease_expires_at: datetime | None = None
    queued_at: datetime
    finished_at: datetime | None = None


class SqlAlchemyCourseGenerationDispatchRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, dispatch: CourseGenerationDispatch) -> CourseGenerationDispatch:
        async with self._session_factory() as session, session.begin():
            if await session.get(CourseGenerationDispatchRecord, dispatch.plan_ref) is not None:
                raise ValueError("course_generation_dispatch_exists")
            session.add(self._record(dispatch))
        return dispatch

    async def claim(
        self, plan_ref: str, *, now: datetime | None = None, lease_seconds: int = 900
    ) -> CourseGenerationDispatch | None:
        current_time = now or datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            record = await session.scalar(
                select(CourseGenerationDispatchRecord)
                .where(CourseGenerationDispatchRecord.plan_ref == plan_ref)
                .with_for_update()
            )
            if record is None or not self._claimable(record, current_time):
                return None
            record.status = CourseGenerationDispatchStatus.RUNNING.value
            record.attempt_count += 1
            record.lease_expires_at = current_time + timedelta(seconds=lease_seconds)
            record.finished_at = None
            await session.flush()
            return self._from_record(record)

    async def finish(self, plan_ref: str, *, succeeded: bool, now: datetime | None = None) -> None:
        async with self._session_factory() as session, session.begin():
            record = await session.get(
                CourseGenerationDispatchRecord, plan_ref, with_for_update=True
            )
            if record is None:
                raise KeyError(plan_ref)
            record.status = (
                CourseGenerationDispatchStatus.SUCCEEDED.value
                if succeeded
                else CourseGenerationDispatchStatus.FAILED.value
            )
            record.lease_expires_at = None
            record.finished_at = now or datetime.now(UTC)

    async def requeue(
        self,
        plan_ref: str,
        *,
        task_statuses: tuple[str, ...],
        assemble_result: bool,
        now: datetime | None = None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            record = await session.get(
                CourseGenerationDispatchRecord, plan_ref, with_for_update=True
            )
            if record is None:
                raise KeyError(plan_ref)
            current_time = now or datetime.now(UTC)
            if record.status == CourseGenerationDispatchStatus.RUNNING.value and (
                record.lease_expires_at is None
                or _as_utc(record.lease_expires_at) > _as_utc(current_time)
            ):
                raise RuntimeError("course_generation_dispatch_already_running")
            record.status = CourseGenerationDispatchStatus.QUEUED.value
            record.task_statuses = list(task_statuses)
            record.assemble_result = assemble_result
            record.lease_expires_at = None
            record.finished_at = None
            record.queued_at = current_time

    async def list_reconcilable(
        self, *, now: datetime | None = None, queue_after_seconds: int = 60
    ) -> list[CourseGenerationDispatch]:
        current_time = now or datetime.now(UTC)
        queued_before = current_time - timedelta(seconds=queue_after_seconds)
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(CourseGenerationDispatchRecord).where(
                        or_(
                            (
                                CourseGenerationDispatchRecord.status
                                == CourseGenerationDispatchStatus.QUEUED.value
                            )
                            & (CourseGenerationDispatchRecord.queued_at <= queued_before),
                            (
                                CourseGenerationDispatchRecord.status
                                == CourseGenerationDispatchStatus.RUNNING.value
                            )
                            & (CourseGenerationDispatchRecord.lease_expires_at <= current_time),
                        )
                    )
                )
            ).all()
        return [self._from_record(record) for record in records]

    @staticmethod
    def _claimable(record: CourseGenerationDispatchRecord, now: datetime) -> bool:
        return record.status == CourseGenerationDispatchStatus.QUEUED.value or (
            record.status == CourseGenerationDispatchStatus.RUNNING.value
            and record.lease_expires_at is not None
            and _as_utc(record.lease_expires_at) <= _as_utc(now)
        )

    @staticmethod
    def _record(dispatch: CourseGenerationDispatch) -> CourseGenerationDispatchRecord:
        return CourseGenerationDispatchRecord(**dispatch.model_dump())

    @staticmethod
    def _from_record(record: CourseGenerationDispatchRecord) -> CourseGenerationDispatch:
        return CourseGenerationDispatch(
            plan_ref=record.plan_ref,
            actor_id=record.actor_id,
            task_statuses=tuple(record.task_statuses),
            assemble_result=record.assemble_result,
            status=CourseGenerationDispatchStatus(record.status),
            attempt_count=record.attempt_count,
            lease_expires_at=record.lease_expires_at,
            queued_at=record.queued_at,
            finished_at=record.finished_at,
        )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
