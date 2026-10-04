"""Bounded Open edX Courses API adapter for external course discovery.

This module only imports provider-owned catalog facts. It does not create
capability claims, call a model, or rank courses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.course_catalog.schemas import (
    CourseAvailability,
    CourseProvenance,
    CourseSourceType,
    ExternalCourse,
    NormalizedCourseCandidate,
)


class OpenEdxProviderError(RuntimeError):
    """Safe, bounded failure from an Open edX catalog request or payload."""


class OpenEdxCourseProvider:
    """Read a bounded page of Open edX catalog courses without retries."""

    provider_ref = "openedx"
    source_system = "openedx"
    list_endpoint = "/api/courses/v1/courses/"
    detail_endpoint = "/api/courses/v1/courses/{course_key}/"

    def __init__(
        self,
        base_url: str,
        access_token: str | None = None,
        timeout_seconds: float = 10.0,
        max_pages: int = 2,
        page_size: int = 50,
        client: httpx.AsyncClient | None = None,
        now: datetime | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        if page_size < 1:
            raise ValueError("page_size must be positive")
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._timeout_seconds = timeout_seconds
        self._max_pages = max_pages
        self._page_size = page_size
        self._client = client
        self._now = now or datetime.now(UTC)

    async def list_courses(self, limit: int = 50) -> tuple[ExternalCourse, ...]:
        """Read at most ``limit`` records and at most ``max_pages`` pages."""
        if limit < 1:
            raise ValueError("limit must be positive")

        next_url: str | None = f"{self._base_url}{self.list_endpoint}"
        params: dict[str, int] | None = {"page_size": min(self._page_size, limit)}
        courses: list[ExternalCourse] = []
        pages_read = 0
        while next_url and pages_read < self._max_pages and len(courses) < limit:
            payload = await self._get_json(next_url, params=params)
            params = None
            results = payload.get("results")
            if not isinstance(results, list):
                raise OpenEdxProviderError("Open edX list response has invalid results")
            for item in results:
                if not isinstance(item, dict):
                    raise OpenEdxProviderError("Open edX list response has malformed course")
                courses.append(
                    self.course_from_payload(
                        item,
                        endpoint=self.list_endpoint,
                        now=self._now,
                    )
                )
                if len(courses) >= limit:
                    break
            pages_read += 1
            next_url = self._next_url(payload)
        return tuple(courses[:limit])

    async def get_course(self, provider_course_id: str) -> ExternalCourse:
        if not provider_course_id.strip():
            raise ValueError("provider_course_id must not be empty")
        url = f"{self._base_url}{self.detail_endpoint.format(course_key=provider_course_id)}"
        payload = await self._get_json(url)
        return self.course_from_payload(payload, endpoint=self.detail_endpoint, now=self._now)

    async def _get_json(self, url: str, params: dict[str, int] | None = None) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        try:
            if self._client is not None:
                response = await self._client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise OpenEdxProviderError(
                f"Open edX returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise OpenEdxProviderError("Open edX request failed: timeout") from exc
        except httpx.TransportError as exc:
            raise OpenEdxProviderError("Open edX request failed: transport error") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenEdxProviderError("Open edX response contains invalid JSON") from exc
        if not isinstance(payload, dict):
            raise OpenEdxProviderError("Open edX response has invalid object shape")
        return payload

    @classmethod
    def course_from_payload(
        cls,
        payload: dict[str, Any],
        *,
        endpoint: str,
        now: datetime,
    ) -> ExternalCourse:
        provider_course_id = cls._string(payload, "course_id") or cls._string(payload, "id")
        title = cls._required_string(payload, "name")
        if provider_course_id is None:
            raise OpenEdxProviderError("Open edX course is missing course_id or id")

        overview = payload.get("overview")
        if overview is not None and not isinstance(overview, str):
            raise OpenEdxProviderError("Open edX course has malformed overview")
        short_description = payload.get("short_description")
        if short_description is not None and not isinstance(short_description, str):
            raise OpenEdxProviderError("Open edX course has malformed short_description")
        description = (
            (overview or short_description or None)
            if isinstance(overview, str)
            else short_description
        )

        pacing = payload.get("pacing")
        delivery_mode = pacing if pacing in {"self_paced", "instructor_paced"} else None
        course_url = cls._string(payload, "marketing_url") or cls._string(payload, "course_url")
        provenance = [
            CourseProvenance(
                kind="provider_metadata",
                source_ref=f"openedx:{provider_course_id}",
                source_field="course_id",
                source_locator=endpoint,
                method="openedx_courses_api",
            )
        ]
        return ExternalCourse(
            provider_ref=cls.provider_ref,
            provider_course_id=provider_course_id,
            title=title,
            description=description,
            duration_minutes=None,
            delivery_mode=delivery_mode,
            language=cls._string(payload, "language"),
            availability=cls._availability(payload, now),
            course_url=course_url,
            provenance=provenance,
        )

    @staticmethod
    def _next_url(payload: dict[str, Any]) -> str | None:
        pagination = payload.get("pagination")
        candidate = pagination.get("next") if isinstance(pagination, dict) else payload.get("next")
        return candidate if isinstance(candidate, str) and candidate else None

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise OpenEdxProviderError(f"Open edX course field {key} is malformed")
        return value.strip() or None

    @classmethod
    def _required_string(cls, payload: dict[str, Any], key: str) -> str:
        value = cls._string(payload, key)
        if value is None:
            raise OpenEdxProviderError(f"Open edX course is missing {key}")
        return value

    @classmethod
    def _availability(cls, payload: dict[str, Any], now: datetime) -> CourseAvailability:
        hidden = payload.get("hidden")
        if hidden is True:
            return CourseAvailability.UNAVAILABLE
        if hidden is not None and not isinstance(hidden, bool):
            raise OpenEdxProviderError("Open edX course field hidden is malformed")
        end = cls._parse_datetime(payload.get("end"))
        start = cls._parse_datetime(payload.get("start"))
        if end is not None and end <= now:
            return CourseAvailability.UNAVAILABLE
        if start is None or start > now:
            return CourseAvailability.UNKNOWN
        return CourseAvailability.AVAILABLE

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise OpenEdxProviderError("Open edX course date field is malformed")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def to_normalized_candidate(course: ExternalCourse) -> NormalizedCourseCandidate:
    """Expose provider facts without fabricating semantic capability claims."""
    return NormalizedCourseCandidate(
        course_ref=f"{course.provider_ref}:{course.provider_course_id}",
        source_type=CourseSourceType.EXTERNAL,
        source_system=course.provider_ref,
        provider_ref=course.provider_ref,
        provider_course_id=course.provider_course_id,
        title=course.title,
        description=course.description,
        capabilities=[],
        prerequisites=[],
        target_level=None,
        duration_minutes=course.duration_minutes,
        delivery_mode=course.delivery_mode,
        language=course.language,
        availability=course.availability,
        provenance=list(course.provenance),
    )
