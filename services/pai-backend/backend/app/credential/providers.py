from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class CourseCompletionAssertionProvider(Protocol):
    async def get(self, source_reference_id: str) -> object | None: ...


class UnavailableCompletionAssertionProvider:
    async def get(self, source_reference_id: str) -> object | None:
        return None


@dataclass(frozen=True)
class CompletionAssertion:
    learner_id: UUID
    organization_id: UUID
    course_id: str
    course_version: str
    completed: bool
    source_system: str
    source_record_id: str


class FakeCompletionAssertionProvider:
    def __init__(self, assertions: dict[str, CompletionAssertion]) -> None:
        self._assertions = assertions

    async def get(self, source_reference_id: str) -> CompletionAssertion | None:
        return self._assertions.get(source_reference_id)


class LearningOutcomeAssertionProvider(Protocol):
    async def get(self, source_reference_id: str) -> object | None: ...


class UnavailableLearningOutcomeAssertionProvider:
    async def get(self, source_reference_id: str) -> object | None:
        return None


@dataclass(frozen=True)
class LearningOutcomeAssertion:
    learner_id: UUID
    organization_id: UUID
    learning_outcome_id: str
    course_version: str
    assessment_id: str
    rubric_version: str
    passed: bool


class FakeLearningOutcomeAssertionProvider:
    def __init__(self, assertions: dict[str, LearningOutcomeAssertion]) -> None:
        self._assertions = assertions

    async def get(self, source_reference_id: str) -> LearningOutcomeAssertion | None:
        return self._assertions.get(source_reference_id)
