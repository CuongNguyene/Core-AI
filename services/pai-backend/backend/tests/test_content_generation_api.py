from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient

from app.authorization.schemas import ActorContext
from app.content_generation.service import ContentGenerationService
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.integration.content_generation_api import router
from app.shared.errors import APIError, api_error_handler, request_validation_error_handler


async def client() -> AsyncClient:
    app = FastAPI()
    app.state.content_generation_service = ContentGenerationService()
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.dependency_overrides[verify_integration_api_key] = lambda: None
    app.dependency_overrides[get_signed_actor_context] = lambda: ActorContext(
        actor_id=UUID("00000000-0000-0000-0000-000000000001"),
        organization_id=UUID("00000000-0000-0000-0000-000000000002"),
        roles=frozenset(),
        authentication_method="signed_actor_context",
    )
    app.include_router(router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_create_content_generation_request_returns_created_contract() -> None:
    async with await client() as http:
        response = await http.post(
            "/api/v1/content-generation/requests",
            json={
                "schema_version": "v1",
                "data": {
                    "blueprint_ref": "blueprint-001",
                    "lesson_ref": "lesson-001",
                    "objective_refs": ["objective-001"],
                    "learning_need_refs": ["learning-need-001"],
                    "generation_type": "lesson_content",
                    "constraints": {"language": "vi"},
                },
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["schema_version"] == "v1"
    assert body["data"] == {
        "request_id": "request-001",
        "result_id": "content-001",
        "status": "CREATED",
    }


@pytest.mark.asyncio
async def test_get_content_generation_result_preserves_traceability_and_empty_sections() -> None:
    async with await client() as http:
        created = await http.post(
            "/api/v1/content-generation/requests",
            json={
                "schema_version": "v1",
                "data": {
                    "blueprint_ref": "blueprint-001",
                    "lesson_ref": "lesson-001",
                    "objective_refs": ["objective-001"],
                    "learning_need_refs": ["learning-need-001"],
                    "generation_type": "lesson_content",
                },
            },
        )
        response = await http.get("/api/v1/content-generation/results/content-001")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["request_ref"] == created.json()["data"]["request_id"]
    assert data["lesson_ref"] == "lesson-001"
    assert data["source_blueprint_ref"] == "blueprint-001"
    assert data["objective_refs"] == ["objective-001"]
    assert data["learning_need_refs"] == ["learning-need-001"]
    assert data["version"] == 1
    assert data["supersedes_result_ref"] is None
    assert data["sections"] == []
    assert data["generation_run"] is None


@pytest.mark.asyncio
async def test_invalid_content_generation_reference_is_rejected() -> None:
    async with await client() as http:
        response = await http.post(
            "/api/v1/content-generation/requests",
            json={
                "schema_version": "v1",
                "data": {
                    "blueprint_ref": "",
                    "lesson_ref": "lesson-001",
                    "objective_refs": ["objective-001"],
                    "generation_type": "lesson_content",
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_failed"


@pytest.mark.asyncio
async def test_unknown_content_generation_result_returns_not_found() -> None:
    async with await client() as http:
        response = await http.get("/api/v1/content-generation/results/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "content_generation_not_found"
