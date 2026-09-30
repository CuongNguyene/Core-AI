from datetime import UTC, datetime, timedelta

import pytest
from test_course_authoring_api import ACTOR_ID, ORG_ID, app_for_api
from test_course_generation import ReferenceReader
from test_hierarchical_generation import FakeLessonGenerator, GoalAuthoring

from app.content_generation.repository import InMemoryContentGenerationRepository
from app.course_authoring.errors import CourseAuthoringRequestNotFoundError
from app.course_generation.context import CourseGenerationContextBuilder
from app.course_generation.errors import CourseGenerationOutputInvalidError
from app.course_generation.hierarchical_service import HierarchicalCourseGenerationService
from app.course_generation.schemas import CourseGenerationAccepted
from app.integration.actor_context import actor_context_headers


@pytest.mark.asyncio
async def test_generate_course_authoring_request_serializes_stable_projection_and_actor() -> None:
    app, headers, _private_key = app_for_api()
    calls: list[tuple[str, object]] = []

    class GenerationService:
        async def generate(self, request_id: str, actor: object) -> CourseGenerationAccepted:
            calls.append((request_id, actor))
            return CourseGenerationAccepted(
                request_ref=request_id,
                generation_run_ref='generation-run-001',
                result_ref='content-generation-result-001',
                status='DRAFT',
                version=1,
            )

    app.state.course_generation_service = GenerationService()
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as http:
        response = await http.post(
            '/api/v1/course-authoring/requests/course-authoring-request-001/generate',
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()['data'] == {
        'request_ref': 'course-authoring-request-001',
        'generation_run_ref': 'generation-run-001',
        'result_ref': 'content-generation-result-001',
        'status': 'DRAFT',
        'version': 1,
    }
    assert calls[0][0] == 'course-authoring-request-001'


@pytest.mark.asyncio
async def test_generate_course_authoring_request_maps_failures() -> None:
    app, headers, _private_key = app_for_api()

    class FailedGenerationService:
        async def generate(self, _request_id: str, _actor: object) -> CourseGenerationAccepted:
            raise CourseGenerationOutputInvalidError('malformed_structured_output')

    app.state.course_generation_service = FailedGenerationService()
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as http:
        response = await http.post(
            '/api/v1/course-authoring/requests/course-authoring-request-001/generate',
            headers=headers,
        )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'course_generation_output_invalid'


@pytest.mark.asyncio
async def test_generate_course_authoring_request_maps_unknown_request() -> None:
    app, headers, _private_key = app_for_api()

    class MissingGenerationService:
        async def generate(self, _request_id: str, _actor: object) -> CourseGenerationAccepted:
            raise CourseAuthoringRequestNotFoundError('missing')

    app.state.course_generation_service = MissingGenerationService()
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as http:
        response = await http.post(
            '/api/v1/course-authoring/requests/missing/generate',
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'course_authoring_request_not_found'


@pytest.mark.asyncio
async def test_hierarchical_generation_api_returns_progress_and_lesson_details() -> None:
    app, headers, _private_key = app_for_api()
    service = HierarchicalCourseGenerationService(
        authoring=GoalAuthoring(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=FakeLessonGenerator(delay=0.001),
        repository=InMemoryContentGenerationRepository(),
        provider='fake-provider',
        model='fake-model',
        max_concurrency=2,
        generation_timeout_seconds=2,
    )
    app.state.course_generation_service = service
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as http:
        response = await http.post(
            '/api/v1/course-authoring/requests/course-authoring-request-001/generate',
            headers=headers,
        )
        assert response.status_code == 200
        plan_ref = response.json()['data']['plan_ref']
        await service.wait_for_plan(plan_ref)
        progress_headers = {
            **headers,
            **actor_context_headers(
                private_key=_private_key,
                key_id='lms-key-1',
                actor_id=ACTOR_ID,
                organization_id=ORG_ID,
                issued_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
                expires_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC) + timedelta(seconds=30),
                nonce='course-generation-api-progress-test',
            ),
        }
        progress = await http.get(
            '/api/v1/course-authoring/requests/course-authoring-request-001/generation',
            headers=progress_headers,
        )

    assert progress.status_code == 200
    assert progress.json()['data']['total_lessons'] == 2
    assert len(progress.json()['data']['lessons']) == 2
    assert progress.json()['data']['status'] == 'COMPLETED'
