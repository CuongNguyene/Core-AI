from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.authorization.fixtures import LEARNER_ID, SME_ID
from app.authorization.repository import InMemorySubjectRepository
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import DocumentKind, ReviewState
from app.main import create_app
from app.matching.api import router as _matching_router  # noqa: F401
from app.matching.repository import (
    InMemoryPreliminaryMatchRepository,
    InMemoryRoleProfileRepository,
)
from app.matching.service import PreliminaryMatchService
from tests.test_extraction_repository import pending_profile, queued_job
from tests.test_matching_repository import active_role


async def matching_client() -> AsyncClient:
    app: FastAPI = create_app()
    extraction = InMemoryExtractionRepository()
    for job_id, profile_id, state in (
        ("job-1", "profile-1", ReviewState.ACCEPTED),
        ("job-jd", "profile-jd", ReviewState.ACCEPTED),
    ):
        job = queued_job().model_copy(update={"id": job_id})
        profile = pending_profile().model_copy(
            update={
                "id": profile_id,
                "job_id": job_id,
                "document_id": "fixture-jd-basic"
                if profile_id == "profile-jd"
                else "fixture-cv-basic",
                "document_kind": DocumentKind.JD if profile_id == "profile-jd" else DocumentKind.CV,
                "review_state": state,
                "accepted_by": "reviewer-1",
                "accepted_at": datetime.now(UTC),
            }
        )
        await extraction.enqueue(job)
        await extraction.mark_succeeded(job_id, profile)
    matches = InMemoryPreliminaryMatchRepository()
    app.state.preliminary_match_service = PreliminaryMatchService(
        extraction,
        InMemoryRoleProfileRepository(
            [
                active_role().model_copy(
                    update={
                        "source_jd_profile_id": "profile-jd",
                        "source_jd_profile_version": 1,
                    }
                )
            ]
        ),
        matches,
    )
    app.state.preliminary_match_repository = matches
    app.state.subject_repository = InMemorySubjectRepository.fixture()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_post_match_returns_criteria_without_overall_score() -> None:
    client = await matching_client()
    async with client:
        response = await client.post(
            "/preliminary-matches",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json={
                "cv_profile_id": "profile-1",
                "role_profile_id": "role-ai-engineer",
                "correlation_id": "corr-1",
            },
        )

    assert response.status_code == 201
    assert response.json()["human_review_required"] is True
    assert response.json()["criterion_results"][0]["human_review_required"] is True
    assert "overall_score" not in response.json()


@pytest.mark.asyncio
async def test_owner_can_read_own_preliminary_match_but_not_another_owners() -> None:
    client = await matching_client()
    headers = {"X-PAI-Actor-ID": str(LEARNER_ID)}
    async with client:
        created = await client.post(
            "/preliminary-matches",
            headers=headers,
            json={
                "cv_profile_id": "profile-1",
                "role_profile_id": "role-ai-engineer",
                "correlation_id": "corr-1",
            },
        )
        own_read = await client.get(f"/preliminary-matches/{created.json()['id']}", headers=headers)
        denied = await client.get(
            f"/preliminary-matches/{created.json()['id']}",
            headers={"X-PAI-Actor-ID": str(SME_ID)},
        )

    assert own_read.status_code == 200
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "preliminary_match_access_denied"
