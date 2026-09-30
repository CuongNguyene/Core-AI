import json
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.course_authoring.models import CourseAuthoringRequestRecord

from .schemas import (
    AudienceSnapshot,
    CourseAuthoringMode,
    CourseAuthoringRequest,
    CourseAuthoringStatus,
    TrainingBrief,
)


class CourseAuthoringRepository(Protocol):
    def allocate_ids(self) -> tuple[str, str]: ...

    async def create(
        self, request: CourseAuthoringRequest, *, idempotency_key: str | None = None
    ) -> CourseAuthoringRequest: ...

    async def get(self, request_id: str) -> CourseAuthoringRequest | None: ...

    async def get_by_idempotency_key(self, key: str) -> CourseAuthoringRequest | None: ...

    async def list(self) -> list[CourseAuthoringRequest]: ...


class InMemoryCourseAuthoringRepository:
    def __init__(self) -> None:
        self._requests: dict[str, CourseAuthoringRequest] = {}
        self._idempotency_keys: dict[str, str] = {}
        self._next_id = 1

    def allocate_ids(self) -> tuple[str, str]:
        suffix = f"{self._next_id:03d}"
        self._next_id += 1
        return f"audience-snapshot-{suffix}", f"course-authoring-request-{suffix}"

    async def create(
        self, request: CourseAuthoringRequest, *, idempotency_key: str | None = None
    ) -> CourseAuthoringRequest:
        self._requests[request.id] = request
        if idempotency_key:
            self._idempotency_keys[idempotency_key] = request.id
        return request

    async def get(self, request_id: str) -> CourseAuthoringRequest | None:
        return self._requests.get(request_id)

    async def get_by_idempotency_key(self, key: str) -> CourseAuthoringRequest | None:
        request_id = self._idempotency_keys.get(key)
        return self._requests.get(request_id) if request_id else None

    async def list(self) -> list[CourseAuthoringRequest]:
        return sorted(self._requests.values(), key=lambda item: item.created_at, reverse=True)


class SqlAlchemyCourseAuthoringRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def allocate_ids(self) -> tuple[str, str]:
        import uuid

        suffix = uuid.uuid4().hex
        return f"audience-snapshot-{suffix}", f"course-authoring-request-{suffix}"

    async def create(
        self, request: CourseAuthoringRequest, *, idempotency_key: str | None = None
    ) -> CourseAuthoringRequest:
        async with self._session_factory() as session, session.begin():
            session.add(
                CourseAuthoringRequestRecord(
                    id=request.id,
                    idempotency_key=idempotency_key,
                    title=request.title,
                    training_brief=request.training_brief.model_dump(mode="json"),
                    audience_snapshot=request.audience_snapshot.model_dump(mode="json"),
                    learning_need_refs=list(request.learning_need_refs),
                    objective_refs=list(request.objective_refs),
                    instructional_blueprint_ref=request.instructional_blueprint_ref,
                    constraints=dict(request.constraints),
                    mode=request.mode.value,
                    status=request.status.value,
                    authoring_workflow_version=request.authoring_workflow_version,
                    created_by_actor_ref=request.created_by_actor_ref,
                    created_at=request.created_at,
                )
            )
        return request.model_copy(deep=True)

    async def get(self, request_id: str) -> CourseAuthoringRequest | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CourseAuthoringRequestRecord).where(
                    CourseAuthoringRequestRecord.id == request_id
                )
            )
            if record is None:
                return None
            return CourseAuthoringRequest(
                id=record.id,
                title=record.title,
                training_brief=TrainingBrief.model_validate_json(json.dumps(record.training_brief)),
                audience_snapshot=AudienceSnapshot.model_validate_json(
                    json.dumps(record.audience_snapshot)
                ),
                learning_need_refs=tuple(record.learning_need_refs),
                objective_refs=tuple(record.objective_refs),
                instructional_blueprint_ref=record.instructional_blueprint_ref,
                constraints=dict(record.constraints),
                mode=CourseAuthoringMode(record.mode),
                status=CourseAuthoringStatus(record.status),
                authoring_workflow_version=record.authoring_workflow_version,
                created_by_actor_ref=record.created_by_actor_ref,
                created_at=record.created_at,
            )

    async def get_by_idempotency_key(self, key: str) -> CourseAuthoringRequest | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CourseAuthoringRequestRecord).where(
                    CourseAuthoringRequestRecord.idempotency_key == key
                )
            )
            if record is None:
                return None
            return CourseAuthoringRequest(
                id=record.id,
                title=record.title,
                training_brief=TrainingBrief.model_validate_json(json.dumps(record.training_brief)),
                audience_snapshot=AudienceSnapshot.model_validate_json(
                    json.dumps(record.audience_snapshot)
                ),
                learning_need_refs=tuple(record.learning_need_refs),
                objective_refs=tuple(record.objective_refs),
                instructional_blueprint_ref=record.instructional_blueprint_ref,
                constraints=dict(record.constraints),
                mode=CourseAuthoringMode(record.mode),
                status=CourseAuthoringStatus(record.status),
                authoring_workflow_version=record.authoring_workflow_version,
                created_by_actor_ref=record.created_by_actor_ref,
                created_at=record.created_at,
            )

    async def list(self) -> list[CourseAuthoringRequest]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(CourseAuthoringRequestRecord).order_by(
                        CourseAuthoringRequestRecord.created_at.desc()
                    )
                )
            ).all()
            return [
                CourseAuthoringRequest(
                    id=record.id,
                    title=record.title,
                    training_brief=TrainingBrief.model_validate_json(
                        json.dumps(record.training_brief)
                    ),
                    audience_snapshot=AudienceSnapshot.model_validate_json(
                        json.dumps(record.audience_snapshot)
                    ),
                    learning_need_refs=tuple(record.learning_need_refs),
                    objective_refs=tuple(record.objective_refs),
                    instructional_blueprint_ref=record.instructional_blueprint_ref,
                    constraints=dict(record.constraints),
                    mode=CourseAuthoringMode(record.mode),
                    status=CourseAuthoringStatus(record.status),
                    authoring_workflow_version=record.authoring_workflow_version,
                    created_by_actor_ref=record.created_by_actor_ref,
                    created_at=record.created_at,
                )
                for record in records
            ]
