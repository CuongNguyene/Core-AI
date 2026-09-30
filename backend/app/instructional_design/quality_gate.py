"""Deterministic quality checks for research instructional-design artifacts."""

from collections.abc import Sequence

from app.instructional_design.contracts import review_prerequisite_structural_minimality
from app.instructional_design.dependency_normalizer import (
    normalize_assessment_dependencies,
    normalize_capability_text,
)
from app.instructional_design.policy import (
    INSTRUCTIONAL_DESIGN_POLICY_V0_1,
    InstructionalDesignPolicy,
)
from app.instructional_design.practice_coverage import evaluate_practice_coverage
from app.instructional_design.prerequisite_minimality import validate_prerequisite_dispositions
from app.instructional_design.schemas import (
    AssessmentSpec,
    CanonicalAssessmentDependency,
    CourseOutline,
    DesignFinding,
    DesignFindingSeverity,
    InstructionalDesignQualityReport,
    InstructionalPattern,
    LearningObjectiveSpec,
    LessonSpec,
    PrerequisiteSpec,
    PrerequisiteStatus,
    ResearchLearningBrief,
)
from app.instructional_design.workload import WorkloadValidationResult

_PRACTICE_PATTERNS = {
    InstructionalPattern.WORKED_EXAMPLE,
    InstructionalPattern.GUIDED_PRACTICE,
    InstructionalPattern.SCENARIO,
    InstructionalPattern.INDEPENDENT_PRACTICE,
}


def _finding(
    code: str,
    severity: DesignFindingSeverity,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    field: str | None = None,
    message: str,
) -> DesignFinding:
    return DesignFinding(
        code=code,
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        message=message,
    )


def _is_obviously_unobservable(performance: str, policy: InstructionalDesignPolicy) -> bool:
    normalized = " ".join(performance.casefold().split())
    return any(normalized.startswith(prefix) for prefix in policy.obvious_non_observable_prefixes)


def _confirmed_prerequisite_cycles(
    prerequisites: Sequence[PrerequisiteSpec],
) -> list[tuple[str, ...]]:
    confirmed = {
        item.id: item for item in prerequisites if item.status is PrerequisiteStatus.CONFIRMED
    }
    graph = {
        item_id: tuple(ref for ref in item.requires_prerequisite_refs if ref in confirmed)
        for item_id, item in confirmed.items()
    }
    visited: set[str] = set()
    stack: list[str] = []
    in_stack: set[str] = set()
    cycles: list[tuple[str, ...]] = []

    def visit(node_id: str) -> None:
        if node_id in in_stack:
            start = stack.index(node_id)
            cycles.append(tuple(stack[start:] + [node_id]))
            return
        if node_id in visited:
            return
        visited.add(node_id)
        stack.append(node_id)
        in_stack.add(node_id)
        for dependency_id in graph[node_id]:
            visit(dependency_id)
        in_stack.remove(node_id)
        stack.pop()

    for node_id in sorted(graph):
        visit(node_id)
    return cycles


def _lesson_positions(
    course_outline: CourseOutline, lessons: Sequence[LessonSpec]
) -> dict[str, int]:
    known_lessons = {lesson.id for lesson in lessons}
    return {
        lesson_id: position
        for position, lesson_id in enumerate(
            lesson_id
            for module in course_outline.modules
            for lesson_id in module.lesson_ids
            if lesson_id in known_lessons
        )
    }


