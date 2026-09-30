import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.integration.repository import InMemoryIntegrationRepository
from app.integration.schemas import (
    CompetencyResultReference,
    CourseBlueprintV1,
)
from app.integration.service import IntegrationService
from app.main import create_app
from app.shared.config import Settings

API_KEY = "integration-test-key"


def app_with_integration() -> tuple[FastAPI, IntegrationService]:
    app = create_app(
        Settings(
            app_env="development",
            integration_api_key=SecretStr(API_KEY),
        )
    )
    service = IntegrationService(InMemoryIntegrationRepository())
    service.register_blueprint(
        CourseBlueprintV1(
            blueprint_id="bp-001",
            version="1",
            title="Python foundations",
            summary="A safe course projection.",
            estimated_duration_minutes=45,
            objectives=[
                {"objective_ref": "obj-1", "title": "Transform data", "sequence": 1}
            ],
            modules=[
                {
                    "module_ref": "mod-1",
                    "title": "Cleaning",
                    "order": 1,
                    "lessons": [
                        {
                            "lesson_ref": "lesson-1",
                            "title": "Invalid values",
                            "order": 1,
                            "delivery_type": "TEXT",
                            "objective_refs": ["obj-1"],
                        }
                    ],
                }
            ],
            assessment_references=[{"assessment_id": "assessment-1", "version": "1"}],
        )
    )
    service.register_competency_result(
        "eval-001",
        CompetencyResultReference(status="PENDING", evaluation_reference="eval-001"),
    )
    app.state.integration_service = service
    return app, service


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"}


@pytest.mark.asyncio
async def test_integration_requires_valid_bearer_api_key() -> None:
    app, _ = app_with_integration()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        missing = await client.get("/api/v1/integration/course-blueprints/bp-001")
        invalid = await client.get(
            "/api/v1/integration/course-blueprints/bp-001",
            headers={"Authorization": "Bearer wrong"},
        )

    assert missing.status_code == 401
    assert invalid.status_code == 401


@pytest.mark.asyncio
async def test_blueprint_uses_v1_envelope_and_safe_projection() -> None:
    app, _ = app_with_integration()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/integration/course-blueprints/bp-001", headers=auth()
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "v1"
    assert payload["data"]["blueprint_id"] == "bp-001"
    assert "evidence" not in payload
    assert "provenance" not in payload
    assert "prompt" not in payload
    assert "internal_policy" not in payload


@pytest.mark.asyncio
async def test_learning_result_accepts_completed_and_is_idempotent() -> None:
    app, _ = app_with_integration()
    body = {
        "submission_id": "submission-001",
        "learner_reference": {"external_user_id": "learner-1", "source_system": "LMS"},
        "course_reference": {"course_id": "course-1"},
        "activity_reference": {
            "activity_id": "lesson-1",
            "activity_type": "LESSON_COMPLETION",
        },
        "completion_status": "COMPLETED",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        first = await client.post(
            "/api/v1/integration/learning-results",
            headers=auth(),
            json={"schema_version": "v1", "data": body},
        )
        second = await client.post(
            "/api/v1/integration/learning-results",
            headers=auth(),
            json={"schema_version": "v1", "data": body},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["schema_version"] == "v1"
    assert first.json()["data"]["status"] == "ACCEPTED"
    assert first.json()["data"]["evaluation_reference"] == second.json()["data"]["evaluation_reference"]


@pytest.mark.asyncio
async def test_learning_result_requires_submission_id_and_completed_status() -> None:
    app, _ = app_with_integration()
    body = {
        "learner_reference": {"external_user_id": "learner-1", "source_system": "LMS"},
        "course_reference": {"course_id": "course-1"},
        "activity_reference": {"activity_id": "lesson-1", "activity_type": "LESSON_COMPLETION"},
        "completion_status": "IN_PROGRESS",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/integration/learning-results",
            headers=auth(),
            json={"schema_version": "v1", "data": body},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_learning_result_accepts_optional_assessment_summary() -> None:
    app, _ = app_with_integration()
    body = {
        "submission_id": "submission-summary-001",
        "learner_reference": {"external_user_id": "learner-1", "source_system": "LMS"},
        "course_reference": {"course_id": "course-1"},
        "activity_reference": {
            "activity_id": "assessment-1",
            "activity_type": "ASSESSMENT_COMPLETION",
        },
        "completion_status": "COMPLETED",
        "assessment_summary": {"score": 0.92},
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/integration/learning-results",
            headers=auth(),
            json={"schema_version": "v1", "data": body},
        )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ACCEPTED"
    assert "assessment_summary" not in response.text


@pytest.mark.asyncio
async def test_competency_result_returns_reference_only() -> None:
    app, _ = app_with_integration()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/integration/competency-results/eval-001", headers=auth()
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "schema_version": "v1",
        "data": {"status": "PENDING", "evaluation_reference": "eval-001"},
    }
    assert "evidence" not in response.text
    assert "provenance" not in response.text
    assert "raw_document" not in response.text
    assert "policy" not in response.text


@pytest.mark.asyncio
async def test_learning_result_evaluation_reference_can_be_polled_safely() -> None:
    app, _ = app_with_integration()
    body = {
        "submission_id": "submission-poll-001",
        "learner_reference": {"external_user_id": "learner-1", "source_system": "LMS"},
        "course_reference": {"course_id": "course-1"},
        "activity_reference": {
            "activity_id": "lesson-1",
            "activity_type": "LESSON_COMPLETION",
        },
        "completion_status": "COMPLETED",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        accepted = await client.post(
            "/api/v1/integration/learning-results",
            headers=auth(),
            json={"schema_version": "v1", "data": body},
        )
        evaluation_reference = accepted.json()["data"]["evaluation_reference"]
        polled = await client.get(
            f"/api/v1/integration/competency-results/{evaluation_reference}", headers=auth()
        )

    assert polled.status_code == 200
    assert polled.json()["data"] == {
        "status": "PENDING",
        "evaluation_reference": evaluation_reference,
    }


@pytest.mark.asyncio
async def test_development_app_exposes_python_blueprint_fixture() -> None:
    app = create_app(
        Settings(
            app_env="development",
            integration_api_key=SecretStr(API_KEY),
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/integration/course-blueprints/bp-python-001", headers=auth()
        )

    assert response.status_code == 200
    assert response.json()["schema_version"] == "v1"
    assert response.json()["data"]["blueprint_id"] == "bp-python-001"
    assert response.json()["data"]["objectives"][0]["objective_ref"] == "obj-001"
