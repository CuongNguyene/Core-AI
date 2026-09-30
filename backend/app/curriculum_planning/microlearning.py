import re
from dataclasses import dataclass

from .schemas import LessonWorkloadCategory

MICROLEARNING_POLICY_VERSION = "sep-08b-v1"
EFFORT_TOLERANCE_PERCENT = 20


@dataclass(frozen=True)
class MicrolearningEffortRange:
    minimum_minutes: int
    maximum_minutes: int


MICROLEARNING_EFFORT_RANGES: dict[LessonWorkloadCategory, MicrolearningEffortRange] = {
    LessonWorkloadCategory.FOUNDATION: MicrolearningEffortRange(15, 30),
    LessonWorkloadCategory.CONCEPT: MicrolearningEffortRange(20, 40),
    LessonWorkloadCategory.APPLIED: MicrolearningEffortRange(30, 60),
    LessonWorkloadCategory.PRACTICE: MicrolearningEffortRange(30, 60),
    LessonWorkloadCategory.INTEGRATION: MicrolearningEffortRange(45, 90),
    LessonWorkloadCategory.ASSESSMENT: MicrolearningEffortRange(20, 60),
    LessonWorkloadCategory.CAPSTONE: MicrolearningEffortRange(60, 180),
}

_EFFORT_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>hours?|hrs?|h|minutes?|mins?|m)\b",
    re.IGNORECASE,
)


def parse_expected_learning_effort_hours(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    match = _EFFORT_PATTERN.search(value)
    if match is None:
        return None
    amount = float(match.group("value"))
    unit = match.group("unit").lower()
    return amount / 60 if unit.startswith(("minute", "min", "m")) else amount


def effort_fit(target_hours: float | None, estimated_hours: float) -> str:
    if target_hours is None:
        return "UNSPECIFIED"
    lower = target_hours * (1 - EFFORT_TOLERANCE_PERCENT / 100)
    upper = target_hours * (1 + EFFORT_TOLERANCE_PERCENT / 100)
    if estimated_hours < lower:
        return "UNDER_TARGET"
    if estimated_hours > upper:
        return "OVER_TARGET"
    return "WITHIN_TARGET"
