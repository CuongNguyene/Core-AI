from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.authorization.schemas import ActorContext, Role
from app.course_authoring.repository import InMemoryCourseAuthoringRepository
from app.course_authoring.service import CourseAuthoringService
from app.integration.actor_context import SignedActorContextVerifier, actor_context_headers
from app.integration.course_authoring_api import router
from app.learning_authoring.service import LearningAuthoringNotFoundError
from app.shared.config import Settings
from app.shared.errors import APIError, api_error_handler, request_validation_error_handler

API_KEY = "integration-test-key"
ACTOR_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ORG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def actor() -> ActorContext:
    return ActorContext(
        actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        roles=frozenset({Role.REVIEWER}),
        authentication_method="signed_actor_context",
    )


class ReferenceReader:
    async def get_learning_need(self, artifact_id: str, _actor: ActorContext) -> object:
        if artifact_id != "learning-need-001":
            raise LearningAuthoringNotFoundError(artifact_id)
        return SimpleNamespace(id=artifact_id)

    async def get_learning_objective(self, artifact_id: str, _actor: ActorContext) -> object:
        if artifact_id != "objective-001":
            raise LearningAuthoringNotFoundError(artifact_id)
        return SimpleNamespace(learning_need_ref="learning-need-001")

    async def get_instructional_blueprint(self, artifact_id: str, _actor: ActorContext) -> object:
        if artifact_id != "blueprint-001":
            raise LearningAuthoringNotFoundError(artifact_id)
        return SimpleNamespace(
            objective_refs=["objective-001"],
            learning_need_ref="learning-need-001",
        )


def request_body(*, objective_refs: list[str] | None = None) -> dict[str, object]:
    return {
        "schema_version": "v1",
        "data": {
            "title": "Python foundations",
            "training_brief": {"goal": "Build practical Python foundations"},
            "learner_refs": ["lms-2", "lms-1"],
            "learning_need_refs": ["learning-need-001"],
            "objective_refs": objective_refs if objective_refs is not None else ["objective-001"],
            "instructional_blueprint_ref": "blueprint-001",
            "constraints": {"language": "vi"},
            "mode": "GAP_DRIVEN",
        },
    }


def app_for_api() -> tuple[FastAPI, dict[str, str], Ed25519PrivateKey]:
    private_key = Ed25519PrivateKey.generate()
    now = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
    signed_headers = actor_context_headers(
        private_key=private_key,
        key_id="lms-key-1",
        actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        issued_at=now,
        expires_at=now + timedelta(seconds=30),
        nonce="course-authoring-api-test",
    )
    app = FastAPI()
    app.state.settings = Settings(_env_file=None, integration_api_key=SecretStr(API_KEY))
    app.state.actor_context_verifier = SignedActorContextVerifier(
        public_keys={"lms-key-1": private_key.public_key()},
        actor_resolver=lambda _actor_id, _organization_id: actor(),
        now=lambda: now,
    )
    app.state.course_authoring_service = CourseAuthoringService(
        repository=InMemoryCourseAuthoringRepository(),
        references=ReferenceReader(),
    )
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.include_router(router)
    return (
        app,
        {
            "Authorization": f"Bearer {API_KEY}",
            "Idempotency-Key": "course-authoring-api-test",
            **signed_headers,
        },
        private_key,
    )


async def client() -> tuple[AsyncClient, dict[str, str], Ed25519PrivateKey]:
    app, headers, private_key = app_for_api()
    return (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver"),
        headers,
        private_key,
    )


