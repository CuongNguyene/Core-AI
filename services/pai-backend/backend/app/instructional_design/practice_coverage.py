"""Deterministic practice-before-summative coverage tracing."""

from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.instructional_design.schemas import (
    AssessmentRole,
    AssessmentSpec,
    CourseOutline,
    DesignFinding,
    DesignFindingSeverity,
    InstructionalPattern,
    LessonSpec,
)


class CoverageStatus(StrEnum):
    COVERED = "covered"
    PARTIALLY_COVERED = "partially_covered"
    NOT_COVERED = "not_covered"
    UNRESOLVED = "unresolved"


class AssessmentCoverageRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    assessment_id: str = Field(min_length=1)
    assessment_role: AssessmentRole
    objective_refs: list[str] = Field(default_factory=list)
    capability_ref: str = Field(min_length=1)
    source_requirement_ref: str = Field(min_length=1)
    instruction_refs: list[str] = Field(default_factory=list)
    guided_practice_refs: list[str] = Field(default_factory=list)
    independent_practice_refs: list[str] = Field(default_factory=list)
    formative_refs: list[str] = Field(default_factory=list)
    status: CoverageStatus


class PracticeCoverageResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    traces: list[AssessmentCoverageRequirement] = Field(default_factory=list)
    findings: list[DesignFinding] = Field(default_factory=list)


def planner_coverage_requirements(assessments: Sequence[AssessmentSpec]) -> list[dict[str, object]]:
    """Expose explicit summative requirements to planners without trusting status output."""

    requirements: list[dict[str, object]] = []
    for assessment in assessments:
        if assessment.effective_role is not AssessmentRole.SUMMATIVE:
            continue
        for index, requirement in enumerate(assessment.required_capabilities):
            requirements.append({
                "assessment_id": assessment.id,
                "objective_refs": list(requirement.objective_ids or assessment.objective_ids),
                "capability_ref": requirement.name,
                "source_requirement_ref": f"{assessment.id}:required_capabilities:{index}",
            })
    return requirements


_INSTRUCTION = {
    InstructionalPattern.EXPLANATION,
    InstructionalPattern.DEMONSTRATION,
    InstructionalPattern.WORKED_EXAMPLE,
}
_GUIDED = {InstructionalPattern.GUIDED_PRACTICE}
_INDEPENDENT = {
    InstructionalPattern.INDEPENDENT_PRACTICE,
    InstructionalPattern.SCENARIO,
    InstructionalPattern.REFLECTION,
}


def _finding(code: str, entity_id: str, message: str) -> DesignFinding:
    return DesignFinding(
        code=code,
        severity=DesignFindingSeverity.ERROR,
        entity_type="assessment",
        entity_id=entity_id,
        field="practice_coverage",
        message=message,
    )


