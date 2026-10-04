"""Provider abstractions for deterministic course catalog fixtures."""

from app.course_catalog.fixtures import external_course_catalog
from app.course_catalog.schemas import ExternalCourse


class MockExternalProvider:
    """Pure in-memory provider used by COURSE-REC-01A and later tests."""

    provider_ref = "mock_provider"

    def __init__(self) -> None:
        self.network_calls = 0
        self.model_calls = 0

    def list_courses(self) -> tuple[ExternalCourse, ...]:
        return external_course_catalog()

    def get_course(self, provider_course_id: str) -> ExternalCourse:
        for course in self.list_courses():
            if course.provider_course_id == provider_course_id:
                return course
        raise KeyError(provider_course_id)
