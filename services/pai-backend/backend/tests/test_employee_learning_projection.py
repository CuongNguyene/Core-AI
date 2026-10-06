import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.authorization.models import OrganizationRecord
from app.authorization.schemas import ActorContext, Role
from app.candidate.models import CandidateRecord
from app.candidate_source import schemas
from app.candidate_source.api import router
from app.candidate_source.domain import CandidateSourceError, project_candidate_profile
from app.candidate_source.models import (
    CandidateExternalEmployeeIdentityRecord,
    CandidateSourceSnapshotRecord,
    CandidateStructuredEvidenceRecord,
    OrganizationExternalMappingRecord,
)
from app.candidate_source.repository import SqlAlchemyCandidateSourceRepository
from app.integration.actor_context import (
    SignedActorContextVerifier,
    actor_context_headers,
    get_signed_actor_context,
)
from app.integration.auth import verify_integration_api_key
from app.shared.database import Base
from app.shared.errors import APIError, api_error_handler, request_validation_error_handler

ROUTE = "/api/v1/candidate-sources/learning-projections"


def payload():
    return json.loads(
        (Path(__file__).parent / "fixtures/employee_learning_projection_v1.json").read_text()
    )


def projection(data=None):
    model = getattr(schemas, "EmployeeLearningProjectionV1", None)
    assert model is not None, "Core-owned frozen Learning Projection DTO is missing"
    return model.model_validate_json(json.dumps(payload() if data is None else data))


def set_path(data, path, value):
    node = data
    for key in path[:-1]:
        node = node[key]
    if value == "__DELETE__":
        del node[path[-1]]
    else:
        node[path[-1]] = value


def test_external_adapter_preserves_source_without_expanding_candidate_profile():
    value = projection()
    internal = value.to_candidate_source_envelope()
    assert internal.source_revision == 17
    assert internal.identity.employee_ref == "HR-EMP-00280"
    assert internal.company == "CÔNG TY CỔ PHẦN TẬP ĐOÀN C.T"
    assert internal.department == "Trung tâm Công nghệ Thông tin"
    assert internal.source_snapshot.source_updated_at.isoformat() == "2026-10-06T10:30:00+07:00"
    assert (
        internal.career_history[0].responsibilities
        == payload()["candidate_source"]["career_history"][0]["responsibilities"]
    )
    profile = project_candidate_profile(internal)
    assert profile.employment_history[0].role == "Engineer"
    assert profile.skills == []
    changed = payload()
    changed["employment_context"]["job_title"] = "Chief AI Officer"
    changed["target_job_source"]["job_description_html"] = "VERIFIED capability"
    changed["auxiliary_signals"]["ats_ai_profile"]["summary"] = "VERIFIED capability"
    assert project_candidate_profile(projection(changed).to_candidate_source_envelope()) == profile


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_id",), "wrong"),
        (("schema_version",), "v2"),
        (("identity", "employee_ref"), ""),
        (("identity", "employee_ref"), "   "),
        (("identity", "employee_ref"), "__DELETE__"),
        (("identity", "source_system"), "ATS"),
        (("snapshot", "source_revision"), "__DELETE__"),
        *((("snapshot", "source_revision"), value) for value in (0, -1, True, "17", 1.5)),
        (("employment_context", "company"), ""),
        (("employment_context", "company"), "   "),
        (("employment_context", "company"), "__DELETE__"),
        *(
            (("candidate_source", name), "__DELETE__")
            for name in (
                "career_history",
                "education",
                "languages",
                "tools",
                "certifications",
                "projects",
            )
        ),
        (("recruitment_evidence", "interviewer_feedback"), "__DELETE__"),
        (("recruitment_evidence", "assessments"), None),
        (("candidate_source", "tools"), {}),
        (("bank_information",), {}),
        (("salary",), 100),
        (("actor_ref",), "evil"),
        (("organization_ref",), "evil"),
        (("employment_context", "job_salary_range"), "high"),
        (("candidate_source", "career_history", 0, "salary"), 100),
        (("candidate_source", "career_history", 0, "technologies"), ["Python"]),
        (("candidate_source", "projects", 0, "project_achievements"), "invented"),
        (("auxiliary_signals", "extra_payload"), {"bank": "secret"}),
    ],
)
def test_strict_projection_rejects_invalid_contract_and_non_pai_data(path, value):
    data = payload()
    set_path(data, path, value)
    with pytest.raises(ValidationError):
        projection(data)


