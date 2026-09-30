from dataclasses import dataclass

from .duration import NormalizedTrainingDuration

DURATION_TOLERANCE_PERCENT = 20


@dataclass(frozen=True)
class CurriculumScopeBounds:
    minimum_modules: int
    maximum_modules: int
    minimum_lessons: int
    maximum_lessons: int


class CurriculumScopePolicy:
    """Centralized planning bounds; bounds guide validation, not exact output."""

    def bounds_for(
        self, duration: NormalizedTrainingDuration, *, strategy: str = "legacy"
    ) -> CurriculumScopeBounds:
        if strategy == "sep-08b-v1":
            return CurriculumScopeBounds(1, 8, 1, 100)
        hours = duration.estimated_total_learning_hours
        if hours is None:
            return CurriculumScopeBounds(1, 4, 2, 12)
        if hours <= 4:
            return CurriculumScopeBounds(1, 2, 2, 6)
        if hours <= 20:
            return CurriculumScopeBounds(2, 4, 6, 12)
        if hours <= 60:
            return CurriculumScopeBounds(3, 6, 10, 24)
        if hours <= 150:
            return CurriculumScopeBounds(5, 10, 18, 40)
        if hours <= 300:
            return CurriculumScopeBounds(8, 14, 30, 60)
        return CurriculumScopeBounds(10, 18, 40, 80)
