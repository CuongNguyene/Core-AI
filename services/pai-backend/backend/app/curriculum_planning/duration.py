import re
from enum import StrEnum
from math import ceil

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_WEEKLY_EFFORT_HOURS = 3


class DurationUnit(StrEnum):
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class WeeklyEffortSource(StrEnum):
    USER_PROVIDED = "USER_PROVIDED"
    DEFAULT = "DEFAULT"
    UNKNOWN = "UNKNOWN"


class NormalizedTrainingDuration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    original: str | None = None
    duration_value: float | None = Field(default=None, gt=0)
    duration_unit: DurationUnit | None = None
    estimated_total_weeks: int | None = Field(default=None, ge=1)
    weekly_effort_hours: float | None = Field(default=None, gt=0)
    weekly_effort_source: WeeklyEffortSource = WeeklyEffortSource.UNKNOWN
    estimated_total_learning_hours: float | None = Field(default=None, gt=0)


_DURATION_PATTERN = re.compile(
    r"^\s*(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>hours?|hrs?|h|days?|d|weeks?|wks?|w|months?|mos?|mo)\s*$",
    re.IGNORECASE,
)


def normalize_training_duration(
    value: str | None,
    *,
    weekly_effort_hours: float | None = None,
) -> NormalizedTrainingDuration:
    if value is None or not value.strip():
        return NormalizedTrainingDuration()

    match = _DURATION_PATTERN.match(value)
    if match is None:
        return NormalizedTrainingDuration(original=value.strip())

    numeric = float(match.group("value"))
    raw_unit = match.group("unit").lower()
    if raw_unit.startswith(("hour", "hr", "h")):
        unit = DurationUnit.HOURS
        total_hours = numeric
        weeks = ceil(total_hours / (weekly_effort_hours or DEFAULT_WEEKLY_EFFORT_HOURS))
    elif raw_unit.startswith(("day", "d")):
        unit = DurationUnit.DAYS
        weeks = max(1, ceil(numeric / 7))
        total_hours = max(
            weekly_effort_hours or DEFAULT_WEEKLY_EFFORT_HOURS,
            (numeric / 7) * (weekly_effort_hours or DEFAULT_WEEKLY_EFFORT_HOURS),
        )
    elif raw_unit.startswith(("week", "wk", "w")):
        unit = DurationUnit.WEEKS
        weeks = ceil(numeric)
        total_hours = weeks * (weekly_effort_hours or DEFAULT_WEEKLY_EFFORT_HOURS)
    else:
        unit = DurationUnit.MONTHS
        weeks = ceil(numeric * 52 / 12)
        total_hours = weeks * (weekly_effort_hours or DEFAULT_WEEKLY_EFFORT_HOURS)

    effort = weekly_effort_hours or DEFAULT_WEEKLY_EFFORT_HOURS
    return NormalizedTrainingDuration(
        original=value.strip(),
        duration_value=numeric,
        duration_unit=unit,
        estimated_total_weeks=weeks,
        weekly_effort_hours=effort,
        weekly_effort_source=(
            WeeklyEffortSource.USER_PROVIDED
            if weekly_effort_hours is not None
            else WeeklyEffortSource.DEFAULT
        ),
        estimated_total_learning_hours=total_hours,
    )
