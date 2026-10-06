import asyncio
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema

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
from app.candidate_source.repository import (
    SqlAlchemyCandidateSourceRepository,
    is_external_identity_unique_violation,
)
from app.candidate_source.schemas import CandidateSourceEnvelope
from app.shared.database import Base

pytestmark = pytest.mark.skipif(
    not os.getenv("PAI_TEST_POSTGRES_URL"),
    reason="requires an isolated PostgreSQL test database in PAI_TEST_POSTGRES_URL",
)


def _async_postgres_url() -> str:
    value = os.environ["PAI_TEST_POSTGRES_URL"]
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+asyncpg://", 1)
    return value


def _envelope(revision: int, role: str = "Engineer") -> CandidateSourceEnvelope:
    return CandidateSourceEnvelope.model_validate_json(
        json.dumps(
            {
                "schema_id": "pai.candidate-source",
                "schema_version": "v1",
                "company": "CT Group",
                "department": "Engineering",
                "identity": {"source_system": "HRM", "employee_ref": "HR-EMP-RACE"},
                "source_revision": revision,
                "source_snapshot": {},
                "career_history": [{"source_record_ref": "job-1", "company": "Acme", "role": role}],
            }
        )
    )


@pytest.fixture
async def postgres_repository():
    schema = f"candidate_source_test_{uuid4().hex}"
    engine = create_async_engine(_async_postgres_url())
    isolated_engine = engine.execution_options(schema_translate_map={None: schema})
    tables = [
        OrganizationRecord.__table__,
        CandidateRecord.__table__,
        OrganizationExternalMappingRecord.__table__,
        CandidateSourceSnapshotRecord.__table__,
        CandidateExternalEmployeeIdentityRecord.__table__,
        CandidateStructuredEvidenceRecord.__table__,
    ]
    async with engine.begin() as connection:
        await connection.execute(CreateSchema(schema))
    async with isolated_engine.begin() as connection:
        await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
    sessions = async_sessionmaker(isolated_engine, expire_on_commit=False)
    organization_id = uuid4()
    actor = ActorContext(
        actor_id=uuid4(), organization_id=organization_id, roles=frozenset({Role.ADMIN})
    )
    async with sessions() as session, session.begin():
        session.add(
            OrganizationRecord(
                id=organization_id,
                code=f"ORG-{schema[-8:]}",
                name="Race Test",
                status="active",
                version=1,
            )
        )
    repository = SqlAlchemyCandidateSourceRepository(sessions)
    await repository.add_organization_mapping(
        organization_id=organization_id,
        source_system="HRM",
        external_company_ref="CT Group",
    )
    try:
        yield repository, sessions, actor
    finally:
        await engine.dispose()
        async_engine = create_async_engine(_async_postgres_url())
        async with async_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await async_engine.dispose()


def test_identity_unique_retry_only_handles_external_identity_constraint() -> None:
    identity_error = IntegrityError(
        "insert", {}, SimpleNamespace(constraint_name="uq_candidate_external_employee_identity")
    )
    other_error = IntegrityError(
        "insert",
        {},
        SimpleNamespace(constraint_name="uq_candidate_source_snapshot_identity_revision"),
    )
    assert is_external_identity_unique_violation(identity_error)
    assert not is_external_identity_unique_violation(other_error)


@pytest.mark.asyncio
async def test_concurrent_same_revision_same_content_is_one_snapshot_and_one_replay(
    postgres_repository,
) -> None:
    repository, sessions, actor = postgres_repository
    results = await asyncio.gather(
        repository.ingest(_envelope(17), actor=actor),
        repository.ingest(_envelope(17), actor=actor),
    )
    assert {result.disposition for result in results} == {"INITIAL", "REPLAY"}
    assert results[0].snapshot_id == results[1].snapshot_id
    async with sessions() as session:
        assert (
            await session.scalar(select(func.count()).select_from(CandidateSourceSnapshotRecord))
            == 1
        )
        assert (
            await session.scalar(
                select(func.count()).select_from(CandidateStructuredEvidenceRecord)
            )
            > 0
        )


@pytest.mark.asyncio
async def test_concurrent_same_revision_different_content_has_one_acceptance(
    postgres_repository,
) -> None:
    repository, sessions, actor = postgres_repository
    results = await asyncio.gather(
        repository.ingest(_envelope(17, "Engineer"), actor=actor),
        repository.ingest(_envelope(17, "Architect"), actor=actor),
        return_exceptions=True,
    )
    accepted = [result for result in results if not isinstance(result, BaseException)]
    rejected = [result for result in results if isinstance(result, CandidateSourceError)]
    assert len(accepted) == 1
    assert accepted[0].disposition == "INITIAL"
    assert len(rejected) == 1
    assert rejected[0].args[0] == "candidate_source_snapshot_revision_conflict"
    async with sessions() as session:
        assert (
            await session.scalar(select(func.count()).select_from(CandidateSourceSnapshotRecord))
            == 1
        )


@pytest.mark.asyncio
async def test_concurrent_revision_two_and_three_leave_three_current(postgres_repository) -> None:
    repository, sessions, actor = postgres_repository
    baseline = await repository.ingest(_envelope(1), actor=actor)
    results = await asyncio.gather(
        repository.ingest(_envelope(2), actor=actor),
        repository.ingest(_envelope(3), actor=actor),
        return_exceptions=True,
    )
    assert any(not isinstance(result, BaseException) for result in results)
    async with sessions() as session:
        identity = await session.scalar(select(CandidateExternalEmployeeIdentityRecord))
        current = await session.get(CandidateSourceSnapshotRecord, identity.current_snapshot_id)
        assert current.source_revision == 3
        assert current.previous_snapshot_id in {
            baseline.snapshot_id,
            *(result.snapshot_id for result in results if not isinstance(result, BaseException)),
        }
        assert await session.scalar(
            select(func.count()).select_from(CandidateSourceSnapshotRecord)
        ) in {2, 3}
