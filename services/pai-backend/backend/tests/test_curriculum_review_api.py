from types import SimpleNamespace
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from test_course_authoring_api import ACTOR_ID, ORG_ID, app_for_api
from test_curriculum_conversation_adapter import service as revision_service_fixture
from app.integration.actor_context import actor_context_headers


class ParentRequestService:
    async def get(self, request_id, _actor):
        return SimpleNamespace(id=request_id)


async def review_client():
    app, headers, private_key = app_for_api()
    revision_service, repository = await revision_service_fixture()
    app.state.course_authoring_service = ParentRequestService()
    app.state.curriculum_revision_service = revision_service
    return app, headers, private_key, repository


def fresh_headers(base_headers, private_key, nonce):
    return {
        **base_headers,
        **actor_context_headers(
            private_key=private_key,
            key_id="lms-key-1",
            actor_id=ACTOR_ID,
            organization_id=ORG_ID,
            issued_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
            expires_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC) + timedelta(seconds=30),
            nonce=nonce,
        ),
    }


@pytest.mark.asyncio
async def test_curriculum_plan_can_be_listed_and_loaded_by_plan_ref() -> None:
    app, headers, private_key, _repository = await review_client()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        listed = await http.get(
            "/api/v1/course-authoring/requests/request-1/curriculum-plans",
            headers=fresh_headers(headers, private_key, "curriculum-list-test"),
        )
        loaded = await http.get(
            "/api/v1/course-authoring/curriculum-plans/curriculum-plan:v1",
            headers=fresh_headers(headers, private_key, "curriculum-get-test"),
        )

    assert listed.status_code == 200
    assert listed.json()["schema_version"] == "v1"
    assert listed.json()["data"][0]["plan_ref"] == "curriculum-plan:v1"
    assert loaded.status_code == 200
    assert loaded.json()["data"]["plan_ref"] == "curriculum-plan:v1"


@pytest.mark.asyncio
async def test_curriculum_feedback_preview_does_not_persist_a_plan() -> None:
    app, headers, _private_key, repository = await review_client()
    body = {
        "feedback": {
            "kind": "ADJUST_EFFORT",
            "target_ref": "lesson-2",
            "estimated_minutes": 45,
        }
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        response = await http.post(
            "/api/v1/course-authoring/curriculum-plans/curriculum-plan:v1/feedback/preview",
            headers=headers,
            json=body,
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["operations"] == [{
        "op": "UPDATE_UNIT_EFFORT",
        "target_ref": "lesson-2",
        "fields": {"estimated_minutes": 45},
        "rationale": None,
    }]
    assert data["before"] == {"estimated_minutes": 30}
    assert data["after"] == {"estimated_minutes": 45}
    assert len(await repository.list_curriculum_plans("request-1")) == 1


@pytest.mark.asyncio
async def test_curriculum_feedback_creates_reviewable_immutable_revision() -> None:
    app, headers, private_key, repository = await review_client()
    body = {
        "feedback": {
            "kind": "ADJUST_EFFORT",
            "target_ref": "lesson-2",
            "estimated_minutes": 45,
        },
        "rationale": "Increase practice time",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        revised = await http.post(
            "/api/v1/course-authoring/curriculum-plans/curriculum-plan:v1/feedback",
            headers=fresh_headers(headers, private_key, "curriculum-feedback-revise"),
            json=body,
        )
        plan_ref = revised.json()["data"]["plan_ref"]
        reviewed = await http.post(
            f"/api/v1/course-authoring/curriculum-plans/{plan_ref}/review",
            headers=fresh_headers(headers, private_key, "curriculum-feedback-review"),
        )
        confirmed = await http.post(
            f"/api/v1/course-authoring/curriculum-plans/{plan_ref}/confirm",
            headers=fresh_headers(headers, private_key, "curriculum-feedback-confirm"),
        )

    assert revised.status_code == 201
    assert revised.json()["data"]["version"] == 2
    assert revised.json()["data"]["supersedes_plan_ref"] == "curriculum-plan:v1"
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["status"] == "READY_FOR_CONFIRMATION"
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "CONFIRMED"
    old = await repository.get_curriculum_plan("curriculum-plan:v1")
    assert old is not None
    assert old.version == 1
    assert old.modules[0].lessons[1].estimated_minutes == 30


@pytest.mark.asyncio
async def test_unsupported_curriculum_feedback_is_rejected_safely() -> None:
    app, headers, _private_key, _repository = await review_client()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        response = await http.post(
            "/api/v1/course-authoring/curriculum-plans/curriculum-plan:v1/feedback/preview",
            headers=headers,
            json={"feedback": {"kind": "REMOVE_UNIT", "target_ref": "lesson-2"}},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "curriculum_revision_operation_not_supported"
