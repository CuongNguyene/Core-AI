from datetime import UTC, datetime, timedelta

import pytest
from test_course_authoring_api import ACTOR_ID, ORG_ID, app_for_api
from test_course_generation import ReferenceReader, authoring_request
from test_curriculum_planning import small_plan
from test_hierarchical_generation import GoalAuthoring

from app.content_generation.repository import InMemoryContentGenerationRepository
from app.course_authoring.schemas import CourseAuthoringMode
from app.course_generation.context import CourseGenerationContextBuilder
from app.curriculum_planning.planner import (
    CurriculumPlanningCandidateValidationError,
    DeterministicCurriculumPlanner,
)
from app.curriculum_planning.policy import CurriculumScopePolicy
from app.curriculum_planning.service import CurriculumPlanningService
from app.curriculum_planning.validation import collect_curriculum_plan_validation
from app.integration.actor_context import actor_context_headers


@pytest.mark.asyncio
async def test_curriculum_plan_api_serializes_plan_and_round_trips_latest_plan() -> None:
    app, headers, private_key = app_for_api()
    await app.state.course_authoring_service._repository.create(
        authoring_request(CourseAuthoringMode.GOAL_DRIVEN).model_copy(
            update={"created_by_actor_ref": ACTOR_ID}
        )
    )
    repository = InMemoryContentGenerationRepository()
    app.state.curriculum_planning_service = CurriculumPlanningService(
        authoring=GoalAuthoring(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        planner=DeterministicCurriculumPlanner(),
        repository=repository,
    )
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        created = await http.post(
            "/api/v1/course-authoring/requests/course-authoring-request-001/plan",
            headers=headers,
        )
        get_headers = {
            **headers,
            **actor_context_headers(
                private_key=private_key,
                key_id="lms-key-1",
                actor_id=ACTOR_ID,
                organization_id=ORG_ID,
                issued_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
                expires_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC) + timedelta(seconds=30),
                nonce="curriculum-plan-api-get-test",
            ),
        }
        restored = await http.get(
            "/api/v1/course-authoring/requests/course-authoring-request-001/plan",
            headers=get_headers,
        )

    assert created.status_code == 201
    assert restored.status_code == 200
    data = created.json()["data"]
    assert data["plan_ref"].startswith("curriculum-plan:")
    assert data["objective_count"] == 4
    assert data["module_count"] == 1
    assert data["lesson_count"] == 2
    assert restored.json()["data"]["plan_ref"] == data["plan_ref"]


@pytest.mark.asyncio
async def test_invalid_plan_error_does_not_expose_candidate_body_or_credentials() -> None:
    app, headers, _private_key = app_for_api()
    await app.state.course_authoring_service._repository.create(
        authoring_request(CourseAuthoringMode.GOAL_DRIVEN).model_copy(
            update={"created_by_actor_ref": ACTOR_ID}
        )
    )
    repository = InMemoryContentGenerationRepository()
    candidate = small_plan(lessons=6, modules=3)
    report = collect_curriculum_plan_validation(candidate, policy=CurriculumScopePolicy())

    class FailedPlanner:
        async def plan(self, _context: object) -> object:
            raise CurriculumPlanningCandidateValidationError(
                candidate_plan=candidate,
                report=report,
                audit=type(
                    "Audit",
                    (),
                    {
                        "provider": "gemini",
                        "model": "gemini-test",
                        "prompt_template_id": "curriculum_planning",
                        "prompt_template_version": "sep-02.3-v1",
                        "correlation_id": "diagnostic-correlation-001",
                    },
                )(),
            )

    app.state.curriculum_planning_service = CurriculumPlanningService(
        authoring=GoalAuthoring(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        planner=FailedPlanner(),
        repository=repository,
    )
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        response = await http.post(
            "/api/v1/course-authoring/requests/course-authoring-request-001/plan",
            headers=headers,
        )

    body = response.text
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "curriculum_plan_invalid"
    assert response.json()["error"]["details"]["issues"][0]["code"]
    assert "actual" in response.json()["error"]["details"]["issues"][0]
    assert "expected" in response.json()["error"]["details"]["issues"][0]
    assert "Authorization" not in body
    assert "gemini-test" not in body
    assert "Backend module" not in body
    attempts = await repository.list_curriculum_planning_attempts("course-authoring-request-001")
    assert len(attempts) == 1