def test_optional_context_and_empty_full_collections_are_supported():
    data = payload()
    data["employment_context"] = {"company": "Exact company"}
    data["snapshot"] = {"source_revision": 1}
    data["candidate_source"] = {key: [] for key in data["candidate_source"]}
    data["recruitment_evidence"] = {"interviewer_feedback": [], "assessments": []}
    data.pop("target_job_source")
    data.pop("auxiliary_signals")
    assert projection(data).to_candidate_source_envelope().source_revision == 1


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        {
            "cv_match_score": None,
            "verified_by_recruiter": None,
            "verified_by": None,
            "verified_at": None,
            "summary": None,
        },
    ],
)
def test_ats_ai_profile_optional_nullable_fields_preserved(value):
    data = payload()
    data["auxiliary_signals"]["ats_ai_profile"] = value
    assert projection(data).source_payload() == data


@pytest.mark.parametrize(
    "value",
    [
        "not an object",
        {"unknown": "not allowed"},
        {"cv_match_score": "85.5"},
        {"verified_by_recruiter": "true"},
        {"verified_by": 17},
        {"verified_at": "invalid date"},
        {"summary": {}},
    ],
)
def test_ats_ai_profile_strict_frozen_schema(value):
    data = payload()
    data["auxiliary_signals"]["ats_ai_profile"] = value
    with pytest.raises(ValidationError):
        projection(data)


@pytest.fixture
async def storage():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        OrganizationRecord.__table__,
        CandidateRecord.__table__,
        OrganizationExternalMappingRecord.__table__,
        CandidateSourceSnapshotRecord.__table__,
        CandidateExternalEmployeeIdentityRecord.__table__,
        CandidateStructuredEvidenceRecord.__table__,
    ]
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    org = uuid4()
    actor = ActorContext(actor_id=uuid4(), organization_id=org, roles=frozenset({Role.ADMIN}))
    async with sessions() as session, session.begin():
        session.add(
            OrganizationRecord(id=org, code="TEST", name="Test", status="active", version=1)
        )
    repo = SqlAlchemyCandidateSourceRepository(sessions)
    await repo.add_organization_mapping(
        organization_id=org,
        source_system="HRM",
        external_company_ref=payload()["employment_context"]["company"],
    )
    try:
        yield repo, sessions, actor
    finally:
        await engine.dispose()


async def ingest(repo, data, actor):
    value = projection(data)
    return await repo.ingest_learning_projection(value, actor=actor)


@pytest.mark.asyncio
async def test_full_projection_roundtrip_history_replay_and_replacement(storage):
    repo, sessions, actor = storage
    data = payload()
    first = await ingest(repo, data, actor)
    audit_only = copy.deepcopy(data)
    audit_only["snapshot"]["source_updated_at"] = "2026-10-07T10:30:00+07:00"
    replay = await ingest(repo, audit_only, actor)
    assert replay.snapshot_id == first.snapshot_id and replay.disposition == "REPLAY"
    newer = copy.deepcopy(data)
    newer["snapshot"]["source_revision"] = 18
    second = await ingest(repo, newer, actor)
    assert second.disposition == "NEWER" and second.snapshot_id != first.snapshot_id
    replacement = copy.deepcopy(newer)
    replacement["snapshot"]["source_revision"] = 19
    replacement["candidate_source"]["certifications"] = []
    third = await ingest(repo, replacement, actor)
    with pytest.raises(CandidateSourceError, match="candidate_source_snapshot_stale"):
        await ingest(repo, data, actor)
    history = await repo.list_snapshots(
        candidate_id=first.candidate_id, organization_id=actor.organization_id
    )
    rows = {row.source_revision: row for row in history}
    assert len(rows) == 3
    assert rows[17].payload == data
    assert rows[18].payload == newer
    assert rows[19].payload == replacement
    assert rows[17].schema_id == "pai.employee-learning-projection"
    assert rows[17].content_fingerprint == rows[18].content_fingerprint
    assert rows[17].fingerprint != rows[18].fingerprint
    async with sessions() as session:
        identity = await session.scalar(select(CandidateExternalEmployeeIdentityRecord))
        assert identity.current_snapshot_id == third.snapshot_id
        assert await session.scalar(select(func.count()).select_from(CandidateRecord)) == 1
        evidence = list((await session.scalars(select(CandidateStructuredEvidenceRecord))).all())
        assert any(
            row.snapshot_id == first.snapshot_id
            and row.source_field_path == "target_job_source.job_description_html"
            and row.source_value == data["target_job_source"]["job_description_html"]
            for row in evidence
        )
        assert any(
            row.snapshot_id == first.snapshot_id
            and row.source_field_path == "candidate_source.career_history[0].responsibilities"
            for row in evidence
        )
        assert not any(
            row.snapshot_id == third.snapshot_id
            and row.source_field_path.startswith("candidate_source.certifications[")
            for row in evidence
        )


