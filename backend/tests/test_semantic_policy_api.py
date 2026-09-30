import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.authorization.fixtures import REVIEWER_ID
from app.authorization.repository import InMemorySubjectRepository
from app.capability_analysis.domain_packs.it_ai import IT_AI_PACK
from app.main import create_app
from app.matching.repository import InMemoryRoleProfileRepository
from app.matching.schemas import RoleProfileStatus
from app.semantic_policy.repository import InMemorySemanticPolicyRepository
from app.semantic_policy.schemas import SemanticPolicyRef
from app.semantic_policy.service import SemanticPolicyResolver
from tests.test_matching_repository import active_role


def _payload() -> dict[str, str]:
    return {
        "policy_id": "fixture-policy",
        "version": "1",
        "domain_pack_id": "it_ai",
        "domain_pack_version": "1",
        "domain_pack_checksum": "sha256:it-ai-v1",
        "description": "fixture policy",
    }


async def _client() -> AsyncClient:
    app: FastAPI = create_app()
    app.state.semantic_policy_repository = InMemorySemanticPolicyRepository()
    app.state.semantic_policy_resolver = SemanticPolicyResolver(
        app.state.semantic_policy_repository,
        (IT_AI_PACK,),
    )
    app.state.subject_repository = InMemorySubjectRepository.fixture()
    app.state.role_profile_repository = InMemoryRoleProfileRepository(
        [active_role().model_copy(update={"status": RoleProfileStatus.PROVISIONAL})]
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_policy_api_exposes_draft_activate_and_exact_read() -> None:
    client = await _client()
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with client:
        created = await client.post("/semantic-policies", headers=headers, json=_payload())
        activated = await client.post(
            "/semantic-policies/fixture-policy/versions/1/activate", headers=headers
        )
        fetched = await client.get(
            "/semantic-policies/fixture-policy/versions/1", headers=headers
        )

    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert fetched.status_code == 200
    assert fetched.json()["version"] == "1"


@pytest.mark.asyncio
async def test_policy_api_cannot_create_active_or_use_latest_version() -> None:
    client = await _client()
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with client:
        invalid = await client.post(
            "/semantic-policies", headers=headers, json={**_payload(), "status": "active"}
        )
        missing = await client.get(
            "/semantic-policies/fixture-policy/versions/latest", headers=headers
        )

    assert invalid.status_code == 422
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_role_profile_binding_requires_exact_policy_and_preserves_audit_boundary() -> None:
    client = await _client()
    headers = {"X-PAI-Actor-ID": str(REVIEWER_ID)}
    async with client:
        await client.post("/semantic-policies", headers=headers, json=_payload())
        await client.post(
            "/semantic-policies/fixture-policy/versions/1/activate", headers=headers
        )
        response = await client.put(
            "/role-profiles/role-ai-engineer/semantic-policy",
            headers=headers,
            json={"role_profile_version": "1.0", **_payload_policy_ref()},
        )

    assert response.status_code == 200
    profile = await client._transport.app.state.role_profile_repository.get_version(  # type: ignore[attr-defined]
        "role-ai-engineer", "1.0"
    )
    assert profile is not None
    assert profile.semantic_policy_ref == SemanticPolicyRef(
        policy_id="fixture-policy", policy_version="1"
    )


def _payload_policy_ref() -> dict[str, str]:
    return {"policy_id": "fixture-policy", "policy_version": "1"}