def evaluate_practice_coverage(
    *,
    assessments: Sequence[AssessmentSpec],
    course_outline: CourseOutline,
    lessons: Sequence[LessonSpec],
) -> PracticeCoverageResult:
    """Trace explicit objective/lesson/assessment refs; never match free text."""

    assessment_by_id = {assessment.id: assessment for assessment in assessments}
    ordered_ids = [
        lesson_id
        for module in course_outline.modules
        for lesson_id in module.lesson_ids
        if any(lesson.id == lesson_id for lesson in lessons)
    ]
    # Artifacts without populated module.lesson_ids retain input order for a deterministic fallback.
    if not ordered_ids:
        ordered_ids = [lesson.id for lesson in lessons]
    position = {lesson_id: index for index, lesson_id in enumerate(ordered_ids)}
    findings: list[DesignFinding] = []

    for lesson in lessons:
        for assessment_id in lesson.formative_assessment_ids:
            referenced = assessment_by_id.get(assessment_id)
            if referenced is not None and referenced.effective_role is not AssessmentRole.FORMATIVE:
                findings.append(_finding("practice_reference_role_mismatch", lesson.id, "A formative reference must target a formative assessment."))
        for assessment_id in lesson.summative_assessment_ids:
            referenced = assessment_by_id.get(assessment_id)
            if referenced is not None and referenced.effective_role is not AssessmentRole.SUMMATIVE:
                findings.append(_finding("practice_reference_role_mismatch", lesson.id, "A summative reference must target a summative assessment."))

    traces: list[AssessmentCoverageRequirement] = []
    for assessment in assessments:
        if assessment.effective_role is not AssessmentRole.SUMMATIVE:
            continue
        summative_positions = [
            position[lesson.id]
            for lesson in lessons
            if assessment.id in lesson.summative_assessment_ids and lesson.id in position
        ]
        summative_position = min(summative_positions) if summative_positions else len(ordered_ids)
        requirements = assessment.required_capabilities
        for index, requirement in enumerate(requirements):
            objective_refs = list(requirement.objective_ids or assessment.objective_ids)
            source_ref = f"{assessment.id}:required_capabilities:{index}"
            if not objective_refs:
                traces.append(AssessmentCoverageRequirement(
                    assessment_id=assessment.id, assessment_role=assessment.effective_role,
                    objective_refs=[], capability_ref=requirement.name,
                    source_requirement_ref=source_ref, status=CoverageStatus.UNRESOLVED,
                ))
                findings.append(_finding("assessment_requirement_not_taught", assessment.id, "Coverage requirement has no resolvable objective reference."))
                continue
            instruction_refs: list[str] = []
            guided_refs: list[str] = []
            independent_refs: list[str] = []
            formative_refs: list[str] = []
            after_refs: list[str] = []
            for lesson in lessons:
                if not set(objective_refs).intersection(lesson.objective_ids):
                    continue
                lesson_position = position.get(lesson.id, len(ordered_ids))
                if lesson_position >= summative_position:
                    if lesson_position > summative_position and lesson.instructional_pattern in (_GUIDED | _INDEPENDENT):
                        after_refs.append(lesson.id)
                    if assessment.id in lesson.formative_assessment_ids:
                        findings.append(_finding("summative_used_as_practice", assessment.id, "A summative assessment cannot satisfy its own prior practice requirement."))
                    continue
                if lesson.instructional_pattern in _INSTRUCTION:
                    instruction_refs.append(lesson.id)
                if lesson.instructional_pattern in _GUIDED:
                    guided_refs.append(lesson.id)
                if lesson.instructional_pattern in _INDEPENDENT:
                    independent_refs.append(lesson.id)
                for formative_id in lesson.formative_assessment_ids:
                    referenced = assessment_by_id.get(formative_id)
                    if referenced is not None and referenced.effective_role is AssessmentRole.FORMATIVE:
                        formative_refs.append(formative_id)
            if after_refs:
                findings.append(_finding("practice_reference_after_summative", assessment.id, "Practice after summative assessment does not count as prior coverage."))
            if not instruction_refs:
                status = CoverageStatus.NOT_COVERED
                findings.append(_finding("assessment_requirement_not_taught", assessment.id, "Summative requirement has no prior explicit instruction."))
            elif not (guided_refs or independent_refs or formative_refs):
                status = CoverageStatus.PARTIALLY_COVERED
                findings.append(_finding("practice_before_summative_missing", assessment.id, "Summative requirement has instruction but no prior practice or formative evidence."))
            else:
                status = CoverageStatus.COVERED
            traces.append(AssessmentCoverageRequirement(
                assessment_id=assessment.id, assessment_role=assessment.effective_role,
                objective_refs=objective_refs, capability_ref=requirement.name,
                source_requirement_ref=source_ref, instruction_refs=instruction_refs,
                guided_practice_refs=guided_refs, independent_practice_refs=independent_refs,
                formative_refs=formative_refs, status=status,
            ))
    findings.sort(key=lambda item: (item.code, item.entity_id or ""))
    return PracticeCoverageResult(traces=traces, findings=findings)
