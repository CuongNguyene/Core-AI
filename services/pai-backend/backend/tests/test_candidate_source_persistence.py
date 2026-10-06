import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.authorization.models import OrganizationRecord
from app.authorization.schemas import ActorContext, Role
from app.candidate.models import CandidateRecord
from app.candidate_source.domain import CandidateSourceError
from app.candidate_source.models import (
    CandidateExternalEmployeeIdentityRecord,
    CandidateSourceSnapshotRecord,
    CandidateStructuredEvidenceRecord,
    OrganizationExternalMappingRecord,
)
from app.candidate_source.repository import SqlAlchemyCandidateSourceRepository
from app.candidate_source.schemas import CandidateSourceEnvelope
from app.shared.database import Base


@pytest.mark.asyncio
async def test_source_ingestion_orders_revisions_and_keeps_full_snapshot_history() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    relevant_tables = [
        OrganizationRecord.__table__,
        CandidateRecord.__table__,
        OrganizationExternalMappingRecord.__table__,
        CandidateSourceSnapshotRecord.__table__,
        CandidateExternalEmployeeIdentityRecord.__table__,
        CandidateStructuredEvidenceRecord.__table__,
    ]
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(sync, tables=relevant_tables)
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repo = SqlAlchemyCandidateSourceRepository(sessions)
    org1, org2 = uuid4(), uuid4()
    actor = ActorContext(actor_id=uuid4(), organization_id=org1, roles=frozenset({Role.ADMIN}))
    async with sessions() as session, session.begin():
        session.add_all(
            [
                OrganizationRecord(id=org1, code="ORG-A", name="A", status="active", version=1),
                OrganizationRecord(id=org2, code="ORG-B", name="B", status="active", version=1),
            ]
        )
    await repo.add_organization_mapping(
        organization_id=org1, source_system="HRM", external_company_ref="CT Group"
    )

    def envelope(
        role: str = "Engineer",
        company: str = "CT Group",
        revision: int = 17,
        career_history: list[dict[str, object]] | None = None,
    ) -> CandidateSourceEnvelope:
        data = {
            "schema_id": "pai.candidate-source",
            "schema_version": "v1",
            "company": company,
            "department": "Engineering",
            "identity": {"source_system": "HRM", "employee_ref": "HR-EMP-00301"},
            "source_revision": revision,
            "source_snapshot": {"source_updated_at": "2026-10-01T10:00:00Z", "source_version": 7},
            "career_history": career_history
            if career_history is not None
            else [{"source_record_ref": "job-1", "company": "Acme", "role": role}],
        }
        return CandidateSourceEnvelope.model_validate_json(json.dumps(data))

    first = await repo.ingest(envelope(), actor=actor)
    replay = await repo.ingest(envelope(), actor=actor)
    async with sessions() as session:
        evidence_before_replay = await session.scalar(
            select(func.count()).select_from(CandidateStructuredEvidenceRecord)
        )
    await repo.ingest(envelope(), actor=actor)
    async with sessions() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(CandidateStructuredEvidenceRecord)
            )
            == evidence_before_replay
        )

    newer_same_content = await repo.ingest(envelope(revision=18), actor=actor)
    with pytest.raises(CandidateSourceError, match="candidate_source_snapshot_stale"):
        await repo.ingest(envelope("Stale Engineer", revision=17), actor=actor)
    with pytest.raises(CandidateSourceError, match="candidate_source_snapshot_revision_conflict"):
        await repo.ingest(envelope("Conflicting Engineer", revision=18), actor=actor)
    replacement = await repo.ingest(envelope(revision=19, career_history=[]), actor=actor)

    assert first.disposition == "INITIAL"
    assert replay.disposition == "REPLAY" and replay.candidate_id == first.candidate_id
    assert newer_same_content.disposition == "NEWER"
    assert newer_same_content.snapshot_id != first.snapshot_id
    assert replacement.disposition == "NEWER"
    assert replacement.source_revision == 19
    assert replacement.current_snapshot_id == replacement.snapshot_id
    history = await repo.list_snapshots(candidate_id=first.candidate_id, organization_id=org1)
    by_revision = {row.source_revision: row for row in history}
    assert set(by_revision) == {17, 18, 19}
    current = await repo.get_current_snapshot(
        candidate_id=first.candidate_id,
        organization_id=org1,
        source_system="HRM",
    )
    assert current.snapshot_id == replacement.snapshot_id
    assert current.snapshot_id != first.snapshot_id
    assert current.source_revision == 19
    assert current.content_fingerprint == by_revision[19].content_fingerprint
    with pytest.raises(CandidateSourceError, match="candidate_source_identity_not_found"):
        await repo.get_current_snapshot(
            candidate_id=uuid4(), organization_id=org1, source_system="HRM"
        )
    assert by_revision[17].source_version == 7
    assert by_revision[19].ordering_state == "CURRENT"
    assert by_revision[18].content_fingerprint == by_revision[17].content_fingerprint

    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(CandidateRecord)) == 1
        assert (
            await session.scalar(select(func.count()).select_from(CandidateSourceSnapshotRecord))
            == 3
        )
        evidence_rows = list(
            (await session.scalars(select(CandidateStructuredEvidenceRecord))).all()
        )
        assert evidence_rows
        assert any(
            row.snapshot_id == by_revision[17].id
            and row.source_field_path == "career_history[0].role"
            for row in evidence_rows
        )
        current_evidence_paths = {
            row.source_field_path for row in evidence_rows if row.snapshot_id == by_revision[19].id
        }
        assert "career_history" in current_evidence_paths
        assert "career_history[0].role" not in current_evidence_paths
        current = await session.scalar(select(CandidateExternalEmployeeIdentityRecord))
        assert current.current_snapshot_id == by_revision[19].id
        assert all(row.external_identity_id == current.id for row in history)
        current_snapshot = await session.get(CandidateSourceSnapshotRecord, by_revision[19].id)
        current_snapshot.source_revision = None
        await session.commit()

    with pytest.raises(CandidateSourceError, match="candidate_source_current_revision_unavailable"):
        await repo.ingest(envelope(revision=20), actor=actor)
    async with sessions() as session:
        assert (
            await session.scalar(select(func.count()).select_from(CandidateSourceSnapshotRecord))
            == 3
        )
        current = await session.scalar(select(CandidateExternalEmployeeIdentityRecord))
        assert current.current_snapshot_id == by_revision[19].id

    with pytest.raises(CandidateSourceError, match="organization_mapping_not_found"):
        await repo.ingest(envelope(company="CT group"), actor=actor)
    with pytest.raises(CandidateSourceError, match="organization_mapping_conflict"):
        await repo.add_organization_mapping(
            organization_id=org2, source_system="HRM", external_company_ref="CT Group"
        )
    other_candidate_id = uuid4()
    async with sessions() as session, session.begin():
        session.add(
            CandidateRecord(
                id=other_candidate_id,
                candidate_code=f"CAN-{other_candidate_id.hex[:12].upper()}",
                display_name=None,
                primary_email=None,
                primary_phone=None,
                organization_id=org1,
                created_by_actor_id=actor.actor_id,
                status="active",
                review_state="draft",
            )
        )
        mismatched_snapshot = await session.get(
            CandidateSourceSnapshotRecord, replacement.snapshot_id
        )
        mismatched_snapshot.candidate_id = other_candidate_id
    with pytest.raises(CandidateSourceError, match="candidate_source_current_snapshot_invalid"):
        await repo.get_current_snapshot(
            candidate_id=first.candidate_id,
            organization_id=org1,
            source_system="HRM",
        )
    await engine.dispose()
