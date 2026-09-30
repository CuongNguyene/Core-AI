import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from app.content_generation.schemas import ContentSectionType, GeneratedCourseSection


@dataclass(frozen=True)
class SectionDepthMetrics:
    """Raw, effective, and validator-facing depth for one generated section."""

    content_words: int
    steps_words: int
    success_criteria_words: int
    effective_words: int
    validation_words: int


def measure_section_depth(section: GeneratedCourseSection) -> SectionDepthMetrics:
    content_words = normalized_word_count(section.content)
    steps_words = sum(normalized_word_count(value) for value in section.steps)
    success_criteria_words = sum(normalized_word_count(value) for value in section.success_criteria)
    effective_words = content_words + steps_words + success_criteria_words
    if section.type is ContentSectionType.GUIDED_PRACTICE:
        validation_words = content_words + steps_words
    elif section.type is ContentSectionType.INDEPENDENT_PRACTICE:
        validation_words = content_words + success_criteria_words
    else:
        validation_words = content_words
    return SectionDepthMetrics(
        content_words=content_words,
        steps_words=steps_words,
        success_criteria_words=success_criteria_words,
        effective_words=effective_words,
        validation_words=validation_words,
    )


class CourseContentQualityPolicy(BaseModel):
    """Centralized deterministic acceptance policy for generated lesson content."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    minimum_section_words: dict[ContentSectionType, int] = Field(
        default_factory=lambda: {
            ContentSectionType.INTRODUCTION: 60,
            ContentSectionType.CONCEPT: 180,
            ContentSectionType.EXAMPLE: 100,
            ContentSectionType.GUIDED_PRACTICE: 100,
            ContentSectionType.INDEPENDENT_PRACTICE: 80,
            ContentSectionType.SUMMARY: 60,
        }
    )
    default_max_lesson_words: int = Field(default=2500, ge=1)
    minimum_duration_max_lesson_words: int = Field(default=1200, ge=1)
    maximum_duration_max_lesson_words: int = Field(default=5000, ge=1)
    words_per_duration_minute: int = Field(default=20, ge=1)

    def maximum_lesson_words(self, duration_constraint: str | None) -> int:
        if not duration_constraint:
            return self.default_max_lesson_words
        match = re.search(r"\b(\d+)\s*(?:minutes?|mins?|phút)\b", duration_constraint.lower())
        if match is None:
            return self.default_max_lesson_words
        estimated = int(match.group(1)) * self.words_per_duration_minute
        return max(
            self.minimum_duration_max_lesson_words,
            min(self.maximum_duration_max_lesson_words, estimated),
        )


REQUIRED_SECTION_TYPES = frozenset(ContentSectionType)


def normalized_word_count(value: str) -> int:
    return len(value.split())
