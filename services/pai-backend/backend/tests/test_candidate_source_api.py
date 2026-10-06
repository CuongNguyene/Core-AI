from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient

from app.authorization.schemas import ActorContext, Role
from app.candidate_source.api import router
from app.candidate_source.domain import CandidateSourceError
from app.candidate_source.repository import IngestedCandidateSnapshot
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.shared.errors import APIError, api_error_handler, request_validation_error_handler

ORG_ID = UUID("00000000-0000-0000-0000-000000000101")
ACTOR_ID = UUID("00000000-0000-0000-0000-000000000102")
CANDIDATE_ID = UUID("00000000-0000-0000-0000-000000000103")
SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000104")


class FakeCandidateSourceRepository:
    def __init__(self, disposition: str = "INITIAL", error: str | None = None) -> None:
        self.disposition = disposition
        self.error = error
        self.received = None

    async def ingest(self, envelope, *, actor):
        self.received = envelope
        if self.error:
            raise CandidateSourceError(self.error)
        return IngestedCandidateSnapshot(
            candidate_id=CANDIDATE_ID,
            snapshot_id=SNAPSHOT_ID,
            source_revision=envelope.source_revision,
            fingerprint="a" * 64,
            disposition=self.disposition,
            current_snapshot_id=SNAPSHOT_ID,
        )


def _payload(revision: int = 17) -> dict[str, object]:
    return {
        "schema_id": "pai.candidate-source",
        "schema_version": "v1",
        "company": "CT Group",
        "identity": {"source_system": "HRM", "employee_ref": "EMP-17"},
        "snapshot": {
            "source_revision": revision,
            "source_updated_at": "2026-10-06T01:00:00Z",
            "source_version": "hrm-v1",
            "source_snapshot_ref": "snapshot-17",
        },
        "career_history": [{"company": "Acme", "role": "Engineer"}],
    }


async def _client(repository: FakeCandidateSourceRepository, roles: frozenset[Role] | None = None):
    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.dependency_overrides[verify_integration_api_key] = lambda: None
    app.dependency_overrides[get_signed_actor_context] = lambda: ActorContext(
        actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        roles=roles or frozenset({Role.ADMIN}),
        authentication_method="signed_actor_context",
    )
    app.state.candidate_source_repository = repository
    app.include_router(router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver"), app


@pytest.mark.asyncio
async def test_external_snapshot_revision_maps_to_internal_envelope_and_returns_created() -> None:
    repository = FakeCandidateSourceRepository()
    http, _app = await _client(repository)
    async with http:
        response = await http.post(
            "/api/v1/candidate-sources/snapshots",
            json={"schema_version": "v1", "data": _payload()},
        )

    assert response.status_code == 201
    assert repository.received.source_revision == 17
    assert (
        repository.received.source_snapshot.source_updated_at.isoformat()
        == "2026-10-06T01:00:00+00:00"
    )
    assert repository.received.source_snapshot.source_version == "hrm-v1"
    assert response.json()["data"]["source_revision"] == 17


@pytest.mark.asyncio
async def test_external_contract_requires_snapshot_revision_and_rejects_internal_top_level_field() -> (
    None
):
    repository = FakeCandidateSourceRepository()
    http, app = await _client(repository)
    invalid = _payload()
    invalid["snapshot"] = {"source_updated_at": "2026-10-06T01:00:00Z"}
    async with http:
        missing = await http.post(
            "/api/v1/candidate-sources/snapshots",
            json={"schema_version": "v1", "data": invalid},
        )
        internal_shape = _payload()
        internal_shape["source_revision"] = internal_shape["snapshot"]["source_revision"]
        del internal_shape["snapshot"]
        top_level = await http.post(
            "/api/v1/candidate-sources/snapshots",
            json={"schema_version": "v1", "data": internal_shape},
        )

    assert missing.status_code == 422
    assert top_level.status_code == 422
    request_schema = app.openapi()["components"]["schemas"]["CandidateSourceProjectionV1"]
    assert "snapshot" in request_schema["required"]
    assert "source_revision" not in request_schema["properties"]
    snapshot_schema = app.openapi()["components"]["schemas"]["CandidateSourceProjectionSnapshot"]
    assert "source_revision" in snapshot_schema["properties"]


@pytest.mark.asyncio
async def test_api_returns_replay_and_stale_conflict_semantics() -> None:
    replay_repo = FakeCandidateSourceRepository(disposition="REPLAY")
    replay_http, _app = await _client(replay_repo)
    async with replay_http:
        replay = await replay_http.post(
            "/api/v1/candidate-sources/snapshots",
            json={"schema_version": "v1", "data": _payload()},
        )
    assert replay.status_code == 200

    stale_repo = FakeCandidateSourceRepository(error="candidate_source_snapshot_stale")
    stale_http, _app = await _client(stale_repo)
    async with stale_http:
        stale = await stale_http.post(
            "/api/v1/candidate-sources/snapshots",
            json={"schema_version": "v1", "data": _payload()},
        )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "candidate_source_snapshot_stale"


@pytest.mark.asyncio
async def test_api_preserves_candidate_source_writer_role_boundary() -> None:
    repository = FakeCandidateSourceRepository()
    http, _app = await _client(repository, frozenset({Role.LEARNER}))
    async with http:
        response = await http.post(
            "/api/v1/candidate-sources/snapshots",
            json={"schema_version": "v1", "data": _payload()},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "candidate_source_writer_required"