@pytest.mark.asyncio
async def test_create_course_authoring_request_returns_contract() -> None:
    http, headers, _private_key = await client()
    async with http:
        response = await http.post(
            "/api/v1/course-authoring/requests", headers=headers, json=request_body()
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["schema_version"] == "v1"
    assert payload["data"]["status"] == "DRAFT"
    assert payload["data"]["audience_snapshot_id"] == "audience-snapshot-001"


@pytest.mark.asyncio
async def test_signed_actor_context_nonce_is_rejected_by_shared_store() -> None:
    app, headers, _private_key = app_for_api()

    class NonceStore:
        def __init__(self) -> None:
            self.nonces: set[str] = set()

        async def consume(self, nonce: str, _expires_at: datetime) -> bool:
            if nonce in self.nonces:
                return False
            self.nonces.add(nonce)
            return True

    app.state.actor_context_nonce_store = NonceStore()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        first = await http.post(
            "/api/v1/course-authoring/requests", headers=headers, json=request_body()
        )
        replay = await http.post(
            "/api/v1/course-authoring/requests", headers=headers, json=request_body()
        )

    assert first.status_code == 201
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "ACTOR_CONTEXT_REPLAYED"


@pytest.mark.asyncio
async def test_retrieve_course_authoring_request_preserves_opaque_refs_and_signed_actor() -> None:
    http, headers, private_key = await client()
    async with http:
        created = await http.post(
            "/api/v1/course-authoring/requests", headers=headers, json=request_body()
        )
        request_id = created.json()["data"]["request_id"]
        retrieve_headers = {
            **headers,
            **actor_context_headers(
                private_key=private_key,
                key_id="lms-key-1",
                actor_id=ACTOR_ID,
                organization_id=ORG_ID,
                issued_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
                expires_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC) + timedelta(seconds=30),
                nonce="course-authoring-api-retrieve-test",
            ),
        }
        response = await http.get(
            f"/api/v1/course-authoring/requests/{request_id}", headers=retrieve_headers
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == request_id
    assert data["created_by_actor_ref"] == str(ACTOR_ID)
    assert data["audience_snapshot"]["learner_refs"] == ["lms-2", "lms-1"]
    assert data["learning_need_refs"] == ["learning-need-001"]
    assert data["objective_refs"] == ["objective-001"]
    assert data["instructional_blueprint_ref"] == "blueprint-001"
    assert data["audience_snapshot"]["source"] == "MANUAL_SELECTION"


@pytest.mark.asyncio
async def test_invalid_upstream_reference_returns_stable_error() -> None:
    http, headers, _private_key = await client()
    async with http:
        response = await http.post(
            "/api/v1/course-authoring/requests",
            headers=headers,
            json=request_body(objective_refs=["objective-missing"]),
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "course_authoring_reference_not_found"


@pytest.mark.asyncio
async def test_unknown_request_id_returns_stable_error() -> None:
    http, headers, _private_key = await client()
    async with http:
        response = await http.get(
            "/api/v1/course-authoring/requests/course-authoring-request-missing",
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "course_authoring_request_not_found"


@pytest.mark.asyncio
async def test_course_authoring_requires_api_key() -> None:
    http, headers, _private_key = await client()
    headers.pop("Authorization")
    async with http:
        response = await http.post(
            "/api/v1/course-authoring/requests", headers=headers, json=request_body()
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "integration_authentication_failed"


@pytest.mark.asyncio
async def test_course_authoring_requires_idempotency_key() -> None:
    http, headers, _private_key = await client()
    headers.pop("Idempotency-Key")
    async with http:
        response = await http.post(
            "/api/v1/course-authoring/requests", headers=headers, json=request_body()
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "idempotency_key_required"


def test_course_authoring_router_is_registered_in_application() -> None:
    from app.main import create_app

    app = create_app(Settings(_env_file=None, integration_api_key=SecretStr(API_KEY)))
    paths = app.openapi()["paths"]

    assert "/api/v1/course-authoring/requests" in paths
    assert "get" in paths["/api/v1/course-authoring/requests"]
    assert "/api/v1/course-authoring/requests/{request_id}" in paths
    assert "/api/v1/course-authoring/requests/{request_id}/generate" in paths
    assert "/api/v1/course-authoring/results/{result_id}/revisions" in paths
    assert "/api/v1/course-authoring/requests/{request_id}/results" in paths
    assert "/api/v1/course-authoring/results/{result_id}/ready-for-materialization" in paths
    assert "/api/v1/course-authoring/requests/{request_id}/curriculum-plans" in paths
    assert "/api/v1/course-authoring/curriculum-plans/{plan_id}" in paths
    assert "/api/v1/course-authoring/curriculum-plans/{plan_id}/feedback/preview" in paths
    assert "/api/v1/course-authoring/curriculum-plans/{plan_id}/feedback" in paths