@pytest.mark.parametrize(
    "section",
    [
        "employment_context",
        "target_job_source",
        "candidate_source",
        "recruitment_evidence",
        "auxiliary_signals",
    ],
)
@pytest.mark.asyncio
async def test_same_revision_change_in_each_source_section_conflicts_without_writes(
    storage, section
):
    repo, sessions, actor = storage
    data = payload()
    first = await ingest(repo, data, actor)
    async with sessions() as session:
        before = await session.scalar(
            select(func.count()).select_from(CandidateStructuredEvidenceRecord)
        )
    changed = copy.deepcopy(data)
    if section == "employment_context":
        changed[section]["job_title"] = "Different title"
    elif section == "target_job_source":
        changed[section]["job_description_html"] = "<p>Different JD</p>"
    elif section == "candidate_source":
        changed[section]["career_history"][0]["responsibilities"] = "Different responsibility"
    elif section == "recruitment_evidence":
        changed[section]["interviewer_feedback"][0]["comment"] = "Different feedback"
    else:
        changed[section]["current_application_ai_score"] = 0.95
    with pytest.raises(CandidateSourceError, match="candidate_source_snapshot_revision_conflict"):
        await ingest(repo, changed, actor)
    async with sessions() as session:
        assert (
            await session.scalar(select(func.count()).select_from(CandidateSourceSnapshotRecord))
            == 1
        )
        assert (
            await session.scalar(
                select(func.count()).select_from(CandidateStructuredEvidenceRecord)
            )
            == before
        )
        identity = await session.scalar(select(CandidateExternalEmployeeIdentityRecord))
        assert identity.current_snapshot_id == first.snapshot_id


@pytest.mark.asyncio
async def test_exact_company_mapping_and_actor_scope_reused(storage):
    repo, _sessions, actor = storage
    data = payload()
    data["employment_context"]["company"] = "unknown company"
    with pytest.raises(CandidateSourceError, match="organization_mapping_not_found"):
        await ingest(repo, data, actor)
    wrong_actor = actor.model_copy(update={"organization_id": uuid4()})
    with pytest.raises(CandidateSourceError, match="candidate_source_organization_forbidden"):
        await ingest(repo, payload(), wrong_actor)


