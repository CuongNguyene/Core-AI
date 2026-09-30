from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.authorization.fixtures import LEARNER_ID, ORG_PAI_ID, REVIEWER_ID
from app.authorization.repository import InMemorySubjectRepository
from app.candidate.repository import InMemoryCandidateRepository
from app.candidate.service import CandidateService
from app.documents.repository import InMemoryDocumentRepository
from app.documents.schemas import DocumentKind as StoredDocumentKind
from app.documents.schemas import DocumentStatus, StoredDocument
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import (
    CVExtractionOutput,
    DocumentKind,
    EvidenceStatus,
    EvidenceType,
    ExtractedClaim,
    ExtractionJob,
    ExtractionProfile,
    JobStatus,
    ReviewState,
    SourceLocator,
)
from app.main import create_app

DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")


async def client() -> AsyncClient:
    app: FastAPI = create_app()
    app.state.subject_repository = InMemorySubjectRepository.fixture()
    documents = InMemoryDocumentRepository()
    await documents.create(
        StoredDocument(
            id=DOCUMENT_ID,
            owner_actor_id=REVIEWER_ID,
            organization_id=ORG_PAI_ID,
            kind=StoredDocumentKind.CV,
            content_type="application/pdf",
            byte_size=10,
            sha256="b" * 64,
            object_key="candidate/api.pdf",
            status=DocumentStatus.CLEAN,
            retention_until=datetime.now(UTC) + timedelta(days=1),
        )
    )
    extractions = InMemoryExtractionRepository()
    await extractions.enqueue(
        ExtractionJob(
            id="job-api-1",
            document_id=str(DOCUMENT_ID),
            document_kind=DocumentKind.CV,
            owner_actor_id=REVIEWER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await extractions.mark_succeeded(
        "job-api-1",
        ExtractionProfile(
            id="profile-api-1",
            job_id="job-api-1",
            document_id=str(DOCUMENT_ID),
            document_kind=DocumentKind.CV,
            owner_actor_id=REVIEWER_ID,
            version=1,
            review_state=ReviewState.PENDING_REVIEW,
            output=CVExtractionOutput(
                skills=[
                    ExtractedClaim(
                        value="Python",
                        evidence_type=EvidenceType.EXPLICIT_SKILL,
                        confidence=0.9,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_locator=SourceLocator(
                            document_id=str(DOCUMENT_ID),
                            section="skills",
                            start_offset=1,
                            end_offset=7,
                        ),
                        source_excerpt="Python",
                    )
                ],
                experience=[],
                education=[],
            ),
            audit={"source": "test"},
        ),
    )
    app.state.document_repository = documents
    app.state.extraction_repository = extractions
    app.state.candidate_repository = InMemoryCandidateRepository()
    app.state.candidate_service = CandidateService(
        app.state.candidate_repository, documents, extractions
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_candidate_api_lifecycle_and_evidence() -> None:
    http = await client()
    reviewer = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with http:
        created = await http.post("/api/v1/candidates", headers=reviewer, json={})
        candidate_id = created.json()["candidate_id"]
        attached = await http.post(
            f"/api/v1/candidates/{candidate_id}/documents",
            headers=reviewer,
            json={"document_id": str(DOCUMENT_ID), "is_primary": True},
        )
        linked = await http.post(
            f"/api/v1/candidates/{candidate_id}/profiles",
            headers=reviewer,
            json={"profile_id": "profile-api-1"},
        )
        accepted = await http.post(
            f"/api/v1/candidates/{candidate_id}/accept",
            headers=reviewer,
            json={
                "expected_profile_version": 1,
                "idempotency_key": "api-review-1",
            },
        )
        detail = await http.get(f"/api/v1/candidates/{candidate_id}", headers=reviewer)
        claim_id = detail.json()["claims"][0]["claim_id"]
        evidence = await http.get(
            f"/api/v1/candidates/{candidate_id}/claims/{claim_id}/evidence",
            headers=reviewer,
        )

    assert created.status_code == 201
    assert attached.status_code == 201
    assert linked.status_code == 201
    assert accepted.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["review_state"] == "accepted"
    assert detail.json()["profile"]["reference"]
    assert "profile_id" not in detail.json()["profile"]
    assert detail.json()["claims"][0]["evidence_available"] is True
    assert evidence.status_code == 200
    assert evidence.json()["items"][0]["excerpt"] == "Python"
    assert "document_id" not in evidence.json()["items"][0]


@pytest.mark.asyncio
async def test_candidate_profile_history_exposes_exact_versions_and_current_marker() -> None:
    http = await client()
    reviewer = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with http:
        created = await http.post("/api/v1/candidates", headers=reviewer, json={})
        candidate_id = created.json()["candidate_id"]
        await http.post(
            f"/api/v1/candidates/{candidate_id}/documents",
            headers=reviewer,
            json={"document_id": str(DOCUMENT_ID)},
        )
        await http.post(
            f"/api/v1/candidates/{candidate_id}/profiles",
            headers=reviewer,
            json={"profile_id": "profile-api-1"},
        )
        response = await http.get(
            f"/api/v1/candidates/{candidate_id}/profiles", headers=reviewer
        )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "profile_id": "profile-api-1",
            "governance_version": 1,
            "profile_version": 1,
            "review_state": "pending_review",
            "document_id": str(DOCUMENT_ID),
            "source_cv_version": None,
            "is_current": False,
        }
    ]


@pytest.mark.asyncio
async def test_candidate_exact_profile_review_route_requires_governance_version() -> None:
    http = await client()
    reviewer = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with http:
        created = await http.post("/api/v1/candidates", headers=reviewer, json={})
        candidate_id = created.json()["candidate_id"]
        await http.post(
            f"/api/v1/candidates/{candidate_id}/documents",
            headers=reviewer,
            json={"document_id": str(DOCUMENT_ID)},
        )
        linked = await http.post(
            f"/api/v1/candidates/{candidate_id}/profiles",
            headers=reviewer,
            json={"profile_id": "profile-api-1"},
        )
        profile_id = linked.json()["candidate_profile_id"]
        accepted = await http.post(
            f"/api/v1/candidates/{candidate_id}/profiles/profile-api-1/accept",
            headers=reviewer,
            json={
                "expected_governance_version": 1,
                "idempotency_key": "api-exact-review-1",
            },
        )
        wrong_version = await http.post(
            f"/api/v1/candidates/{candidate_id}/profiles/profile-api-1/reject",
            headers=reviewer,
            json={
                "expected_governance_version": 2,
                "idempotency_key": "api-exact-review-2",
            },
        )

    assert profile_id
    assert accepted.status_code == 200
    assert accepted.json()["current_profile_id"] == "profile-api-1"
    assert wrong_version.status_code == 409
    assert wrong_version.json()["error"]["code"] == "candidate_profile_governance_conflict"


@pytest.mark.asyncio
async def test_candidate_api_requires_actor_and_reviewer_role_for_mutations() -> None:
    http = await client()
    async with http:
        missing = await http.post("/api/v1/candidates", json={})
        learner = await http.post(
            "/api/v1/candidates",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json={},
        )

    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "development_identity_required"
    assert learner.status_code == 403
    assert learner.json()["error"]["code"] == "candidate_reviewer_role_required"


@pytest.mark.asyncio
async def test_candidate_list_status_and_request_revision_are_authorized() -> None:
    http = await client()
    reviewer = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with http:
        created = await http.post("/api/v1/candidates", headers=reviewer, json={})
        candidate_id = created.json()["candidate_id"]
        await http.post(
            f"/api/v1/candidates/{candidate_id}/documents",
            headers=reviewer,
            json={"document_id": str(DOCUMENT_ID)},
        )
        await http.post(
            f"/api/v1/candidates/{candidate_id}/profiles",
            headers=reviewer,
            json={"profile_id": "profile-api-1"},
        )
        listed = await http.get("/api/v1/candidates", headers=reviewer)
        status_response = await http.get(
            f"/api/v1/candidates/{candidate_id}/extraction-status", headers=reviewer
        )
        revised = await http.post(
            f"/api/v1/candidates/{candidate_id}/request-revision",
            headers=reviewer,
            json={"expected_profile_version": 1, "idempotency_key": "api-review-revision"},
        )

    assert listed.status_code == 200
    assert any(item["candidate_id"] == candidate_id for item in listed.json()["items"])
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "succeeded"
    assert status_response.json()["documents"][0]["review_state"] == "pending_review"
    assert revised.status_code == 200
    assert revised.json()["review_state"] == "needs_revision"


@pytest.mark.asyncio
async def test_candidate_list_supports_status_limit_cursor_and_deterministic_sort() -> None:
    http = await client()
    reviewer = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with http:
        first = await http.post("/api/v1/candidates", headers=reviewer, json={})
        second = await http.post("/api/v1/candidates", headers=reviewer, json={})
        page = await http.get(
            "/api/v1/candidates?status=active&limit=1&sort=created_at_asc",
            headers=reviewer,
        )
        cursor = page.json()["next_cursor"]
        next_page = await http.get(
            f"/api/v1/candidates?status=active&limit=1&sort=created_at_asc&cursor={cursor}",
            headers=reviewer,
        )

    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["items"][0]["candidate_id"] == first.json()["candidate_id"]
    assert next_page.status_code == 200
    assert next_page.json()["items"][0]["candidate_id"] == second.json()["candidate_id"]


@pytest.mark.asyncio
async def test_candidate_create_returns_human_friendly_code_and_searches_by_name() -> None:
    http = await client()
    reviewer = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with http:
        created = await http.post(
            "/api/v1/candidates",
            headers=reviewer,
            json={"display_name": "Nguyễn Văn A", "email": "nguyen.a@example.com"},
        )
        code = created.json()["candidate_code"]
        searched = await http.get(
            "/api/v1/candidates?q=Nguyễn",
            headers=reviewer,
        )

    assert created.status_code == 201
    assert code.startswith("CAN-")
    assert searched.status_code == 200
    assert searched.json()["items"][0]["candidate_code"] == code
    assert searched.json()["items"][0]["display_name"] == "Nguyễn Văn A"


@pytest.mark.asyncio
async def test_candidate_cv_version_is_explicit_and_same_candidate_gets_version_two() -> None:
    http = await client()
    reviewer = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    second_document_id = UUID("33333333-3333-3333-3333-333333333333")
    async with http:
        await http.post(
            "/api/v1/candidates",
            headers=reviewer,
            json={"display_name": "Candidate with CV history"},
        )
        candidate_id = (await http.get("/api/v1/candidates", headers=reviewer)).json()["items"][-1]["candidate_id"]
        documents = http._transport.app.state.document_repository
        await documents.create(
            StoredDocument(
                id=second_document_id,
                owner_actor_id=REVIEWER_ID,
                organization_id=ORG_PAI_ID,
                kind=StoredDocumentKind.CV,
                content_type="application/pdf",
                byte_size=11,
                sha256="c" * 64,
                object_key="candidate/api-v2.pdf",
                status=DocumentStatus.CLEAN,
                retention_until=datetime.now(UTC) + timedelta(days=1),
            )
        )
        first = await http.post(
            f"/api/v1/candidates/{candidate_id}/cv/versions",
            headers=reviewer,
            json={"document_id": str(DOCUMENT_ID)},
        )
        second = await http.post(
            f"/api/v1/candidates/{candidate_id}/cv/versions",
            headers=reviewer,
            json={"document_id": str(second_document_id)},
        )
        history = await http.get(
            f"/api/v1/candidates/{candidate_id}/cv/versions",
            headers=reviewer,
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert [item["version"] for item in history.json()["items"]] == [2, 1]


@pytest.mark.asyncio
async def test_review_response_uses_stable_version_and_replays_idempotently() -> None:
    http = await client()
    reviewer = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with http:
        created = await http.post("/api/v1/candidates", headers=reviewer, json={})
        candidate_id = created.json()["candidate_id"]
        await http.post(
            f"/api/v1/candidates/{candidate_id}/documents",
            headers=reviewer,
            json={"document_id": str(DOCUMENT_ID)},
        )
        await http.post(
            f"/api/v1/candidates/{candidate_id}/profiles",
            headers=reviewer,
            json={"profile_id": "profile-api-1"},
        )
        payload = {"expected_profile_version": 1, "idempotency_key": "same-review"}
        accepted = await http.post(
            f"/api/v1/candidates/{candidate_id}/accept", headers=reviewer, json=payload
        )
        replay = await http.post(
            f"/api/v1/candidates/{candidate_id}/accept", headers=reviewer, json=payload
        )
        conflict = await http.post(
            f"/api/v1/candidates/{candidate_id}/reject",
            headers=reviewer,
            json=payload,
        )

    assert accepted.status_code == 200
    assert accepted.json()["version"] == 1
    assert replay.status_code == 200
    assert replay.json() == accepted.json()
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "candidate_review_idempotency_conflict"


@pytest.mark.asyncio
async def test_document_association_returns_candidate_and_document_references() -> None:
    http = await client()
    reviewer = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with http:
        created = await http.post("/api/v1/candidates", headers=reviewer, json={})
        candidate_id = created.json()["candidate_id"]
        attached = await http.post(
            f"/api/v1/candidates/{candidate_id}/documents",
            headers=reviewer,
            json={"document_id": str(DOCUMENT_ID)},
        )

    assert attached.status_code == 201
    assert attached.json()["candidate_id"] == candidate_id
    assert attached.json()["document_id"] == str(DOCUMENT_ID)
    assert "candidate_document_id" in attached.json()
