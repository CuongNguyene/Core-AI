import asyncio
import copy
import os

import pytest
from sqlalchemy import select
from test_candidate_source_concurrency import postgres_repository as postgres_repository
from test_employee_learning_projection import payload, projection

from app.candidate_source.domain import CandidateSourceError
from app.candidate_source.models import (
    CandidateExternalEmployeeIdentityRecord,
    CandidateSourceSnapshotRecord,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("PAI_TEST_POSTGRES_URL"), reason="requires isolated PostgreSQL"
)


@pytest.mark.asyncio
async def test_learning_projection_uses_shared_postgres_identity_retry_and_ordering(
    postgres_repository,
):
    repo, sessions, actor = postgres_repository
    data = payload()
    data["employment_context"]["company"] = "CT Group"
    first, replay = await asyncio.gather(
        repo.ingest_learning_projection(projection(data), actor=actor),
        repo.ingest_learning_projection(projection(data), actor=actor),
    )
    assert {first.disposition, replay.disposition} == {"INITIAL", "REPLAY"}
    assert first.snapshot_id == replay.snapshot_id
    changed = copy.deepcopy(data)
    changed["target_job_source"]["job_description_html"] = "Changed source JD"
    conflict = await asyncio.gather(
        repo.ingest_learning_projection(projection(data), actor=actor),
        repo.ingest_learning_projection(projection(changed), actor=actor),
        return_exceptions=True,
    )
    errors = [result for result in conflict if isinstance(result, CandidateSourceError)]
    assert len(errors) == 1
    assert errors[0].args[0] == "candidate_source_snapshot_revision_conflict"
    newer = copy.deepcopy(data)
    newer["snapshot"]["source_revision"] = 18
    newest = copy.deepcopy(data)
    newest["snapshot"]["source_revision"] = 19
    revision_results = await asyncio.gather(
        repo.ingest_learning_projection(projection(newer), actor=actor),
        repo.ingest_learning_projection(projection(newest), actor=actor),
        return_exceptions=True,
    )
    for result in revision_results:
        if isinstance(result, BaseException):
            assert isinstance(result, CandidateSourceError)
            assert result.args[0] == "candidate_source_snapshot_stale"
        else:
            assert result.disposition == "NEWER"
    async with sessions() as session:
        identity = await session.scalar(select(CandidateExternalEmployeeIdentityRecord))
        current = await session.get(CandidateSourceSnapshotRecord, identity.current_snapshot_id)
        assert current.source_revision == 19
        assert current.payload == newest
    history = await repo.list_snapshots(
        candidate_id=first.candidate_id, organization_id=actor.organization_id
    )
    assert next(row for row in history if row.source_revision == 17).payload == data
