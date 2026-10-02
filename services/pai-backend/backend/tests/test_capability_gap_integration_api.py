from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.authorization.fixtures import LEARNER_ID, ORG_PAI_ID, subject_fixture
from app.candidate.repository import InMemoryCandidateRepository
from app.candidate.schemas import Candidate, CandidateReviewState
from app.capability_analysis.errors import CurrentTargetNotUsableError
from app.integration.actor_context import (
    SignedActorContextVerifier,
    actor_context_headers,
)
from app.integration.nonce_store import InMemoryActorContextNonceStore
from app.main import create_app
from app.matching.schemas import CriterionDimension, RequirementClassification, RoleRequirement
from app.role_registry.repository import InMemoryRoleRegistryRepository
from app.role_registry.schemas import Role, RoleStatus
from app.shared.config import Settings
from tests.test_capability_analysis_service import learner, service_with

CANDIDATE_ID = UUID("10000000-0000-0000-0000-000000000001")
ROLE_ID = UUID("20000000-0000-0000-0000-000000000001")
AUTH_PRIVATE_KEY = Ed25519PrivateKey.generate()
AUTH_NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)


async def capability_integration_client() -> tuple[AsyncClient, InMemoryCandidateRepository]:
    app: FastAPI = create_app(
        Settings(app_env="development", integration_api_key=SecretStr("integration-test-key"))
    )
    service, _, _ = await service_with(
        target_requirements=[
            RoleRequirement(
                id="critical-python",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.ROLE_CRITICAL,
                evidence_terms=["Python"],
                confidence_threshold=1.0,
                assessment_recommendation="practical_task",
                rubric_version="1.0",
            ),
            RoleRequirement(
                id="missing-kubernetes",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.PREFERRED,
                evidence_terms=["Kubernetes"],
                confidence_threshold=0.8,
                assessment_recommendation="practical_task",
                rubric_version="1.0",
            ),
        ]
    )
    candidates = InMemoryCandidateRepository()
    await candidates.create(
        Candidate(
            candidate_id=CANDIDATE_ID,
            candidate_code="CAN-1001",
            display_name="Nguyen Van A",
            organization_id=ORG_PAI_ID,
            created_by_actor_id=LEARNER_ID,
            review_state=CandidateReviewState.PENDING_REVIEW,
            current_profile_id="cv-profile-1",
            current_profile_version=3,
        )
    )
    profile_repository = service._role_profiles  # type: ignore[attr-defined]
    profile_repository._profiles[0] = profile_repository._profiles[0].model_copy(  # type: ignore[attr-defined]
        update={"role_id": ROLE_ID}
    )
    role_registry = InMemoryRoleRegistryRepository()
    await role_registry.create_role(
        Role(
            id=ROLE_ID,
            organization_id=ORG_PAI_ID,
            role_code="ROLE-ENG-01",
            title="Platform Engineer",
            created_by=LEARNER_ID,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            status=RoleStatus.ACTIVE,
        )
    )
    service._candidates = candidates  # type: ignore[attr-defined]
    service._role_registry = role_registry  # type: ignore[attr-defined]
    app.state.capability_gap_analysis_service = service
    app.state.subject_repository = subject_fixture()
    app.state.actor_context_verifier = SignedActorContextVerifier(
        public_keys={"lms-key-1": AUTH_PRIVATE_KEY.public_key()},
        now=lambda: AUTH_NOW,
    )
    app.state.actor_context_nonce_store = InMemoryActorContextNonceStore()
    return (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver"),
        candidates,
    )


def headers(key: str = "analysis-key-001") -> dict[str, str]:
    return {
        "Authorization": "Bearer integration-test-key",
        "Idempotency-Key": key,
        **actor_context_headers(
            private_key=AUTH_PRIVATE_KEY,
            key_id="lms-key-1",
            actor_id=LEARNER_ID,
            organization_id=ORG_PAI_ID,
            issued_at=AUTH_NOW,
            expires_at=AUTH_NOW + timedelta(seconds=30),
            nonce=f"capability-gap-{uuid4()}",
        ),
    }


