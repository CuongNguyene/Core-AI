import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.authorization.repository import InMemorySubjectRepository
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import (
    CVExtractionOutput,
    DocumentKind,
    EvidenceStatus,
    ExtractedClaim,
    ExtractionJob,
    ExtractionProfile,
    JDRequirementExtractionOutputV2,
    JDRequirementExtractionV2,
    JDRequirementModality,
    JobStatus,
    RequirementFieldProvenance,
    ReviewState,
    SourceLocator,
)
from app.main import create_app


def sample_profile() -> ExtractionProfile:
    return ExtractionProfile(
        id="profile-1",
        job_id="job-1",
        document_id="fixture-cv-basic",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        version=1,
        review_state=ReviewState.PENDING_REVIEW,
        output=CVExtractionOutput(
            skills=[
                ExtractedClaim(
                    value="Python",
                    confidence=0.9,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_locator=SourceLocator(
                        document_id="fixture-cv-basic",
                        section="skills",
                        start_offset=16,
                        end_offset=22,
                    ),
                    source_excerpt="Python",
                )
            ],
            experience=[],
            education=[],
        ),
        audit={
            "provider": "mock",
            "model": "mock-v1",
            "prompt_template_version": "1.0",
            "policy_version": "privacy-v1",
        },
    )


def sample_jd_v2_profile() -> ExtractionProfile:
    content = "Role: Backend Engineer\nRequirements: Python and FastAPI experience.\n"
    start = content.index("Python")
    return ExtractionProfile(
        id="jd-profile-1",
        job_id="jd-job-1",
        document_id="fixture-jd-basic",
        document_kind=DocumentKind.JD,
        owner_actor_id=LEARNER_ID,
        version=1,
        review_state=ReviewState.PENDING_REVIEW,
        output=JDRequirementExtractionOutputV2(
            requirements=[
                JDRequirementExtractionV2(
                    requirement_id="req-python",
                    statement="Use Python",
                    criterion_dimension="skill",
                    modality=JDRequirementModality.MUST,
                    evidence_terms=["Python"],
                    confidence=0.9,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_locator=SourceLocator(
                        document_id="fixture-jd-basic",
                        section="requirements",
                        start_offset=start,
                        end_offset=start + len("Python"),
                    ),
                    source_excerpt="Python",
                    provenance={"statement": RequirementFieldProvenance.JD_EXTRACTION},
                )
            ]
        ),
        audit={"provider": "mock", "model": "mock-v2", "policy_version": "privacy-v1"},
    )


async def client_with_repository() -> tuple[AsyncClient, InMemoryExtractionRepository]:
    app: FastAPI = create_app()
    repository = InMemoryExtractionRepository()
    app.state.extraction_repository = repository
    app.state.subject_repository = InMemorySubjectRepository.fixture()
    return (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver"),
        repository,
    )


