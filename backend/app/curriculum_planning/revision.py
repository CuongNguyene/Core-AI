from __future__ import annotations

from enum import StrEnum
from typing import Any

from app.course_authoring.brief_revision_schemas import BriefRevisionPayload

from .microlearning import MICROLEARNING_POLICY_VERSION
from .schemas import CurriculumLessonPlan, CurriculumPlan
from .validation import collect_curriculum_plan_validation
from .workload import workload_profile_for

CURRICULUM_REVIEW_WORKFLOW_VERSION = "sep-08d-v1"


class CurriculumFeedbackAction(StrEnum):
    REDUCE_EMPHASIS = "REDUCE_EMPHASIS"
    INCREASE_EMPHASIS = "INCREASE_EMPHASIS"
    REMOVE_UNIT = "REMOVE_UNIT"
    ADD_UNIT = "ADD_UNIT"
    MOVE_UNIT = "MOVE_UNIT"
    MERGE_UNITS = "MERGE_UNITS"
    SPLIT_UNIT = "SPLIT_UNIT"
    REORDER_MODULE = "REORDER_MODULE"
    REORDER_UNIT = "REORDER_UNIT"
    ADJUST_PRACTICE = "ADJUST_PRACTICE"
    ADJUST_ASSESSMENT = "ADJUST_ASSESSMENT"
    ADJUST_EFFORT = "ADJUST_EFFORT"
    OTHER = "OTHER"


class CurriculumPatchOperation(StrEnum):
    UPDATE_UNIT_EFFORT = "UPDATE_UNIT_EFFORT"
    REMOVE_UNIT = "REMOVE_UNIT"
    ADD_UNIT = "ADD_UNIT"


def _normalized(value: str) -> str:
    return " ".join(value.lower().split())


def validate_patch_scope(
    operations: list[dict[str, Any]], brief: BriefRevisionPayload
) -> None:
    confirmed_scope = _normalized(" ".join((*brief.desired_outcomes, brief.training_goal)))
    for operation in operations:
        if operation.get("op") != CurriculumPatchOperation.ADD_UNIT.value:
            continue
        fields = operation.get("fields") or {}
        title = str(fields.get("title", "")).strip()
        if not title or _normalized(title) not in confirmed_scope:
            raise ValueError("SCOPE_EXPANSION_REQUIRES_BRIEF_REVISION")


def _update_effort(lesson: CurriculumLessonPlan, minutes: int) -> CurriculumLessonPlan:
    profile = workload_profile_for(lesson.lesson_type)
    instruction = round(minutes * profile.instruction_ratio)
    return lesson.model_copy(update={
        "estimated_minutes": minutes,
        "estimated_instruction_minutes": instruction,
        "estimated_practice_minutes": minutes - instruction,
        "estimated_total_effort_minutes": minutes,
        "workload_category": profile.category,
    })


def apply_curriculum_patch(plan: CurriculumPlan, operations: list[dict[str, Any]]) -> CurriculumPlan:
    updated = plan
    for operation in operations:
        op = operation.get("op")
        target_ref = operation.get("target_ref")
        if op == CurriculumPatchOperation.UPDATE_UNIT_EFFORT.value:
            minutes = int((operation.get("fields") or {}).get("estimated_minutes", 0))
            if minutes <= 0:
                raise ValueError("curriculum_revision_invalid")
            found = False
            modules = []
            for module in updated.modules:
                lessons = []
                for lesson in module.lessons:
                    if lesson.id == target_ref:
                        lesson = _update_effort(lesson, minutes)
                        found = True
                    lessons.append(lesson)
                modules.append(module.model_copy(update={
                    "lessons": lessons,
                    "estimated_hours": sum(item.estimated_minutes for item in lessons) / 60,
                }))
            if not found:
                raise ValueError("curriculum_revision_invalid")
            updated = updated.model_copy(update={"modules": modules})
        elif op in {CurriculumPatchOperation.REMOVE_UNIT.value, CurriculumPatchOperation.ADD_UNIT.value}:
            raise ValueError("curriculum_revision_operation_not_supported")
        else:
            raise ValueError("curriculum_revision_operation_not_supported")
    return updated


def validate_revised_plan(plan: CurriculumPlan) -> None:
    report = collect_curriculum_plan_validation(plan)
    if not report.valid:
        raise ValueError("curriculum_revision_invalid")
    if plan.planning_metadata.get("planning_strategy") == MICROLEARNING_POLICY_VERSION:
        for module in plan.modules:
            for lesson in module.lessons:
                if lesson.estimated_minutes <= 0:
                    raise ValueError("curriculum_revision_invalid")
