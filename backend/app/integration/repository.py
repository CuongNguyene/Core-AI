from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integration.models import IntegrationLearningResultRecord
from app.integration.schemas import (
    LearningResultRequest,
)


@dataclass(frozen=True)
class StoredLearningResult:
    submission_id: str
    evaluation_reference: str


class IntegrationRepository(Protocol):
    async def get_learning_result(self, submission_id: str) -> StoredLearningResult | None: ...

    async def get_learning_result_by_evaluation(
        self, evaluation_reference: str
    ) -> StoredLearningResult | None: ...

    async def create_learning_result(
        self, request: LearningResultRequest, evaluation_reference: str
    ) -> StoredLearningResult: ...


class InMemoryIntegrationRepository:
    def __init__(self) -> None:
        self.learning_results: dict[str, StoredLearningResult] = {}

    async def get_learning_result(self, submission_id: str) -> StoredLearningResult | None:
        return self.learning_results.get(submission_id)

    async def get_learning_result_by_evaluation(
        self, evaluation_reference: str
    ) -> StoredLearningResult | None:
        return next(
            (
                result
                for result in self.learning_results.values()
                if result.evaluation_reference == evaluation_reference
            ),
            None,
        )

    async def create_learning_result(
        self, request: LearningResultRequest, evaluation_reference: str
    ) -> StoredLearningResult:
        existing = self.learning_results.get(request.submission_id)
        if existing is not None:
            return existing
        result = StoredLearningResult(request.submission_id, evaluation_reference)
        self.learning_results[request.submission_id] = result
        return result


class SqlAlchemyIntegrationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_learning_result(self, submission_id: str) -> StoredLearningResult | None:
        async with self._session_factory() as session:
            record = await session.get(IntegrationLearningResultRecord, submission_id)
            if record is None:
                return None
            return StoredLearningResult(record.submission_id, record.evaluation_reference)

    async def get_learning_result_by_evaluation(
        self, evaluation_reference: str
    ) -> StoredLearningResult | None:
        async with self._session_factory() as session:
            from sqlalchemy import select

            record = await session.scalar(
                select(IntegrationLearningResultRecord).where(
                    IntegrationLearningResultRecord.evaluation_reference == evaluation_reference
                )
            )
            if record is None:
                return None
            return StoredLearningResult(record.submission_id, record.evaluation_reference)

    async def create_learning_result(
        self, request: LearningResultRequest, evaluation_reference: str
    ) -> StoredLearningResult:
        async with self._session_factory() as session, session.begin():
            existing = await session.get(IntegrationLearningResultRecord, request.submission_id)
            if existing is not None:
                return StoredLearningResult(existing.submission_id, existing.evaluation_reference)
            session.add(
                IntegrationLearningResultRecord(
                    submission_id=request.submission_id,
                    evaluation_reference=evaluation_reference,
                    status="ACCEPTED",
                    learner_reference=request.learner_reference.model_dump(mode="json"),
                    course_reference=request.course_reference.model_dump(mode="json"),
                    activity_reference=request.activity_reference.model_dump(mode="json"),
                    completion_status=request.completion_status,
                    created_at=datetime.now(UTC),
                )
            )
        return StoredLearningResult(request.submission_id, evaluation_reference)
