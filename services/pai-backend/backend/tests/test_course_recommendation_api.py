from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import test_course_rec_3d6_end_to_end as fixtures
import test_governed_target_adapter as target_fixtures
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.authorization.schemas import ActorContext, Role
from app.course_recommendation.engine import CourseRecommendationEngine
from app.course_recommendation.execution_service import CourseRecommendationExecutionService
from app.course_recommendation.repository import SqlAlchemyCourseRecommendationExecutionRepository
from app.integration.actor_context import SignedActorContextVerifier, actor_context_headers
from app.integration.course_recommendation_api import router
from app.shared.config import Settings
from app.shared.database import Base
from app.shared.errors import APIError, api_error_handler, request_validation_error_handler

API_KEY = "course-recommendation-test-key"
ACTOR_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ORG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _payload(*, include_course=True, request_key="api-key"):
    release = target_fixtures._active_release()
    target, _ = fixtures._target_projection((fixtures.CAPABILITY_COMMUNICATION,), release)
    courses = []
    if include_course:
        _, course, _, _ = fixtures._course_projection(
            course_ref="skillscommons:api-test",
            capability_refs=(fixtures.CAPABILITY_COMMUNICATION,),
            release=release,
        )
        courses.append(course)
    return {
        "schema_version": "v1",
        "data": {
            "request_key": request_key,
            "target_projection": target.model_dump(mode="json"),
            "course_projections": [item.model_dump(mode="json") for item in courses],
            "max_results": 5,
        },
    }


def _test_app(session_factory, *, roles=frozenset({Role.REVIEWER})):
    private_key = Ed25519PrivateKey.generate()
    now = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
    actor = ActorContext(
        actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        roles=roles,
        authentication_method="signed_actor_context",
    )
    app = FastAPI()
    app.state.settings = Settings(_env_file=None, integration_api_key=SecretStr(API_KEY))
    app.state.actor_context_verifier = SignedActorContextVerifier(
        public_keys={"test-key": private_key.public_key()},
        actor_resolver=lambda _actor, _org: actor,
        now=lambda: now,
    )
    repository = SqlAlchemyCourseRecommendationExecutionRepository(session_factory)
    app.state.course_recommendation_execution_service = CourseRecommendationExecutionService(
        repository=repository, engine=CourseRecommendationEngine()
    )
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.include_router(router)
    return app, private_key, now


def _headers(private_key, now, nonce):
    return {
        "Authorization": f"Bearer {API_KEY}",
        **actor_context_headers(
            private_key=private_key,
            key_id="test-key",
            actor_id=ACTOR_ID,
            organization_id=ORG_ID,
            issued_at=now,
            expires_at=now + timedelta(seconds=30),
            nonce=nonce,
        ),
    }


@pytest.mark.asyncio
async def test_authenticated_post_and_historical_get_round_trip(session_factory) -> None:
    app, private_key, now = _test_app(session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        created = await http.post(
            "/api/v1/course-recommendations",
            headers=_headers(private_key, now, "create-api"),
            json=_payload(),
        )
        assert created.status_code == 201, created.text
        recommendation_id = created.json()["data"]["id"]
        read = await http.get(
            f"/api/v1/course-recommendations/{recommendation_id}",
            headers=_headers(private_key, now, "read-api"),
        )

    assert created.status_code == 201
    assert created.json()["schema_version"] == "v1"
    assert read.status_code == 200
    assert read.json()["data"] == created.json()["data"]
    assert created.json()["data"]["algorithm_id"] == "deterministic_course_recommendation"


@pytest.mark.asyncio
async def test_same_request_key_replays_and_changed_request_conflicts(session_factory) -> None:
    app, private_key, now = _test_app(session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        first = await http.post(
            "/api/v1/course-recommendations",
            headers=_headers(private_key, now, "replay-1"),
            json=_payload(),
        )
        replay = await http.post(
            "/api/v1/course-recommendations",
            headers=_headers(private_key, now, "replay-2"),
            json=_payload(),
        )
        conflict = await http.post(
            "/api/v1/course-recommendations",
            headers=_headers(private_key, now, "replay-3"),
            json=_payload(include_course=False),
        )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "recommendation_idempotency_conflict"


@pytest.mark.asyncio
async def test_auth_validation_and_not_found_errors_are_stable(session_factory) -> None:
    app, private_key, now = _test_app(session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        unauthenticated = await http.post("/api/v1/course-recommendations", json=_payload())
        invalid = await http.post(
            "/api/v1/course-recommendations",
            headers=_headers(private_key, now, "invalid-api"),
            json={"schema_version": "v1", "data": {"request_key": "bad"}},
        )
        missing = await http.get(
            "/api/v1/course-recommendations/crx_missing",
            headers=_headers(private_key, now, "missing-api"),
        )

    assert unauthenticated.status_code == 401
    assert invalid.status_code == 422
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "recommendation_not_found"
