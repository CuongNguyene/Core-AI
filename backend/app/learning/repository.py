from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.learning.models import LearningAuditEventRecord, LearningPathRecord
from app.learning.schemas import LearningPath, LearningPathStatus


class LearningPathRepository(Protocol):
    async def create(self, path: LearningPath) -> LearningPath: ...

    async def get(self, path_id: str, version: int | None = None) -> LearningPath | None: ...

    async def get_by_idempotency_key(self, key: str) -> LearningPath | None: ...

    async def supersede(self, path_id: str, successor: LearningPath) -> LearningPath: ...

    async def review(self, path_id: str, actor_id: UUID, expected_version: int) -> LearningPath: ...

    async def approve(self, path_id: str, actor_id: UUID, expected_version: int) -> LearningPath: ...


class InMemoryLearningPathRepository:
    def __init__(self, *, audit_failure: bool = False) -> None:
        self.paths: dict[tuple[str, int], LearningPath] = {}
        self.audit_events: list[dict[str, object]] = []
        self._audit_failure = audit_failure

    async def create(self, path: LearningPath) -> LearningPath:
        key = (path.id, path.version)
        if key in self.paths:
            raise ValueError("learning path version is immutable")
        if path.idempotency_key and any(item.idempotency_key == path.idempotency_key for item in self.paths.values()):
            raise ValueError("learning path idempotency key exists")
        self._append_audit(path, "LEARNING_PATH_CREATED")
        self.paths[key] = path.model_copy(deep=True)
        return path.model_copy(deep=True)

    async def get(self, path_id: str, version: int | None = None) -> LearningPath | None:
        if version is not None:
            path = self.paths.get((path_id, version))
            return path.model_copy(deep=True) if path else None
        candidates = [path for (item_id, _), path in self.paths.items() if item_id == path_id]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.version).model_copy(deep=True)

    async def get_by_idempotency_key(self, key: str) -> LearningPath | None:
        for path in self.paths.values():
            if path.idempotency_key == key:
                return path.model_copy(deep=True)
        return None

    async def supersede(self, path_id: str, successor: LearningPath) -> LearningPath:
        current = await self.get(path_id)
        if current is None:
            raise KeyError(path_id)
        if successor.id != path_id or successor.version != current.version + 1:
            raise ValueError("learning path version conflict")
        old_key = (current.id, current.version)
        self._append_audit(successor, "LEARNING_PATH_SUPERSEDED")
        self.paths[old_key] = current.model_copy(
            update={"status": LearningPathStatus.SUPERSEDED}, deep=True
        )
        self.paths[(successor.id, successor.version)] = successor.model_copy(deep=True)
        return successor.model_copy(deep=True)

    async def review(self, path_id: str, actor_id: UUID, expected_version: int) -> LearningPath:
        current = await self.get(path_id)
        if current is None or current.version != expected_version:
            raise ValueError("learning path version conflict")
        reviewed = current.model_copy(
            update={
                "reviewed": True,
                "reviewed_by": actor_id,
                "reviewed_at": datetime.now(UTC),
                "reviewed_version": current.version,
            },
            deep=True,
        )
        self._append_audit(reviewed, "LEARNING_PATH_REVIEWED", actor_id=actor_id)
        self.paths[(current.id, current.version)] = reviewed
        return reviewed.model_copy(deep=True)

    async def approve(self, path_id: str, actor_id: UUID, expected_version: int) -> LearningPath:
        current = await self.get(path_id)
        if current is None or current.version != expected_version:
            raise ValueError("learning path version conflict")
        for key, candidate in list(self.paths.items()):
            if candidate.id == path_id and candidate.version < current.version and candidate.status is LearningPathStatus.ACTIVE:
                self.paths[key] = candidate.model_copy(
                    update={"status": LearningPathStatus.SUPERSEDED}, deep=True
                )
        approved = current.model_copy(
            update={
                "status": LearningPathStatus.ACTIVE,
                "approved_by": actor_id,
                "approved_at": datetime.now(UTC),
                "approved_version": current.version,
            },
            deep=True,
        )
        self._append_audit(approved, "LEARNING_PATH_APPROVED", actor_id=actor_id)
        self.paths[(current.id, current.version)] = approved
        return approved.model_copy(deep=True)

    def _append_audit(self, path: LearningPath, action: str, *, actor_id: UUID | None = None) -> None:
        if self._audit_failure:
            raise RuntimeError("audit_insert_failed")
        self.audit_events.append(
            {
                "action": action,
                "path_id": path.id,
                "actor_id": actor_id or path.created_by,
                "metadata": {
                    "path_version": path.version,
                    "status": path.status.value,
                    "target_profile_id": path.target_profile_id,
                    "target_profile_version": path.target_profile_version,
                    "preliminary_match_id": path.preliminary_match_id,
                    "generator_version": path.generator_version,
                    "policy_version": path.policy_version,
            "correlation_id": path.correlation_id,
            "source_type": path.source_type.value,
            "capability_analysis_id": path.capability_analysis_id,
            "capability_analysis_version": path.capability_analysis_version,
            "source_gap_ids": path.source_gap_ids,
            "validation": path.validation.model_dump(mode="json"),
                },
            }
        )


class SqlAlchemyLearningPathRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, path: LearningPath) -> LearningPath:
        try:
            async with self._session_factory() as session, session.begin():
                existing = await session.get(LearningPathRecord, (path.id, path.version))
                if existing is not None:
                    raise ValueError("learning path version is immutable")
                session.add(self._to_record(path))
                session.add(self._audit_record(path, "LEARNING_PATH_CREATED"))
        except IntegrityError as exc:
            raise ValueError("learning path idempotency key exists") from exc
        return path.model_copy(deep=True)

    async def get(self, path_id: str, version: int | None = None) -> LearningPath | None:
        async with self._session_factory() as session:
            if version is not None:
                record = await session.get(LearningPathRecord, (path_id, version))
            else:
                from sqlalchemy import desc, select

                record = await session.scalar(
                    select(LearningPathRecord)
                    .where(LearningPathRecord.id == path_id)
                    .order_by(desc(LearningPathRecord.version))
                    .limit(1)
                )
            return self._from_record(record) if record is not None else None

    async def get_by_idempotency_key(self, key: str) -> LearningPath | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(LearningPathRecord).where(LearningPathRecord.idempotency_key == key)
            )
            return self._from_record(record) if record is not None else None

    async def supersede(self, path_id: str, successor: LearningPath) -> LearningPath:
        async with self._session_factory() as session, session.begin():
            from sqlalchemy import select

            current = await session.scalar(
                select(LearningPathRecord)
                .where(LearningPathRecord.id == path_id)
                .order_by(LearningPathRecord.version.desc())
                .limit(1)
                .with_for_update()
            )
            if current is None:
                raise KeyError(path_id)
            if successor.id != path_id or successor.version != current.version + 1:
                raise ValueError("learning path version conflict")
            current.status = LearningPathStatus.SUPERSEDED.value
            session.add(self._to_record(successor))
            session.add(self._audit_record(successor, "LEARNING_PATH_SUPERSEDED"))
        return successor.model_copy(deep=True)

    async def review(self, path_id: str, actor_id: UUID, expected_version: int) -> LearningPath:
        async with self._session_factory() as session, session.begin():
            record = await session.get(LearningPathRecord, (path_id, expected_version), with_for_update=True)
            if record is None:
                raise ValueError("learning path version conflict")
            reviewed_at = datetime.now(UTC)
            record.reviewed = True
            record.reviewed_by = actor_id
            record.reviewed_at = reviewed_at
            record.reviewed_version = expected_version
            path = self._from_record(record)
            session.add(self._audit_record(path, "LEARNING_PATH_REVIEWED", actor_id=actor_id))
        return path

    async def approve(self, path_id: str, actor_id: UUID, expected_version: int) -> LearningPath:
        async with self._session_factory() as session, session.begin():
            from sqlalchemy import update

            record = await session.get(LearningPathRecord, (path_id, expected_version), with_for_update=True)
            if record is None:
                raise ValueError("learning path version conflict")
            await session.execute(
                update(LearningPathRecord)
                .where(
                    LearningPathRecord.id == path_id,
                    LearningPathRecord.version < expected_version,
                    LearningPathRecord.status == LearningPathStatus.ACTIVE.value,
                )
                .values(status=LearningPathStatus.SUPERSEDED.value)
            )
            approved_at = datetime.now(UTC)
            record.status = LearningPathStatus.ACTIVE.value
            record.approved_by = actor_id
            record.approved_at = approved_at
            record.approved_version = expected_version
            path = self._from_record(record)
            session.add(self._audit_record(path, "LEARNING_PATH_APPROVED", actor_id=actor_id))
        return path

    @staticmethod
    def _to_record(path: LearningPath) -> LearningPathRecord:
        payload = path.model_dump(mode="json")
        return LearningPathRecord(
            id=path.id,
            version=path.version,
            status=path.status.value,
            subject_id=path.subject_id,
            organization_id=path.organization_id,
            target_profile_id=path.target_profile_id,
            target_profile_version=path.target_profile_version,
            preliminary_match_id=path.preliminary_match_id,
            verified_competency_record_ids=[
                str(item) for item in path.verified_competency_record_ids
            ],
            approved_gap_ids=path.approved_gap_ids,
            development_goal=path.development_goal,
            target_completion_date=path.target_completion_date,
            objectives=payload["objectives"],
            prerequisite_nodes=payload["prerequisite_nodes"],
            prerequisite_edges=payload["prerequisite_edges"],
            learning_objects=payload["learning_objects"],
            lessons=payload["lessons"],
            modules=payload["modules"],
            blueprints=payload["blueprints"],
            generator_version=path.generator_version,
            policy_version=path.policy_version,
            correlation_id=path.correlation_id,
            created_by=path.created_by,
            created_at=path.created_at,
            source_type=path.source_type.value,
            capability_analysis_id=path.capability_analysis_id,
            capability_analysis_version=path.capability_analysis_version,
            source_candidate_id=path.source_candidate_id,
            source_profile_id=path.source_profile_id,
            source_profile_version=path.source_profile_version,
            source_target_id=path.source_target_id,
            source_target_version=path.source_target_version,
            source_gap_ids=path.source_gap_ids,
            source_evidence_refs=path.source_evidence_refs,
            source_recommendation_refs=path.source_recommendation_refs,
            validation=path.validation.model_dump(mode="json"),
            reviewed=path.reviewed,
            reviewed_by=path.reviewed_by,
            reviewed_at=path.reviewed_at,
            reviewed_version=path.reviewed_version,
            approved_by=path.approved_by,
            approved_at=path.approved_at,
            approved_version=path.approved_version,
            idempotency_key=path.idempotency_key,
            request_fingerprint=path.request_fingerprint,
        )

    @staticmethod
    def _from_record(record: LearningPathRecord) -> LearningPath:
        return LearningPath.model_validate(
            {
                "id": record.id,
                "version": record.version,
                "status": record.status,
                "subject_id": record.subject_id,
                "organization_id": record.organization_id,
                "target_profile_id": record.target_profile_id,
                "target_profile_version": record.target_profile_version,
                "preliminary_match_id": record.preliminary_match_id,
                "verified_competency_record_ids": record.verified_competency_record_ids,
                "approved_gap_ids": record.approved_gap_ids,
                "development_goal": record.development_goal,
                "target_completion_date": record.target_completion_date,
                "objectives": record.objectives,
                "prerequisite_nodes": record.prerequisite_nodes,
                "prerequisite_edges": record.prerequisite_edges,
                "learning_objects": record.learning_objects,
                "lessons": record.lessons,
                "modules": record.modules,
                "blueprints": record.blueprints,
                "generator_version": record.generator_version,
                "policy_version": record.policy_version,
                "correlation_id": record.correlation_id,
                "created_by": record.created_by,
                "created_at": record.created_at,
                "source_type": record.source_type,
                "capability_analysis_id": record.capability_analysis_id,
                "capability_analysis_version": record.capability_analysis_version,
                "source_candidate_id": record.source_candidate_id,
                "source_profile_id": record.source_profile_id,
                "source_profile_version": record.source_profile_version,
                "source_target_id": record.source_target_id,
                "source_target_version": record.source_target_version,
                "source_gap_ids": record.source_gap_ids,
                "source_evidence_refs": record.source_evidence_refs,
                "source_recommendation_refs": record.source_recommendation_refs,
                "validation": record.validation,
                "reviewed": record.reviewed,
                "reviewed_by": record.reviewed_by,
                "reviewed_at": record.reviewed_at,
                "reviewed_version": record.reviewed_version,
                "approved_by": record.approved_by,
                "approved_at": record.approved_at,
                "approved_version": record.approved_version,
                "idempotency_key": record.idempotency_key,
                "request_fingerprint": record.request_fingerprint,
            },
            strict=False,
        )

    @staticmethod
    def _audit_record(
        path: LearningPath, action: str, *, actor_id: UUID | None = None
    ) -> LearningAuditEventRecord:
        return LearningAuditEventRecord(
            id=uuid4(),
            path_id=path.id,
            actor_id=actor_id or path.created_by,
            action=action,
            audit_metadata={
                "path_version": path.version,
                "status": path.status.value,
                "target_profile_id": path.target_profile_id,
                "target_profile_version": path.target_profile_version,
                "preliminary_match_id": path.preliminary_match_id,
                "generator_version": path.generator_version,
                "policy_version": path.policy_version,
                "correlation_id": path.correlation_id,
            },
        )
