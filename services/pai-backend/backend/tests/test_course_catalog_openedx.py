from datetime import UTC, datetime

import httpx
import pytest

from app.course_catalog.openedx import (
    OpenEdxCourseProvider,
    OpenEdxProviderError,
    to_normalized_candidate,
)
from app.course_catalog.schemas import CourseAvailability, CourseSourceType

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _course(**overrides: object) -> dict[str, object]:
    course: dict[str, object] = {
        "course_id": "course-v1:demo+101+2026",
        "name": "Open edX Fundamentals",
        "overview": "<p>Learn <strong>course operations</strong>.</p>",
        "effort": "6 weeks",
        "pacing": "self_paced",
        "marketing_url": "https://openedx.example.invalid/courses/demo-101",
        "start": "2026-09-01T00:00:00Z",
        "end": "2026-12-31T00:00:00Z",
        "enrollment_start": "2026-08-01T00:00:00Z",
        "enrollment_end": "2026-11-30T00:00:00Z",
        "hidden": False,
    }
    course.update(overrides)
    return course


@pytest.mark.asyncio
async def test_list_courses_maps_openedx_records_and_bounds_pagination() -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path.endswith("/courses/") and request.url.params.get("page") is None:
            return httpx.Response(
                200,
                json={
                    "results": [_course()],
                    "pagination": {
                        "next": "https://openedx.example.invalid/api/courses/v1/courses/?page=2"
                    },
                },
                request=request,
            )
        return httpx.Response(
            200,
            json={"results": [_course(course_id="course-v1:demo+102+2026", name="Second Course")]},
            request=request,
        )

    async with _client(handler) as client:
        provider = OpenEdxCourseProvider(
            base_url="https://openedx.example.invalid",
            client=client,
            max_pages=2,
            page_size=1,
            now=NOW,
        )
        courses = await provider.list_courses(limit=2)

    assert [course.provider_course_id for course in courses] == [
        "course-v1:demo+101+2026",
        "course-v1:demo+102+2026",
    ]
    assert len(requests) == 2
    assert "page=2" in requests[1]
    assert courses[0].provider_ref == "openedx"
    assert courses[0].course_url == "https://openedx.example.invalid/courses/demo-101"


@pytest.mark.asyncio
async def test_get_course_maps_detail_and_keeps_effort_out_of_duration() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_course(), request=request)

    async with _client(handler) as client:
        provider = OpenEdxCourseProvider(
            base_url="https://openedx.example.invalid",
            client=client,
            now=NOW,
        )
        course = await provider.get_course("course-v1:demo+101+2026")

    assert course.title == "Open edX Fundamentals"
    assert course.description == "<p>Learn <strong>course operations</strong>.</p>"
    assert course.duration_minutes is None
    assert course.delivery_mode == "self_paced"
    assert course.availability is CourseAvailability.AVAILABLE
    assert course.provenance[0].kind == "provider_metadata"
    assert course.provenance[0].source_locator == "/api/courses/v1/courses/{course_key}/"


@pytest.mark.asyncio
async def test_minimal_course_uses_safe_nullable_defaults() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"course_id": "minimal", "name": "Minimal Course"}, request=request
        )

    async with _client(handler) as client:
        provider = OpenEdxCourseProvider(
            base_url="https://openedx.example.invalid",
            client=client,
            now=NOW,
        )
        course = await provider.get_course("minimal")

    assert course.description is None
    assert course.duration_minutes is None
    assert course.delivery_mode is None
    assert course.language is None
    assert course.availability is CourseAvailability.UNKNOWN
    assert course.course_url is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("overview", None, "Short description"),
        ("overview", "", "Short description"),
        ("effort", "8 hours", None),
        ("start", "2026-12-01T00:00:00Z", CourseAvailability.UNKNOWN),
        ("end", "2026-01-01T00:00:00Z", CourseAvailability.UNAVAILABLE),
        ("hidden", True, CourseAvailability.UNAVAILABLE),
    ],
)
async def test_field_fallbacks_and_conservative_availability(
    field: str, value: object, expected: object
) -> None:
    payload = _course(**{field: value})
    payload["short_description"] = "Short description"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    async with _client(handler) as client:
        provider = OpenEdxCourseProvider(
            base_url="https://openedx.example.invalid",
            client=client,
            now=NOW,
        )
        course = await provider.get_course("course-v1:demo+101+2026")

    if field in {"overview", "effort"}:
        assert (
            course.description == expected
            if field == "overview"
            else course.duration_minutes == expected
        )
    else:
        assert course.availability is expected


def test_external_course_normalizes_without_fabricating_capabilities_or_level() -> None:
    course = OpenEdxCourseProvider.course_from_payload(
        _course(),
        endpoint="GET /api/courses/v1/courses/{course_key}/",
        now=NOW,
    )

    candidate = to_normalized_candidate(course)

    assert candidate.course_ref == "openedx:course-v1:demo+101+2026"
    assert candidate.source_type is CourseSourceType.EXTERNAL
    assert candidate.capabilities == []
    assert candidate.target_level is None
    assert candidate.prerequisites == []
    assert candidate.duration_minutes is None
    assert candidate.provenance == course.provenance


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 502, 503])
async def test_http_statuses_are_safe_provider_errors(status: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="provider error", request=request)

    async with _client(handler) as client:
        provider = OpenEdxCourseProvider(
            base_url="https://openedx.example.invalid",
            client=client,
        )
        with pytest.raises(OpenEdxProviderError, match=f"HTTP {status}") as error:
            await provider.get_course("course-v1:demo+101+2026")

    assert "provider error" not in str(error.value)


@pytest.mark.asyncio
async def test_invalid_json_is_rejected_without_persisting_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json-secret-like-body", request=request)

    async with _client(handler) as client:
        provider = OpenEdxCourseProvider(
            base_url="https://openedx.example.invalid",
            client=client,
        )
        with pytest.raises(OpenEdxProviderError, match="invalid JSON") as error:
            await provider.get_course("course-v1:demo+101+2026")

    assert "not-json-secret-like-body" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"results": "not-a-list"},
        {"results": ["not-a-course"]},
        {"course_id": "missing-title"},
        {"name": "missing-id"},
        {"course_id": "bad-overview", "name": "Bad", "overview": {"unsafe": True}},
    ],
)
async def test_malformed_provider_shapes_are_rejected(payload: dict[str, object]) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    async with _client(handler) as client:
        provider = OpenEdxCourseProvider(
            base_url="https://openedx.example.invalid",
            client=client,
        )
        with pytest.raises(OpenEdxProviderError):
            if "results" in payload:
                await provider.list_courses()
            else:
                await provider.get_course("course-v1:demo+101+2026")


@pytest.mark.asyncio
async def test_timeout_and_connection_errors_are_bounded_and_safe() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with _client(handler) as client:
        provider = OpenEdxCourseProvider(
            base_url="https://openedx.example.invalid",
            client=client,
            timeout_seconds=0.2,
        )
        with pytest.raises(OpenEdxProviderError, match="request failed"):
            await provider.get_course("course-v1:demo+101+2026")


@pytest.mark.asyncio
async def test_auth_header_is_optional_and_never_in_error() -> None:
    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(200, json=_course(), request=request)

    async with _client(handler) as client:
        provider = OpenEdxCourseProvider(
            base_url="https://openedx.example.invalid",
            access_token="test-token",
            client=client,
        )
        await provider.get_course("course-v1:demo+101+2026")

    assert seen["authorization"] == "Bearer test-token"
