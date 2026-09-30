import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.authorization.repository import InMemorySubjectRepository
from app.main import create_app
from app.matching.schemas import RoleProfileStatus
from tests.test_capability_analysis_service import service_with


async def capability_client() -> AsyncClient:
    app: FastAPI = create_app()
    service, _, portfolios = await service_with()
    app.state.capability_gap_analysis_service = service
    app.state.capability_gap_portfolio_repository = portfolios
    app.state.subject_repository = InMemorySubjectRepository.fixture()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def valid_ids(*, future_target_profile_id: str | None = None) -> dict[str, str]:
    payload = {
        "cv_profile_id": "cv-profile-1",
        "current_target_profile_id": "role-current",
        "correlation_id": "capability-api-1",
    }
    if future_target_profile_id is not None:
        payload["future_target_profile_id"] = future_target_profile_id
    return payload


@pytest.mark.asyncio
async def test_api_accepts_references_not_inline_candidate_profile() -> None:
    client = await capability_client()
    async with client:
        response = await client.post(
            "/capability-gap-portfolios",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json=valid_ids(),
        )

    assert response.status_code == 201
    assert "combined_readiness_score" not in response.json()
    assert response.json()["current_role"]["target_type"] == "current_role"
    assert "candidate_profile" not in response.json()


@pytest.mark.asyncio
async def test_api_rejects_inline_profile_and_non_owner_read() -> None:
    client = await capability_client()
    async with client:
        rejected = await client.post(
            "/capability-gap-portfolios",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json={**valid_ids(), "candidate_profile": {"skills": []}},
        )
        created = await client.post(
            "/capability-gap-portfolios",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json=valid_ids(),
        )
        denied = await client.get(
            f"/capability-gap-portfolios/{created.json()['id']}",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
        )

    assert rejected.status_code == 422
    assert denied.status_code == 200


@pytest.mark.asyncio
async def test_api_rejects_raw_text_in_an_identifier_without_audit_write() -> None:
    client = await capability_client()
    repository = client._transport.app.state.capability_gap_portfolio_repository  # type: ignore[attr-defined]
    async with client:
        response = await client.post(
            "/capability-gap-portfolios",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json={**valid_ids(), "cv_profile_id": "Alice Nguyen CV: phone 0900000000"},
        )

    assert response.status_code == 422
    assert repository.audit_events == []


@pytest.mark.asyncio
async def test_api_rejects_correlation_id_that_exceeds_persistence_limit() -> None:
    client = await capability_client()
    async with client:
        response = await client.post(
            "/capability-gap-portfolios",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json={**valid_ids(), "correlation_id": "c" * 65},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_maps_future_draft_to_safe_error_code() -> None:
    client = await capability_client()
    service = client._transport.app.state.capability_gap_analysis_service  # type: ignore[attr-defined]
    service._role_profiles._profiles.append(  # type: ignore[attr-defined]
        __import__("tests.test_matching_repository", fromlist=["active_role"])
        .active_role()
        .model_copy(update={"id": "role-future", "status": RoleProfileStatus.DRAFT})
    )
    async with client:
        response = await client.post(
            "/capability-gap-portfolios",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json=valid_ids(future_target_profile_id="role-future"),
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "future_target_not_usable"


@pytest.mark.asyncio
async def test_api_maps_missing_semantic_policy_to_safe_error_code() -> None:
    app: FastAPI = create_app()
    service, _, portfolios = await service_with(semantic_policy=None)
    app.state.capability_gap_analysis_service = service
    app.state.capability_gap_portfolio_repository = portfolios
    app.state.subject_repository = InMemorySubjectRepository.fixture()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/capability-gap-portfolios",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json=valid_ids(),
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "semantic_policy_not_configured"
