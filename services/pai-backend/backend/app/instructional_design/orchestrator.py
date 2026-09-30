"""Assembly boundary for research snapshots; provider execution remains outside this module."""

from collections.abc import Sequence

from app.instructional_design.dependency_normalizer import normalize_assessment_dependencies
from app.instructional_design.policy import (
    INSTRUCTIONAL_DESIGN_POLICY_V0_1,
    InstructionalDesignPolicy,
)
from app.instructional_design.provenance_aliases import (
    DependencyIdentity,
    resolve_dependency_identity,
)
from app.instructional_design.quality_gate import evaluate_instructional_design
from app.instructional_design.schemas import (
    AssessmentDependencyCandidate,
    AssessmentSpec,
    CourseOutline,
    DesignFinding,
    DesignFindingSeverity,
    GenerationProvenance,
    InstructionalDesignResearchSnapshot,
    LearningObjectiveSpec,
    LessonSpec,
    PrerequisiteClassification,
    PrerequisiteSpec,
    ResearchLearningBrief,
)
from app.instructional_design.workload import WorkloadValidationResult


def deduplicate_exact_prerequisites(
    prerequisites: Sequence[PrerequisiteSpec],
) -> list[PrerequisiteSpec]:
    """Collapse only exact normalized capability duplicates; preserve first provenance."""

    seen: dict[tuple[str, PrerequisiteClassification], PrerequisiteSpec] = {}
    for item in prerequisites:
        key = (" ".join(item.capability.casefold().split()), item.classification)
        if key not in seen:
            seen[key] = item
            continue
        existing = seen[key]
        seen[key] = existing.model_copy(
            update={
                "required_for_refs": list(
                    dict.fromkeys([*existing.required_for_refs, *item.required_for_refs])
                )
            }
        )
    return list(seen.values())


def attach_prerequisite_dependency_provenance(
    prerequisites: Sequence[PrerequisiteSpec],
    dependency_candidates: Sequence[AssessmentDependencyCandidate],
    *,
    dependency_identities: Sequence[DependencyIdentity] = (),
    findings: list[DesignFinding] | None = None,
) -> list[PrerequisiteSpec]:
    """Recover a missing candidate edge without inventing semantic provenance.

    The model may emit a disposition without ``source_dependency_refs`` even
    though the preceding assessment stage emitted the same dependency.  The
    orchestration boundary may restore that mechanical edge by exact
    normalized capability equality.  Existing refs are immutable; unmatched
    values remain unresolved and are never guessed.
    """

    recovered: list[PrerequisiteSpec] = []
    for prerequisite in prerequisites:
        if prerequisite.source_dependency_refs:
            recovered.append(prerequisite)
            continue
        resolution = resolve_dependency_identity(
            prerequisite.capability,
            dependency_candidates,
            identities=dependency_identities,
        )
        refs = [resolution.dependency_ref] if resolution.dependency_ref else []
        if resolution.conflict and findings is not None:
            findings.append(
                DesignFinding(
                    code="dependency_alias_conflict",
                    severity=DesignFindingSeverity.ERROR,
                    entity_type="prerequisite",
                    entity_id=prerequisite.id,
                    field="source_dependency_refs",
                    message="A declared dependency alias matches multiple dependency identities.",
                )
            )
        recovered.append(
            prerequisite.model_copy(update={"source_dependency_refs": refs})
            if refs
            else prerequisite
        )
    return recovered


def attach_lesson_ids(
    course_outline: CourseOutline, lessons: Sequence[LessonSpec]
) -> CourseOutline:
    """Application-owned module -> lesson edges, derived after lesson generation."""

    lesson_ids_by_module: dict[str, list[str]] = {}
    for lesson in lessons:
        lesson_ids_by_module.setdefault(lesson.module_id, []).append(lesson.id)
    return course_outline.model_copy(
        update={
            "modules": [
                module.model_copy(
                    update={"lesson_ids": lesson_ids_by_module.get(module.id, [])}
                )
                for module in course_outline.modules
            ]
        }
    )


def build_research_snapshot(
    *,
    brief: ResearchLearningBrief,
    objectives: Sequence[LearningObjectiveSpec],
    assessments: Sequence[AssessmentSpec],
    dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
    prerequisites: Sequence[PrerequisiteSpec],
    course_outline: CourseOutline,
    lessons: Sequence[LessonSpec],
    generation_provenance: GenerationProvenance,
    policy: InstructionalDesignPolicy = INSTRUCTIONAL_DESIGN_POLICY_V0_1,
    workload_validation: WorkloadValidationResult | None = None,
    dependency_identities: Sequence[DependencyIdentity] = (),
) -> InstructionalDesignResearchSnapshot:
    """Snapshot already-proposed artifacts and apply trusted deterministic validation."""

    provenance_findings: list[DesignFinding] = []
    resolved_prerequisites = attach_prerequisite_dependency_provenance(
        prerequisites,
        dependency_candidates,
        dependency_identities=dependency_identities,
        findings=provenance_findings,
    )
    normalized_results = [
        normalize_assessment_dependencies(
            assessment,
            dependency_candidates=dependency_candidates,
        )
        for assessment in assessments
    ]
    normalized_dependencies = [
        dependency for result in normalized_results for dependency in result.dependencies
    ]
    normalization_findings = [
        finding for result in normalized_results for finding in result.findings
    ]
    quality_report = evaluate_instructional_design(
        brief=brief,
        objectives=objectives,
        assessments=assessments,
        canonical_dependencies=normalized_dependencies,
        dependency_normalization_findings=normalization_findings,
        prerequisites=resolved_prerequisites,
        course_outline=course_outline,
        lessons=lessons,
        policy=policy,
        workload_validation=workload_validation,
    )
    if provenance_findings:
        quality_report = quality_report.model_copy(
            update={"findings": [*quality_report.findings, *provenance_findings]}
        )
    return InstructionalDesignResearchSnapshot(
        snapshot_version="instructional-design-research-snapshot@0.1",
        brief=brief,
        objectives=list(objectives),
        assessments=list(assessments),
        dependency_candidates=list(dependency_candidates),
        prerequisites=resolved_prerequisites,
        canonical_dependencies=normalized_dependencies,
        course_outline=course_outline,
        lessons=list(lessons),
        quality_report=quality_report,
        generation_provenance=generation_provenance,
    )
