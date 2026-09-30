"""Auditable workload/time-budget semantics for instructional-design planning.

These are planning estimates, not predictions of learner completion time. Category
allocations are the arithmetic source of truth; lesson/module totals are context
and must not be added a second time.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkloadCategory(StrEnum):
    INSTRUCTION = "instruction"
    GUIDED_PRACTICE = "guided_practice"
    INDEPENDENT_PRACTICE = "independent_practice"
    FORMATIVE_ASSESSMENT = "formative_assessment"
    SUMMATIVE_ASSESSMENT = "summative_assessment"
    FEEDBACK_REVISION = "feedback_revision"


class WorkloadBudgetStatus(StrEnum):
    WITHIN_BUDGET = "within_budget"
    NEAR_LIMIT = "near_limit"
    OVER_BUDGET = "over_budget"


class WorkloadBudgetPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    policy_id: str = "workload_budget_policy"
    policy_version: str = "0.1"
    near_limit_slack_ratio: float = Field(default=0.10, ge=0, le=1)


DEFAULT_WORKLOAD_BUDGET_POLICY = WorkloadBudgetPolicy()


class WorkloadBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    declared_total_minutes: int = Field(gt=0)
    categories: dict[WorkloadCategory, int] = Field(default_factory=dict)
    planned_total_minutes: int = Field(ge=0)
    unallocated_minutes: int = Field(ge=0)
    over_budget_minutes: int = Field(ge=0)
    status: WorkloadBudgetStatus
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def arithmetic_is_consistent(self) -> WorkloadBudget:
        expected = sum(self.categories.values())
        if expected != self.planned_total_minutes:
            raise ValueError("planned_total_minutes must equal category allocation sum")
        if self.unallocated_minutes != max(self.declared_total_minutes - expected, 0):
            raise ValueError("unallocated_minutes is inconsistent with declared budget")
        if self.over_budget_minutes != max(expected - self.declared_total_minutes, 0):
            raise ValueError("over_budget_minutes is inconsistent with declared budget")
        return self


class WorkloadValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    budget: WorkloadBudget | None = None
    findings: list[dict[str, str | int]] = Field(default_factory=list)


class WorkloadBudgetContext(BaseModel):
    """Explicit planner input; it never lets model output redefine the budget."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    declared_total_minutes: int = Field(gt=0)
    assessment_time_requirements: dict[str, int | None] = Field(default_factory=dict)
    allocated_module_minutes: dict[str, int | None] = Field(default_factory=dict)
    allocated_lesson_minutes: dict[str, int | None] = Field(default_factory=dict)


def build_workload_budget_context(
    *,
    declared_total_minutes: int,
    assessments: Mapping[str, int | None],
    modules: Mapping[str, int | None] | None = None,
    lessons: Mapping[str, int | None] | None = None,
) -> WorkloadBudgetContext:
    return WorkloadBudgetContext(
        declared_total_minutes=declared_total_minutes,
        assessment_time_requirements=dict(assessments),
        allocated_module_minutes=dict(modules or {}),
        allocated_lesson_minutes=dict(lessons or {}),
    )


def calculate_workload_budget(
    *,
    declared_total_minutes: int,
    categories: Mapping[WorkloadCategory, int],
    policy: WorkloadBudgetPolicy = DEFAULT_WORKLOAD_BUDGET_POLICY,
) -> WorkloadBudget:
    """Calculate a budget from canonical category allocations only."""

    if declared_total_minutes <= 0:
        raise ValueError("declared_total_minutes must be positive")
    if any(minutes < 0 for minutes in categories.values()):
        raise ValueError("workload minutes cannot be negative")
    planned = sum(categories.values())
    slack = max(declared_total_minutes - planned, 0)
    over = max(planned - declared_total_minutes, 0)
    status = (
        WorkloadBudgetStatus.OVER_BUDGET
        if over
        else WorkloadBudgetStatus.NEAR_LIMIT
        if 0 < slack <= declared_total_minutes * policy.near_limit_slack_ratio
        else WorkloadBudgetStatus.WITHIN_BUDGET
    )
    return WorkloadBudget(
        declared_total_minutes=declared_total_minutes,
        categories=dict(categories),
        planned_total_minutes=planned,
        unallocated_minutes=slack,
        over_budget_minutes=over,
        status=status,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
    )


def validate_workload_allocations(
    *,
    declared_total_minutes: int,
    categories: Mapping[WorkloadCategory, int | None],
    policy: WorkloadBudgetPolicy = DEFAULT_WORKLOAD_BUDGET_POLICY,
) -> WorkloadValidationResult:
    """Reject unresolved categories rather than treating missing time as zero."""

    missing = sorted(category.value for category, minutes in categories.items() if minutes is None)
    if missing:
        return WorkloadValidationResult(
            findings=[{
                "code": "workload_time_allocation_missing",
                "severity": "error",
                "field": ",".join(missing),
                "message": "Required workload allocation is unresolved; missing time is not zero.",
            }]
        )
    budget = calculate_workload_budget(
        declared_total_minutes=declared_total_minutes,
        categories={category: cast(int, minutes) for category, minutes in categories.items()},
        policy=policy,
    )
    findings: list[dict[str, str | int]] = []
    if budget.status is WorkloadBudgetStatus.OVER_BUDGET:
        findings.append({
            "code": "workload_time_budget_exceeded",
            "severity": "warning",
            "declared_minutes": budget.declared_total_minutes,
            "planned_minutes": budget.planned_total_minutes,
            "over_budget_minutes": budget.over_budget_minutes,
            "message": "Planned workload exceeds the declared learning-time budget.",
        })
    return WorkloadValidationResult(budget=budget, findings=findings)