@pytest.mark.asyncio
async def test_create_job_requires_development_actor_header() -> None:
    client, _ = await client_with_repository()
    async with client:
        response = await client.post(
            "/extraction-jobs",
            json={"document_id": "fixture-cv-basic", "document_kind": "cv"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "development_identity_required"


@pytest.mark.asyncio
async def test_owner_can_create_and_read_extraction_job() -> None:
    client, _ = await client_with_repository()
    headers = {"X-PAI-Actor-ID": str(LEARNER_ID)}
    async with client:
        created = await client.post(
            "/extraction-jobs",
            headers=headers,
            json={"document_id": "fixture-cv-basic", "document_kind": "cv"},
        )
        job_id = created.json()["id"]
        fetched = await client.get(f"/extraction-jobs/{job_id}", headers=headers)

    assert created.status_code == 201
    assert created.json()["status"] == "queued"
    assert created.json()["stage"] == "queued"
    assert created.json()["completed_units"] is None
    assert created.json()["total_units"] is None
    assert fetched.status_code == 200
    assert fetched.json()["owner_actor_id"] == str(LEARNER_ID)


@pytest.mark.asyncio
async def test_owner_can_cancel_active_extraction_job() -> None:
    client, _ = await client_with_repository()
    headers = {"X-PAI-Actor-ID": str(LEARNER_ID)}
    async with client:
        created = await client.post(
            "/extraction-jobs",
            headers=headers,
            json={"document_id": "fixture-jd-basic", "document_kind": "jd"},
        )
        cancelled = await client.delete(
            f"/extraction-jobs/{created.json()['id']}", headers=headers
        )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "failed"
    assert cancelled.json()["error_category"] == "cancelled_by_user"

@pytest.mark.asyncio
async def test_reviewer_correction_creates_new_profile_version() -> None:
    client, repository = await client_with_repository()
    await repository.enqueue(
        ExtractionJob(
            id="job-1",
            document_id="fixture-cv-basic",
            document_kind=DocumentKind.CV,
            owner_actor_id=LEARNER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await repository.mark_succeeded("job-1", sample_profile())
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with client:
        response = await client.post(
            "/extraction-profiles/profile-1/corrections",
            headers=headers,
            json={"output": sample_profile().output.model_dump(mode="json")},
        )

    assert response.status_code == 201
    assert response.json()["version"] == 2
    assert response.json()["review_state"] == "corrected"


@pytest.mark.asyncio
async def test_reviewer_correction_validates_v2_requirement_identity_and_source() -> None:
    client, repository = await client_with_repository()
    await repository.enqueue(
        ExtractionJob(
            id="jd-job-1",
            document_id="fixture-jd-basic",
            document_kind=DocumentKind.JD,
            owner_actor_id=LEARNER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await repository.mark_succeeded("jd-job-1", sample_jd_v2_profile())
    invalid = sample_jd_v2_profile().output.model_dump(mode="json")
    invalid["requirements"][0]["source_excerpt"] = "not present"
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}

    async with client:
        response = await client.post(
            "/extraction-profiles/jd-profile-1/corrections",
            headers=headers,
            json={"output": invalid},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_correction_output"


@pytest.mark.asyncio
async def test_reviewer_correction_binds_v2_locator_to_original_document() -> None:
    client, repository = await client_with_repository()
    await repository.enqueue(
        ExtractionJob(
            id="jd-job-1",
            document_id="fixture-jd-basic",
            document_kind=DocumentKind.JD,
            owner_actor_id=LEARNER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await repository.mark_succeeded("jd-job-1", sample_jd_v2_profile())
    corrected = sample_jd_v2_profile().output.model_dump(mode="json")
    corrected["requirements"][0]["source_locator"]["document_id"] = "provider-placeholder"
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}

    async with client:
        response = await client.post(
            "/extraction-profiles/jd-profile-1/corrections",
            headers=headers,
            json={"output": corrected},
        )

    assert response.status_code == 201
    assert (
        response.json()["output"]["requirements"][0]["source_locator"]["document_id"]
        == "fixture-jd-basic"
    )


@pytest.mark.asyncio
async def test_reviewer_can_read_normalized_jd_review_projection() -> None:
    client, repository = await client_with_repository()
    await repository.enqueue(
        ExtractionJob(
            id="jd-job-1",
            document_id="fixture-jd-basic",
            document_kind=DocumentKind.JD,
            owner_actor_id=LEARNER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await repository.mark_succeeded("jd-job-1", sample_jd_v2_profile())
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}

    async with client:
        response = await client.get(
            "/extraction-profiles/jd-profile-1/review",
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_kind"] == "jd"
    assert payload["requirement_count"] == 1
    assert payload["groups"][0]["key"] == "required"
    assert payload["requirements"][0]["evidence_location"]["kind"] == "text_span"
    assert "source_locator" not in payload["requirements"][0]


@pytest.mark.asyncio
async def test_reviewer_jd_item_correction_creates_new_version_without_mutating_v1() -> None:
    client, repository = await client_with_repository()
    profile = sample_jd_v2_profile()
    await repository.enqueue(
        ExtractionJob(
            id="jd-job-1",
            document_id="fixture-jd-basic",
            document_kind=DocumentKind.JD,
            owner_actor_id=LEARNER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await repository.mark_succeeded("jd-job-1", profile)
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with client:
        review = await client.get("/extraction-profiles/jd-profile-1/review", headers=headers)
        item_id = review.json()["requirements"][0]["review_item_id"]
        response = await client.post(
            "/extraction-profiles/jd-profile-1/review-corrections",
            headers=headers,
            json={
                "expected_version": 1,
                "review_item_id": item_id,
                "operation": "correct",
                "statement": "Use Python and FastAPI",
                "modality": "must",
                "criterion_dimension": "skill",
                "reason": "Clarified requirement",
            },
        )
        original = await client.get("/extraction-profiles/jd-profile-1", headers=headers)

    assert response.status_code == 201
    assert response.json()["version"] == 2
    assert response.json()["review_state"] == "corrected"
    assert response.json()["audit"]["actor_id"] == str(REVIEWER_ID)
    assert original.json()["version"] == 1
    assert original.json()["output"]["requirements"][0]["statement"] == "Use Python"


@pytest.mark.asyncio
async def test_reviewer_jd_item_correction_rejects_stale_version() -> None:
    client, repository = await client_with_repository()
    await repository.enqueue(
        ExtractionJob(
            id="jd-job-1",
            document_id="fixture-jd-basic",
            document_kind=DocumentKind.JD,
            owner_actor_id=LEARNER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await repository.mark_succeeded("jd-job-1", sample_jd_v2_profile())
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with client:
        review = await client.get("/extraction-profiles/jd-profile-1/review", headers=headers)
        item_id = review.json()["requirements"][0]["review_item_id"]
        response = await client.post(
            "/extraction-profiles/jd-profile-1/review-corrections",
            headers=headers,
            json={
                "expected_version": 99,
                "review_item_id": item_id,
                "operation": "remove",
                "reason": "Duplicate",
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "extraction_profile_version_conflict"


@pytest.mark.asyncio
async def test_reviewer_accepts_current_extraction_profile() -> None:
    client, repository = await client_with_repository()
    await repository.enqueue(
        ExtractionJob(
            id="job-1",
            document_id="fixture-cv-basic",
            document_kind=DocumentKind.CV,
            owner_actor_id=LEARNER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await repository.mark_succeeded("job-1", sample_profile())
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with client:
        response = await client.post(
            "/extraction-profiles/profile-1/accept",
            headers=headers,
            json={"expected_version": 1},
        )

    assert response.status_code == 200
    assert response.json()["review_state"] == "accepted"
    assert response.json()["accepted_by"] == str(REVIEWER_ID)


@pytest.mark.asyncio
async def test_accept_rejects_non_reviewer_and_stale_version() -> None:
    client, repository = await client_with_repository()
    await repository.enqueue(
        ExtractionJob(
            id="job-1",
            document_id="fixture-cv-basic",
            document_kind=DocumentKind.CV,
            owner_actor_id=LEARNER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await repository.mark_succeeded("job-1", sample_profile())
    async with client:
        forbidden = await client.post(
            "/extraction-profiles/profile-1/accept",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json={"expected_version": 1},
        )
        stale = await client.post(
            "/extraction-profiles/profile-1/accept",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
            json={"expected_version": 2},
        )

    assert forbidden.status_code == 403
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "extraction_profile_version_conflict"
