from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from test_course_authoring_api import app_for_api, request_body

from app.course_authoring.schemas import AudienceSnapshot, AudienceSnapshotSource
from app.integration.actor_context import SIGNATURE_HEADER


def test_audience_snapshot_rejects_a_count_that_does_not_match_ordered_refs() -> None:
    with pytest.raises(ValidationError):
        AudienceSnapshot(
            id="audience-001",
            learner_refs=("learner-3", "learner-1", "learner-2"),
            learner_count=2,
            captured_at=datetime(2026, 8, 24, tzinfo=UTC),
            source=AudienceSnapshotSource.MANUAL_SELECTION,
        )


@pytest.mark.asyncio
async def test_course_authoring_rejects_an_invalid_signed_actor_context() -> None:
    app, headers, _private_key = app_for_api()
    headers[SIGNATURE_HEADER] = "ed25519:invalid-signature"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as http:
        response = await http.post(
            "/api/v1/course-authoring/requests",
            headers=headers,
            json=request_body(),
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ACTOR_CONTEXT_INVALID"


def test_audience_snapshot_keeps_the_original_order_and_is_frozen() -> None:
    snapshot = AudienceSnapshot(
        id="audience-001",
        learner_refs=("learner-3", "learner-1", "learner-2"),
        learner_count=3,
        captured_at=datetime(2026, 8, 24, tzinfo=UTC),
        source=AudienceSnapshotSource.MANUAL_SELECTION,
    )

    assert snapshot.learner_refs == ("learner-3", "learner-1", "learner-2")
    assert snapshot.learner_count == len(snapshot.learner_refs)
    with pytest.raises(ValidationError):
        snapshot.learner_refs = ("learner-1",)  # type: ignore[misc]