def app_for(repo, actor, *, auth_override=True):
    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    if auth_override:
        app.dependency_overrides[verify_integration_api_key] = lambda: None
    else:
        app.state.settings = SimpleNamespace(
            integration_api_key=SimpleNamespace(get_secret_value=lambda: "test-key")
        )
    app.dependency_overrides[get_signed_actor_context] = lambda: actor
    app.state.candidate_source_repository = repo
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_learning_projection_route_persists_full_source_and_maps_ordering_errors(storage):
    repo, _sessions, actor = storage
    app = app_for(repo, actor)
    data = payload()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        first = await http.post(ROUTE, json={"schema_version": "v1", "data": data})
        assert first.status_code == 201
        replay = await http.post(ROUTE, json={"schema_version": "v1", "data": data})
        assert replay.status_code == 200
        changed = copy.deepcopy(data)
        changed["target_job_source"]["job_description_html"] = "Different JD"
        conflict = await http.post(ROUTE, json={"schema_version": "v1", "data": changed})
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "candidate_source_snapshot_revision_conflict"
        data["snapshot"]["source_revision"] = 18
        assert (
            await http.post(ROUTE, json={"schema_version": "v1", "data": data})
        ).status_code == 201
        data["snapshot"]["source_revision"] = 17
        stale = await http.post(ROUTE, json={"schema_version": "v1", "data": data})
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "candidate_source_snapshot_stale"
    schemas_out = app.openapi()["components"]["schemas"]
    assert "snapshot" in schemas_out["EmployeeLearningProjectionV1"]["required"]
    assert "source_revision" in schemas_out["LearningProjectionSnapshot"]["required"]
    assert "/api/v1/candidate-sources/snapshots" in app.openapi()["paths"]


@pytest.mark.asyncio
async def test_learning_projection_auth_and_writer_roles_are_required(storage):
    repo, sessions, actor = storage
    app = app_for(repo, actor, auth_override=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        denied = await http.post(ROUTE, json={"schema_version": "v1", "data": payload()})
        assert denied.status_code == 401
        learner = actor.model_copy(update={"roles": frozenset({Role.LEARNER})})
        app.dependency_overrides[get_signed_actor_context] = lambda: learner
        denied_role = await http.post(
            ROUTE,
            headers={"Authorization": "Bearer test-key"},
            json={"schema_version": "v1", "data": payload()},
        )
        assert denied_role.status_code == 403
        assert denied_role.json()["error"]["code"] == "candidate_source_writer_required"
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(CandidateRecord)) == 0


@pytest.mark.asyncio
async def test_learning_projection_signed_actor_scope_and_transport_validation(storage):
    repo, _sessions, actor = storage
    app = app_for(repo, actor, auth_override=False)
    del app.dependency_overrides[get_signed_actor_context]
    key = Ed25519PrivateKey.generate()
    app.state.actor_context_verifier = SignedActorContextVerifier(
        public_keys={"test-key": key.public_key()}, actor_resolver=lambda _id, _org: actor
    )

    def headers(org=None):
        now = datetime.now(UTC)
        return {
            "Authorization": "Bearer test-key",
            **actor_context_headers(
                private_key=key,
                key_id="test-key",
                actor_id=actor.actor_id,
                organization_id=org or actor.organization_id,
                issued_at=now,
                expires_at=now + timedelta(seconds=30),
                nonce=str(uuid4()),
            ),
        }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        body = {"schema_version": "v1", "data": payload()}
        assert (
            await http.post(ROUTE, json=body, headers={"Authorization": "Bearer test-key"})
        ).status_code == 401
        assert (await http.post(ROUTE, json=body, headers=headers(uuid4()))).status_code == 403
        invalid = copy.deepcopy(body)
        invalid["data"]["organization_ref"] = str(uuid4())
        assert (await http.post(ROUTE, json=invalid, headers=headers())).status_code == 422
        unknown = copy.deepcopy(body)
        unknown["data"]["employment_context"]["company"] = "UNKNOWN"
        missing = await http.post(ROUTE, json=unknown, headers=headers())
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "organization_mapping_not_found"
        body["data"]["recruitment_evidence"]["interviewer_feedback"][0]["occurred_at"] = (
            "2026-10-01T09:00:00+07:00"
        )
        body["data"]["recruitment_evidence"]["assessments"][0]["occurred_at"] = (
            "2026-10-01T10:00:00+07:00"
        )
        assert (await http.post(ROUTE, json=body, headers=headers())).status_code == 201
        app.state.candidate_source_repository = None
        unavailable = await http.post(ROUTE, json=body, headers=headers())
        assert unavailable.status_code == 503
        assert unavailable.json()["error"]["code"] == "candidate_source_unavailable"