def request_body(target: str = "role-current@1") -> dict[str, object]:
    return {
        "schema_version": "v1",
        "data": {"current_target_reference": target},
    }


@pytest.mark.asyncio
async def test_candidate_analysis_resolves_profile_and_returns_v1_projection() -> None:
    client, _ = await capability_integration_client()
    async with client:
        response = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers(),
            json=request_body(),
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["schema_version"] == "v1"
    assert payload["data"]["candidate_reference"] == str(CANDIDATE_ID)
    assert payload["data"]["analysis_id"] == "analysis-key-001"
    assert payload["data"]["status"] == "ready"
    assert payload["data"]["analysis_version"] == 1
    assert "cv_profile_id" not in payload["data"]
    assert "organization_id" not in payload["data"]


@pytest.mark.asyncio
async def test_historical_analysis_get_projects_human_identity_metadata() -> None:
    client, _ = await capability_integration_client()
    async with client:
        created = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("identity-projection-key"),
            json=request_body(),
        )
        response = await client.get(
            f"/api/v1/integration/capability-analyses/{created.json()['data']['analysis_id']}",
            headers=headers("identity-projection-key"),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["candidate"] == {
        "candidate_id": str(CANDIDATE_ID),
        "candidate_code": "CAN-1001",
        "display_name": "Nguyen Van A",
    }
    assert data["role"] == {
        "role_id": str(ROLE_ID),
        "role_code": "ROLE-ENG-01",
        "title": "Platform Engineer",
    }
    assert data["candidate_profile"]["profile_id"] == "cv-profile-1"
    assert data["candidate_profile"]["profile_version"] == 3
    assert data["role_profile"]["profile_id"] == "role-current"
    assert data["role_profile"]["profile_version"] == "1"


@pytest.mark.asyncio
async def test_analysis_history_exposes_real_analysis_version_without_fabrication() -> None:
    client, _ = await capability_integration_client()
    async with client:
        created = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("history-version-key"),
            json=request_body(),
        )
        response = await client.get(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("history-version-read"),
        )

    assert created.status_code == 201
    assert response.status_code == 200
    item = next(
        item
        for item in response.json()["data"]["items"]
        if item["analysis_id"] == created.json()["data"]["analysis_id"]
    )
    assert item["analysis_version"] == 1
    assert item["created_at"] is None


@pytest.mark.asyncio
async def test_learning_decision_projection_is_read_only_and_scoped_to_analysis() -> None:
    client, _ = await capability_integration_client()
    async with client:
        created = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("learning-decision-key"),
            json=request_body(),
        )
        response = await client.get(
            f"/api/v1/integration/capability-analyses/{created.json()['data']['analysis_id']}/learning-decision",
            headers=headers("learning-decision-read"),
        )

    assert created.status_code == 201
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["analysis_id"] == created.json()["data"]["analysis_id"]
    assert len(data["learning_readiness"]["included_learning_items"]) == 1
    assert data["learning_readiness"]["included_learning_items"][0]["requirement_ref"] == "critical-python"
    assert "generation_allowed" in data["learning_readiness"]
    assert "current_profile_id" not in str(data)


@pytest.mark.asyncio
async def test_same_idempotency_key_returns_same_analysis() -> None:
    client, _ = await capability_integration_client()
    async with client:
        first = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("retry-key"),
            json=request_body(),
        )
        second = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("retry-key"),
            json=request_body(),
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["data"]["analysis_id"] == first.json()["data"]["analysis_id"]


@pytest.mark.asyncio
async def test_reused_idempotency_key_with_different_target_is_rejected() -> None:
    client, _ = await capability_integration_client()
    async with client:
        first = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("conflict-key"),
            json=request_body("role-current@1"),
        )
        conflict = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("conflict-key"),
            json=request_body("role-current@2"),
        )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "capability_analysis_idempotency_conflict"


@pytest.mark.asyncio
async def test_missing_idempotency_key_fails_closed() -> None:
    client, _ = await capability_integration_client()
    request_headers = headers()
    request_headers.pop("Idempotency-Key")
    async with client:
        response = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=request_headers,
            json=request_body(),
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "idempotency_key_required"


