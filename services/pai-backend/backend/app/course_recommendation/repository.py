from __future__ import annotations

import json
import uuid
from datetime import UTC
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.course_recommendation.execution_schemas import (
    RecommendationExecutionCreateResult,
    RecommendationExecutionRecord,
)
from app.course_recommendation.models import CourseRecommendationExecutionRecord as ORMRecord


class RecommendationIdempotencyConflict(ValueError):
    pass


class RecommendationPersistenceError(RuntimeError):
    pass


class CourseRecommendationExecutionRepository(Protocol):
    @staticmethod
    def allocate_id() -> str: ...

    async def create_or_get(
        self, execution: RecommendationExecutionRecord
    ) -> RecommendationExecutionCreateResult: ...

    async def get(self, execution_id: str) -> RecommendationExecutionRecord | None: ...

    async def get_by_scope_key(
        self, *, organization_ref: UUID, actor_ref: UUID, request_key: str
    ) -> RecommendationExecutionRecord | None: ...


class SqlAlchemyCourseRecommendationExecutionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def allocate_id() -> str:
        return f"crx_{uuid.uuid4().hex}"

    async def create_or_get(
        self, execution: RecommendationExecutionRecord
    ) -> RecommendationExecutionCreateResult:
        try:
            async with self._session_factory() as session, session.begin():
                session.add(_to_orm(execution))
            return RecommendationExecutionCreateResult(execution=execution, created=True)
        except IntegrityError as exc:
            existing = await self.get_by_scope_key(
                organization_ref=execution.organization_ref,
                actor_ref=execution.actor_ref,
                request_key=execution.request_key,
            )
            if existing is None:
                raise RecommendationPersistenceError(
                    "recommendation_execution_persistence_failed"
                ) from exc
            if existing.request_fingerprint != execution.request_fingerprint:
                raise RecommendationIdempotencyConflict(
                    "recommendation_idempotency_conflict"
                ) from exc
            return RecommendationExecutionCreateResult(execution=existing, created=False)

    async def get(self, execution_id: str) -> RecommendationExecutionRecord | None:
        async with self._session_factory() as session:
            row = await session.scalar(select(ORMRecord).where(ORMRecord.id == execution_id))
            return _from_orm(row) if row is not None else None

    async def get_by_scope_key(
        self, *, organization_ref: UUID, actor_ref: UUID, request_key: str
    ) -> RecommendationExecutionRecord | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ORMRecord).where(
                    ORMRecord.organization_ref == organization_ref,
                    ORMRecord.actor_ref == actor_ref,
                    ORMRecord.request_key == request_key,
                )
            )
            return _from_orm(row) if row is not None else None


def _to_orm(execution: RecommendationExecutionRecord) -> ORMRecord:
    return ORMRecord(
        id=execution.id,
        request_key=execution.request_key,
        request_fingerprint=execution.request_fingerprint,
        snapshot_schema_version=execution.snapshot_schema_version,
        algorithm_id=execution.algorithm_id,
        algorithm_version=execution.algorithm_version,
        result_kind=execution.result_kind,
        target_ref=execution.target_ref,
        source_learning_need_ref=execution.source_learning_need_ref,
        organization_ref=execution.organization_ref,
        actor_ref=execution.actor_ref,
        request_snapshot=execution.request_snapshot.model_dump(mode="json"),
        result_snapshot=execution.result_snapshot.model_dump(mode="json"),
        governance_snapshot=execution.governance_snapshot.model_dump(mode="json"),
        created_at=execution.created_at,
    )


def _from_orm(row: ORMRecord) -> RecommendationExecutionRecord:
    try:
        return RecommendationExecutionRecord.model_validate_json(
            json.dumps(
                {
                    "id": row.id,
                    "request_key": row.request_key,
                    "request_fingerprint": row.request_fingerprint,
                    "snapshot_schema_version": row.snapshot_schema_version,
                    "algorithm_id": row.algorithm_id,
                    "algorithm_version": row.algorithm_version,
                    "result_kind": row.result_kind,
                    "target_ref": row.target_ref,
                    "source_learning_need_ref": row.source_learning_need_ref,
                    "organization_ref": str(row.organization_ref),
                    "actor_ref": str(row.actor_ref),
                    "request_snapshot": row.request_snapshot,
                    "result_snapshot": row.result_snapshot,
                    "governance_snapshot": row.governance_snapshot,
                    "created_at": (
                        row.created_at.replace(tzinfo=UTC)
                        if row.created_at.tzinfo is None
                        else row.created_at
                    ).isoformat(),
                },
                sort_keys=True,
            )
        )
    except (ValueError, TypeError) as exc:
        raise RecommendationPersistenceError("recommendation_execution_snapshot_corrupt") from exc
