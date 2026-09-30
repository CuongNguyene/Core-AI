from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from test_course_authoring_api import ACTOR_ID, ORG_ID, app_for_api
from test_course_authoring_revision import AuthoringReader, stored_result

from app.content_generation.repository import InMemoryContentGenerationRepository
from app.course_authoring.revision_service import CourseDraftRevisionService
from app.integration.actor_context import actor_context_headers


def revision_body() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "data": {
            "source_result_ref": "content-generation-result-001",
            "change_summary": "Clarified the lesson introduction.",
            "section_changes": [{
                "module_order": 1,
                "lesson_order": 1,
                "section_order": 1,
                "content": "Learners examine invalid values before analysis.",
            }],
        },
    }


@pytest.mark.asyncio
async def test_revision_api_forwards_actor_and_returns_new_version() -> None:
    app, headers, private_key = app_for_api()
    repository = InMemoryContentGenerationRepository()
    await repository.create_result(stored_result())
    app.state.content_generation_repository = repository
    app.state.course_draft_revision_service = CourseDraftRevisionService(
        repository=repository,
        authoring=AuthoringReader(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        response = await http.post(
            "/api/v1/course-authoring/results/content-generation-result-001/revisions",
            headers=headers,
            json=revision_body(),
        )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["request_ref"] == "course-authoring-request-001"
    assert data["version"] == 2
    assert data["supersedes_result_ref"] == "content-generation-result-001"
    assert data["revision_metadata"]["editor_actor_ref"] == str(ACTOR_ID)


@pytest.mark.asyncio
async def test_revision_api_lists_versions_and_marks_latest_ready() -> None:
    app, headers, private_key = app_for_api()
    repository = InMemoryContentGenerationRepository()
    await repository.create_result(stored_result())
    app.state.content_generation_repository = repository
    app.state.course_draft_revision_service = CourseDraftRevisionService(
        repository=repository,
        authoring=AuthoringReader(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        revised = await http.post(
            "/api/v1/course-authoring/results/content-generation-result-001/revisions",
            headers=headers,
            json=revision_body(),
        )
        result_id = revised.json()["data"]["id"]
        list_headers = {
            **headers,
            **actor_context_headers(
                private_key=private_key,
                key_id="lms-key-1",
                actor_id=ACTOR_ID,
                organization_id=ORG_ID,
                issued_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
                expires_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC) + timedelta(seconds=30),
                nonce="course-revision-list-test",
            ),
        }
        versions = await http.get(
            "/api/v1/course-authoring/requests/course-authoring-request-001/results",
            headers=list_headers,
        )
        ready_headers = {
            **headers,
            **actor_context_headers(
                private_key=private_key,
                key_id="lms-key-1",
                actor_id=ACTOR_ID,
                organization_id=ORG_ID,
                issued_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
                expires_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC) + timedelta(seconds=30),
                nonce="course-revision-ready-test",
            ),
        }
        ready = await http.post(
            f"/api/v1/course-authoring/results/{result_id}/ready-for-materialization",
            headers=ready_headers,
        )

    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()["data"]] == [2, 1]
    assert versions.json()["data"][0]["revision_metadata"]["change_summary"] == "Clarified the lesson introduction."
    assert ready.status_code == 200
    assert ready.json()["data"]["status"] == "READY_FOR_MATERIALIZATION"
