from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.authorization.models import ScopedDelegationRecord
from app.authorization.schemas import DelegationStatus
from app.competency.models import CompetencyAuditEventRecord, CompetencyDecisionRecord
from app.competency.repository import SqlAlchemyCompetencyRepository
from app.competency.schemas import (
    CompetencyDecision,
    CompetencyLevelStatus,
    CompetencyRecord,
)
from app.shared.database import Base


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def record() -> CompetencyRecord:
    return CompetencyRecord(
        id=uuid4(),
        subject_id=uuid4(),
        organization_id=uuid4(),
        competency_id="python",
        status=CompetencyLevelStatus.UNKNOWN,
        level=None,
        version=1,
        valid_until=None,
        reassessment_due_at=None,
    )


def decision(item: CompetencyRecord, *, delegation_id: UUID | None = None) -> CompetencyDecision:
    return CompetencyDecision(
        id=uuid4(),
        subject_id=item.subject_id,
        organization_id=item.organization_id,
        competency_id=item.competency_id,
        assessment_submission_id=uuid4(),
        evidence_ids=[uuid4()],
        rubric_version="1.0",
        policy_version="assessment-v1",
        previous_status=item.status,
        status=CompetencyLevelStatus.ASSESSED,
        decided_by=uuid4(),
        delegation_id=delegation_id,
        valid_until=datetime(2027, 8, 3, tzinfo=UTC),
        reassessment_due_at=datetime(2027, 7, 3, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_decision_persists_evidence_validity_and_safe_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyCompetencyRepository(session_factory)
    current = record()
    await repository.create_record(current)

    updated = await repository.transition(
        current.id,
        expected_version=1,
        decision=decision(current),
    )

    assert updated.status is CompetencyLevelStatus.ASSESSED
    assert updated.version == 2
    async with session_factory() as session:
        history = await session.get(CompetencyDecisionRecord, updated.last_decision_id)
        events = list((await session.scalars(select(CompetencyAuditEventRecord))).all())
    assert history is not None
    assert history.evidence_ids
    assert len(events) == 1
    assert "evidence_ids" not in events[0].audit_metadata


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_competency_state_and_decision_version(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = SqlAlchemyCompetencyRepository(session_factory)
    current = record()
    await repository.create_record(current)

    async def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(repository, "_append_audit", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await repository.transition(current.id, expected_version=1, decision=decision(current))

    stored = await repository.get_record(current.id)
    assert stored == current


@pytest.mark.asyncio
async def test_stale_competency_version_is_rejected_without_new_history(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyCompetencyRepository(session_factory)
    current = record()
    await repository.create_record(current)

    with pytest.raises(ValueError, match="version_conflict"):
        await repository.transition(current.id, expected_version=2, decision=decision(current))

    assert await repository.get_record(current.id) == current


@pytest.mark.asyncio
async def test_verification_history_keeps_delegation_reference_after_revoke(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyCompetencyRepository(session_factory)
    current = record()
    delegation_id = uuid4()
    delegated_sme_id = uuid4()
    await repository.create_record(current)
    async with session_factory() as session, session.begin():
        session.add(
            ScopedDelegationRecord(
                id=delegation_id,
                user_id=delegated_sme_id,
                permission="competency.verify",
                organization_id=current.organization_id,
                competency_scope=[current.competency_id],
                valid_from=datetime(2026, 1, 1, tzinfo=UTC),
                valid_until=datetime(2027, 1, 1, tzinfo=UTC),
                status=DelegationStatus.ACTIVE.value,
                granted_by=uuid4(),
                reason="fixture",
                version=1,
            )
        )
    verified_decision = decision(current, delegation_id=delegation_id).model_copy(
        update={"status": CompetencyLevelStatus.VERIFIED, "decided_by": delegated_sme_id}
    )

    updated = await repository.transition(
        current.id, expected_version=1, decision=verified_decision
    )
    async with session_factory() as session, session.begin():
        delegation = await session.get(ScopedDelegationRecord, delegation_id)
        assert delegation is not None
        delegation.status = DelegationStatus.REVOKED.value
    stored = await repository.get_decision(updated.last_decision_id)

    assert stored is not None
    assert stored.delegation_id == delegation_id
