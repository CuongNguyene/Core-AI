from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.competency.models import (
    CompetencyAuditEventRecord,
    CompetencyDecisionRecord,
    CompetencyRecordRecord,
)
from app.competency.schemas import CompetencyDecision, CompetencyLevelStatus, CompetencyRecord


class InMemoryCompetencyRepository:
    def __init__(self, records: list[CompetencyRecord]) -> None:
        self._records = {record.id: record.model_copy(deep=True) for record in records}

    async def get_record(self, record_id: UUID) -> CompetencyRecord | None:
        record = self._records.get(record_id)
        return record.model_copy(deep=True) if record is not None else None


class SqlAlchemyCompetencyRepository:
    """Persists derived competency state and immutable decision history."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_record(self, record: CompetencyRecord) -> CompetencyRecord:
        async with self._session_factory() as session, session.begin():
            session.add(_record_to_orm(record))
        return record

    async def get_record(self, record_id: UUID) -> CompetencyRecord | None:
        async with self._session_factory() as session:
            record = await session.get(CompetencyRecordRecord, record_id)
            return _record_from_orm(record) if record is not None else None

    async def get_decision(self, decision_id: UUID | None) -> CompetencyDecision | None:
        if decision_id is None:
            return None
        async with self._session_factory() as session:
            decision = await session.get(CompetencyDecisionRecord, decision_id)
            if decision is None:
                return None
            record = await session.get(CompetencyRecordRecord, decision.competency_record_id)
            if record is None:
                raise RuntimeError("competency_record_missing")
            return _decision_from_orm(decision, record)

    async def transition(
        self, record_id: UUID, *, expected_version: int, decision: CompetencyDecision
    ) -> CompetencyRecord:
        async with self._session_factory() as session, session.begin():
            record = await session.scalar(
                select(CompetencyRecordRecord)
                .where(CompetencyRecordRecord.id == record_id)
                .with_for_update()
            )
            if record is None:
                raise KeyError(record_id)
            if record.version != expected_version:
                raise ValueError("version_conflict")
            if decision.organization_id != record.organization_id:
                raise ValueError("organization_mismatch")
            if (
                decision.subject_id != record.subject_id
                or decision.competency_id != record.competency_id
            ):
                raise ValueError("decision_subject_or_competency_mismatch")
            if decision.decided_by is None:
                raise ValueError("decision_actor_required")
            if decision.previous_status.value != record.status:
                raise ValueError("previous_status_conflict")
            if decision.status.value == record.status:
                raise ValueError("state_transition_required")
            session.add(
                CompetencyDecisionRecord(
                    id=decision.id,
                    competency_record_id=record.id,
                    assessment_submission_id=decision.assessment_submission_id,
                    previous_status=decision.previous_status.value,
                    status=decision.status.value,
                    evidence_ids=[str(item) for item in decision.evidence_ids],
                    rubric_version=decision.rubric_version,
                    policy_version=decision.policy_version,
                    decided_by=decision.decided_by,
                    delegation_id=decision.delegation_id,
                    valid_until=decision.valid_until,
                    reassessment_due_at=decision.reassessment_due_at,
                )
            )
            record.status = decision.status.value
            record.version += 1
            record.last_decision_id = decision.id
            record.valid_until = decision.valid_until
            record.reassessment_due_at = decision.reassessment_due_at
            await self._append_audit(session, record, decision, expected_version)
            await session.flush()
            return _record_from_orm(record)

    async def record_authorization_denied(
        self, record_id: UUID, *, actor_id: UUID, reason_code: str
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                CompetencyAuditEventRecord(
                    id=uuid4(),
                    competency_record_id=record_id,
                    actor_id=actor_id,
                    action="AUTHORIZATION_DENIED",
                    audit_metadata={"reason_code": reason_code},
                )
            )

    @staticmethod
    async def _append_audit(
        session: AsyncSession,
        record: CompetencyRecordRecord,
        decision: CompetencyDecision,
        expected_version: int,
    ) -> None:
        session.add(
            CompetencyAuditEventRecord(
                id=uuid4(),
                competency_record_id=record.id,
                competency_decision_id=decision.id,
                actor_id=decision.decided_by,
                action="COMPETENCY_DECISION_RECORDED",
                audit_metadata={
                    "previous_status": decision.previous_status.value,
                    "new_status": decision.status.value,
                    "expected_version": expected_version,
                    "new_version": expected_version + 1,
                    "rubric_version": decision.rubric_version,
                    "policy_version": decision.policy_version,
                    "delegation_id": str(decision.delegation_id)
                    if decision.delegation_id
                    else None,
                },
            )
        )


def _record_to_orm(item: CompetencyRecord) -> CompetencyRecordRecord:
    return CompetencyRecordRecord(
        id=item.id,
        subject_id=item.subject_id,
        organization_id=item.organization_id,
        competency_id=item.competency_id,
        status=item.status.value,
        level=item.level,
        version=item.version,
        last_decision_id=item.last_decision_id,
        valid_until=item.valid_until,
        reassessment_due_at=item.reassessment_due_at,
    )


def _record_from_orm(item: CompetencyRecordRecord) -> CompetencyRecord:
    return CompetencyRecord.model_validate(
        {
            "id": item.id,
            "subject_id": item.subject_id,
            "organization_id": item.organization_id,
            "competency_id": item.competency_id,
            "status": CompetencyLevelStatus(item.status),
            "level": item.level,
            "version": item.version,
            "last_decision_id": item.last_decision_id,
            "valid_until": item.valid_until,
            "reassessment_due_at": item.reassessment_due_at,
        }
    )


def _decision_from_orm(
    item: CompetencyDecisionRecord, record: CompetencyRecordRecord
) -> CompetencyDecision:
    return CompetencyDecision(
        id=item.id,
        subject_id=record.subject_id,
        organization_id=record.organization_id,
        competency_id=record.competency_id,
        assessment_submission_id=item.assessment_submission_id,
        evidence_ids=[UUID(value) for value in item.evidence_ids],
        rubric_version=item.rubric_version,
        policy_version=item.policy_version,
        previous_status=CompetencyLevelStatus(item.previous_status),
        status=CompetencyLevelStatus(item.status),
        decided_by=item.decided_by,
        delegation_id=item.delegation_id,
        valid_until=item.valid_until,
        reassessment_due_at=item.reassessment_due_at,
    )