@pytest.mark.asyncio
async def test_evidence_endpoint_resolves_projected_canonical_reference() -> None:
    client, _ = await capability_integration_client()
    async with client:
        created = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("evidence-key"),
            json=request_body(),
        )
        gap = next(
            item
            for item in created.json()["data"]["gaps"]
            if item["evidence_references"]
        )
        response = await client.get(
            f"/api/v1/integration/capability-analyses/{created.json()['data']['analysis_id']}"
            f"/gaps/{gap['gap_reference']}/evidence",
            headers=headers("evidence-key"),
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["items"]
    assert {item["reference"] for item in payload["items"]} == set(
        gap["evidence_references"]
    )
    assert "cv_profile_id" not in payload
    assert "organization_id" not in payload
    assert "actor_id" not in payload


@pytest.mark.asyncio
async def test_evidence_endpoint_returns_empty_for_gap_without_evidence() -> None:
    client, _ = await capability_integration_client()
    async with client:
        created = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("empty-evidence-key"),
            json=request_body(),
        )
        gap = next(
            item
            for item in created.json()["data"]["gaps"]
            if not item["evidence_references"]
        )
        response = await client.get(
            f"/api/v1/integration/capability-analyses/{created.json()['data']['analysis_id']}"
            f"/gaps/{gap['gap_reference']}/evidence",
            headers=headers("empty-evidence-key"),
        )

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_missing_target_is_not_normalized_as_idempotency_conflict() -> None:
    client, _ = await capability_integration_client()
    service = client._transport.app.state.capability_gap_analysis_service  # type: ignore[attr-defined]

    with pytest.raises(CurrentTargetNotUsableError):
        await service.create_for_candidate(
            candidate_id=CANDIDATE_ID,
            current_target_reference="missing-role@1",
            future_target_reference=None,
            idempotency_key="missing-target-001",
            actor=learner(),
        )


@pytest.mark.asyncio
async def test_human_assisted_reanalysis_creates_new_analysis_from_selected_evidence() -> None:
    client, _ = await capability_integration_client()
    async with client:
        source = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("assisted-source"),
            json=request_body(),
        )
        source_gap = next(
            item for item in source.json()["data"]["gaps"] if item["evidence_references"]
        )
        assisted = await client.post(
            f"/api/v1/integration/capability-analyses/{source.json()['data']['analysis_id']}"
            "/reanalyse-with-evidence",
            headers=headers("assisted-reanalysis"),
            json={
                "schema_version": "v1",
                "data": {
                    "evidence_selections": [
                        {
                            "requirement_id": source_gap["requirement_reference"],
                            "selected_evidence_refs": source_gap["evidence_references"],
                        }
                    ]
                },
            },
        )

    assert assisted.status_code == 201
    assert assisted.json()["data"]["analysis_id"] != source.json()["data"]["analysis_id"]
    assert assisted.json()["data"]["candidate_reference"] == str(CANDIDATE_ID)
    assert assisted.json()["data"]["human_assisted"]["source_analysis_id"] == source.json()["data"]["analysis_id"]


@pytest.mark.asyncio
async def test_candidate_evidence_projection_returns_canonical_pool_not_assessment_evidence() -> None:
    client, _ = await capability_integration_client()
    async with client:
        source = await client.post(
            f"/api/v1/integration/candidates/{CANDIDATE_ID}/capability-analyses",
            headers=headers("candidate-evidence-source"),
            json=request_body(),
        )
        response = await client.get(
            f"/api/v1/integration/capability-analyses/{source.json()['data']['analysis_id']}"
            "/candidate-evidence",
            headers=headers("candidate-evidence-read"),
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["analysis_id"] == source.json()["data"]["analysis_id"]
    assert payload["items"]
    assert all(set(item) == {"evidence_ref", "evidence_type", "label", "source_label", "excerpt"} for item in payload["items"])
    assert all(len(item["excerpt"] or "") <= 500 for item in payload["items"])