def evaluate_instructional_design(
    *,
    brief: ResearchLearningBrief,
    objectives: Sequence[LearningObjectiveSpec],
    assessments: Sequence[AssessmentSpec],
    canonical_dependencies: Sequence[CanonicalAssessmentDependency] | None = None,
    dependency_normalization_findings: Sequence[DesignFinding] = (),
    prerequisites: Sequence[PrerequisiteSpec],
    course_outline: CourseOutline,
    lessons: Sequence[LessonSpec],
    policy: InstructionalDesignPolicy = INSTRUCTIONAL_DESIGN_POLICY_V0_1,
    workload_validation: WorkloadValidationResult | None = None,
) -> InstructionalDesignQualityReport:
    """Return a reproducible report; no model output is trusted as a gate decision."""

    findings: list[DesignFinding] = list(dependency_normalization_findings)
    findings.extend(validate_prerequisite_dispositions(prerequisites))
    practice_coverage = evaluate_practice_coverage(
        assessments=assessments,
        course_outline=course_outline,
        lessons=lessons,
    )
    findings.extend(practice_coverage.findings)
    if workload_validation is not None:
        for workload_finding in workload_validation.findings:
            findings.append(
                _finding(
                    str(workload_finding["code"]),
                    DesignFindingSeverity(str(workload_finding["severity"])),
                    field=str(workload_finding.get("field", "workload")),
                    message=str(workload_finding["message"]),
                )
            )
    objective_by_id = {objective.id: objective for objective in objectives}
    assessment_objective_ids = {
        objective_id for assessment in assessments for objective_id in assessment.objective_ids
    }
    lesson_objective_ids = {
        objective_id for lesson in lessons for objective_id in lesson.objective_ids
    }

    for objective in objectives:
        if _is_obviously_unobservable(objective.performance, policy):
            findings.append(
                _finding(
                    "objective_not_observable",
                    DesignFindingSeverity.ERROR,
                    entity_type="learning_objective",
                    entity_id=objective.id,
                    field="performance",
                    message="Objective uses an obviously non-observable formulation.",
                )
            )
        if objective.id not in assessment_objective_ids:
            findings.append(
                _finding(
                    "objective_without_assessment",
                    DesignFindingSeverity.ERROR,
                    entity_type="learning_objective",
                    entity_id=objective.id,
                    message="Every objective requires at least one assessment.",
                )
            )
        if objective.id not in lesson_objective_ids:
            findings.append(
                _finding(
                    "objective_not_taught",
                    DesignFindingSeverity.ERROR,
                    entity_type="learning_objective",
                    entity_id=objective.id,
                    message="Objective is assessed or declared but not covered by a lesson.",
                )
            )

    for assessment in assessments:
        if not assessment.objective_ids:
            findings.append(
                _finding(
                    "orphan_assessment",
                    DesignFindingSeverity.ERROR,
                    entity_type="assessment",
                    entity_id=assessment.id,
                    field="objective_ids",
                    message="Assessment must reference at least one objective.",
                )
            )
        if not assessment.required_evidence or not assessment.task.description.strip():
            findings.append(
                _finding(
                    "assessment_evidence_task_not_structurally_aligned",
                    DesignFindingSeverity.ERROR,
                    entity_type="assessment",
                    entity_id=assessment.id,
                    message="Assessment task must structurally elicit at least one evidence criterion.",
                )
            )
        for objective_id in assessment.objective_ids:
            referenced_objective = objective_by_id.get(objective_id)
            if referenced_objective is None:
                continue
            if policy.cognitive_rank(assessment.cognitive_process) < policy.cognitive_rank(
                referenced_objective.cognitive_process
            ):
                findings.append(
                    _finding(
                        "insufficient_cognitive_demand",
                        (
                            DesignFindingSeverity.ERROR
                            if assessment.effective_role.value == "summative"
                            else DesignFindingSeverity.WARNING
                        ),
                        entity_type="assessment",
                        entity_id=assessment.id,
                        message="Assessment cognitive demand is below its objective demand.",
                    )
                )

    for module in course_outline.modules:
        if not module.objective_ids:
            findings.append(
                _finding(
                    "orphan_module",
                    DesignFindingSeverity.ERROR,
                    entity_type="course_module",
                    entity_id=module.id,
                    field="objective_ids",
                    message="Course module must reference at least one objective.",
                )
            )
        expected_lesson_ids = {
            lesson.id for lesson in lessons if lesson.module_id == module.id
        }
        if set(module.lesson_ids) != expected_lesson_ids:
            findings.append(
                _finding(
                    "module_lesson_ids_mismatch",
                    DesignFindingSeverity.ERROR,
                    entity_type="course_module",
                    entity_id=module.id,
                    field="lesson_ids",
                    message="Module lesson_ids must equal the lessons assigned to the module.",
                )
            )
        if module.objective_ids and not expected_lesson_ids:
            findings.append(
                _finding(
                    "module_without_instruction",
                    DesignFindingSeverity.ERROR,
                    entity_type="course_module",
                    entity_id=module.id,
                    field="lesson_ids",
                    message="An objective-linked module requires at least one instructional lesson.",
                )
            )

    declared_module_minutes = sum(module.estimated_minutes or 0 for module in course_outline.modules)
    if (
        course_outline.estimated_minutes is not None
        and declared_module_minutes > course_outline.estimated_minutes
        and not any(
            warning.type.value == "scope_time_conflict"
            and warning.decision.value == "prioritized_core_objectives"
            for warning in course_outline.planning_warnings
        )
    ):
        findings.append(
            _finding(
                "scope_time_conflict_missing_planning_warning",
                DesignFindingSeverity.WARNING,
                entity_type="course_outline",
                entity_id=course_outline.id,
                field="planning_warnings",
                message="Declared module duration exceeds course duration without a scope/time decision.",
            )
        )

    module_by_id = {module.id: module for module in course_outline.modules}
    assessment_by_id = {assessment.id: assessment for assessment in assessments}
    for lesson in lessons:
        if not lesson.objective_ids:
            findings.append(
                _finding(
                    "orphan_lesson",
                    DesignFindingSeverity.ERROR,
                    entity_type="lesson",
                    entity_id=lesson.id,
                    field="objective_ids",
                    message="Lesson must reference at least one objective.",
                )
            )
        lesson_module = module_by_id.get(lesson.module_id)
        for objective_id in lesson.objective_ids:
            if objective_id not in course_outline.objective_ids:
                findings.append(
                    _finding(
                        "lesson_objective_not_in_course_outline",
                        DesignFindingSeverity.ERROR,
                        entity_type="lesson",
                        entity_id=lesson.id,
                        field="objective_ids",
                        message="Lesson objective must be declared by the course outline.",
                    )
                )
            if lesson_module is not None and objective_id not in lesson_module.objective_ids:
                findings.append(
                    _finding(
                        "lesson_objective_not_owned_by_module",
                        DesignFindingSeverity.ERROR,
                        entity_type="lesson",
                        entity_id=lesson.id,
                        field="objective_ids",
                        message="Lesson objective must be owned by its referenced module.",
                    )
                )
        for assessment_id in lesson.formative_assessment_ids:
            referenced_assessment = assessment_by_id.get(assessment_id)
            if (
                referenced_assessment is not None
                and referenced_assessment.effective_role.value != "formative"
            ):
                findings.append(
                    _finding(
                        "lesson_formative_assessment_is_not_formative",
                        DesignFindingSeverity.ERROR,
                        entity_type="lesson",
                        entity_id=lesson.id,
                        field="formative_assessment_ids",
                        message="formative_assessment_ids may reference only formative assessments.",
                    )
                )

    practice_objective_ids = {
        objective_id
        for lesson in lessons
        if lesson.instructional_pattern in _PRACTICE_PATTERNS
        for objective_id in lesson.objective_ids
    }
    for assessment in assessments:
        if assessment.effective_role.value != "summative":
            continue
        for objective_id in assessment.objective_ids:
            assessed_objective = objective_by_id.get(objective_id)
            if assessed_objective is None or assessed_objective.cognitive_process.value in {
                "remember",
                "understand",
            }:
                continue
            if objective_id not in practice_objective_ids:
                findings.append(
                    _finding(
                        "summative_without_prior_practice",
                        DesignFindingSeverity.ERROR,
                        entity_type="assessment",
                        entity_id=assessment.id,
                        field="objective_ids",
                        message="Applied or higher-order objectives require a preparatory practice activity.",
                    )
                )

    unresolved_prerequisites = [
        item.id for item in prerequisites if item.status is not PrerequisiteStatus.CONFIRMED
    ]
    for cycle in _confirmed_prerequisite_cycles(prerequisites):
        findings.append(
            _finding(
                "prerequisite_cycle",
                DesignFindingSeverity.BLOCKING,
                entity_type="prerequisite",
                entity_id=cycle[0],
                message=f"Confirmed prerequisite cycle: {' -> '.join(cycle)}.",
            )
        )

    prerequisite_by_id = {item.id: item for item in prerequisites}
    allowed_requirement_refs = set(objective_by_id) | set(assessment_by_id)
    for prerequisite in prerequisites:
        review = review_prerequisite_structural_minimality(
            prerequisite,
            allowed_requirement_refs=allowed_requirement_refs,
        )
        if review.status.value == "structurally_supported" or review.status.value == "not_applicable":
            continue
        findings.append(
            _finding(
                f"prerequisite_candidate_{review.status.value}",
                DesignFindingSeverity.WARNING,
                entity_type="prerequisite",
                entity_id=prerequisite.id,
                message="Prerequisite candidate needs reviewer attention before it can be treated as minimal.",
            )
        )
    lesson_positions = _lesson_positions(course_outline, lessons)
    lesson_positions_by_objective: dict[str, list[int]] = {}
    for lesson in lessons:
        position = lesson_positions.get(lesson.id)
        if position is None:
            continue
        for objective_id in lesson.objective_ids:
            lesson_positions_by_objective.setdefault(objective_id, []).append(position)
    for objective in objectives:
        dependent_positions = lesson_positions_by_objective.get(objective.id, [])
        if not dependent_positions:
            continue
        for prerequisite_id in objective.prerequisite_refs:
            referenced_prerequisite = prerequisite_by_id.get(prerequisite_id)
            if (
                referenced_prerequisite is None
                or referenced_prerequisite.status is not PrerequisiteStatus.CONFIRMED
                or referenced_prerequisite.teaching_objective_id is None
            ):
                continue
            teaching_positions = lesson_positions_by_objective.get(
                referenced_prerequisite.teaching_objective_id, []
            )
            if teaching_positions and min(teaching_positions) > min(dependent_positions):
                findings.append(
                    _finding(
                        "prerequisite_order_violation",
                        DesignFindingSeverity.ERROR,
                        entity_type="prerequisite",
                        entity_id=referenced_prerequisite.id,
                        message="Confirmed prerequisite is taught after its dependent objective.",
                    )
                )

    taught_capability_refs = {
        normalize_capability_text(capability_ref)
        for objective in objectives
        if objective.id in lesson_objective_ids
        for capability_ref in objective.capability_refs
    }
    covered_capability_refs = (
        {normalize_capability_text(value) for value in brief.learner_state.known}
        | taught_capability_refs
        | {
            normalize_capability_text(prerequisite.capability)
            for prerequisite in prerequisites
            if prerequisite.status is PrerequisiteStatus.CONFIRMED
        }
    )
    artifact_ids = (
        set(objective_by_id)
        | set(assessment_by_id)
        | set(prerequisite_by_id)
        | set(module_by_id)
        | {lesson.id for lesson in lessons}
    )
    if canonical_dependencies is None:
        normalized_results = [
            normalize_assessment_dependencies(assessment) for assessment in assessments
        ]
        canonical_dependencies = [
            dependency for result in normalized_results for dependency in result.dependencies
        ]
        findings.extend(
            finding for result in normalized_results for finding in result.findings
        )
    for dependency in canonical_dependencies:
        if dependency.dependency_role.value != "required_capability":
            continue
        capability_ref = normalize_capability_text(dependency.capability_ref)
        if capability_ref in {normalize_capability_text(value) for value in artifact_ids}:
            field = "required_capabilities"
            if any(
                source.type.value == "legacy_compatibility"
                for source in dependency.provenance.sources
            ):
                field = "required_capability_refs"
            source_ref = next(
                source.source_ref
                for source in dependency.provenance.sources
                if source.type.value
                in {"typed_required_capability", "legacy_compatibility"}
            )
            findings.append(
                _finding(
                    "assessment_capability_ref_is_artifact_id",
                    DesignFindingSeverity.ERROR,
                    entity_type="assessment",
                    entity_id=source_ref,
                    field=field,
                    message="Assessment capability requirements must be semantic capability strings, not artifact IDs.",
                )
            )
            continue
        if capability_ref not in covered_capability_refs:
            findings.append(
                _finding(
                    "assessment_dependency_not_covered",
                    DesignFindingSeverity.ERROR,
                    entity_type="assessment",
                    entity_id=next(
                        source.source_ref
                        for source in dependency.provenance.sources
                        if source.type.value
                        in {"typed_required_capability", "legacy_compatibility"}
                    ),
                    field="required_capabilities",
                    message="Assessment dependency is not known, confirmed, or taught by the course.",
                )
            )

    findings.sort(
        key=lambda finding: (
            finding.severity.value,
            finding.code,
            finding.entity_type or "",
            finding.entity_id or "",
        )
    )
    objective_count = len(objectives)
    taught_count = sum(item.id in lesson_objective_ids for item in objectives)
    assessed_count = sum(item.id in assessment_objective_ids for item in objectives)
    passed = not any(
        finding.severity in {DesignFindingSeverity.ERROR, DesignFindingSeverity.BLOCKING}
        for finding in findings
    )
    return InstructionalDesignQualityReport(
        passed=passed,
        findings=findings,
        objective_coverage=taught_count / objective_count if objective_count else 0.0,
        assessment_coverage=assessed_count / objective_count if objective_count else 0.0,
        unresolved_prerequisites=unresolved_prerequisites,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        practice_coverage=[trace.model_dump(mode="json") for trace in practice_coverage.traces],
    )
