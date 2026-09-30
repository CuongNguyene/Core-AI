"""Injected research runners for fair one-shot and staged design experiments."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from inspect import signature
from typing import Protocol, cast, runtime_checkable

from app.instructional_design.contracts import (
    ONE_SHOT_BASELINE_SCHEMA_ID,
    AssessmentDesigner,
    AssessmentDesignOutput,
    CoursePlanner,
    CoursePlanningOutput,
    LearningObjectiveDesignOutput,
    LessonPlanner,
    LessonPlanningOutput,
    ObjectiveDesigner,
    OneShotInstructionalDesignOutput,
    PrerequisiteProposalOutput,
    PrerequisiteProposer,
)
from app.instructional_design.experiment import (
    ExperimentCondition,
    ExperimentPartialArtifacts,
    ExperimentRun,
    ExperimentRunResult,
    ExperimentRunStatus,
    StageFailure,
)
from app.instructional_design.fixtures import ResearchFixtureBundle
from app.instructional_design.orchestrator import (
    attach_lesson_ids,
    attach_prerequisite_dependency_provenance,
    build_research_snapshot,
    deduplicate_exact_prerequisites,
)
from app.instructional_design.provenance_aliases import DependencyIdentity
from app.instructional_design.schemas import (
    AssessmentDependencyCandidate,
    AssessmentRole,
    AssessmentSpec,
    CourseOutline,
    GenerationProvenance,
    InstructionalPattern,
    LearningObjectiveSpec,
    LessonSpec,
    PrerequisiteSpec,
    ResearchLearningBrief,
)
from app.instructional_design.workload import (
    WorkloadCategory,
    WorkloadValidationResult,
    build_workload_budget_context,
    validate_workload_allocations,
)
from app.model_gateway.contracts import InferenceAuditMetadata


def _supports_workload_context(proposer: object) -> bool:
    return "workload_context" in signature(cast(Callable[..., object], proposer)).parameters


class OneShotInstructionalDesignGenerator(Protocol):
    async def generate(self, brief: ResearchLearningBrief) -> OneShotInstructionalDesignOutput: ...


class StructuredDesignerSet(Protocol):
    @property
    def objective(self) -> ObjectiveDesigner: ...

    @property
    def assessment(self) -> AssessmentDesigner: ...

    @property
    def prerequisite(self) -> PrerequisiteProposer: ...

    @property
    def course(self) -> CoursePlanner: ...

    @property
    def lesson(self) -> LessonPlanner: ...


@runtime_checkable
class AuditedModelCaller(Protocol):
    @property
    def model_audits(self) -> Sequence[InferenceAuditMetadata]: ...


def build_module_objective_scope(
    course_outline: CourseOutline,
    *,
    objective_ids: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    """Build the application-owned objective allow-list for each module."""

    allowed_objective_ids = set(objective_ids)
    if not set(course_outline.objective_ids).issubset(allowed_objective_ids):
        raise ValueError("course objective outside supplied objectives")
    scope: dict[str, tuple[str, ...]] = {}
    for module in course_outline.modules:
        if not set(module.objective_ids).issubset(allowed_objective_ids):
            raise ValueError("module objective outside course")
        scope[module.id] = tuple(module.objective_ids)
    return scope


def validate_lesson_objective_scope(
    *,
    module_objective_ids: Sequence[str],
    lesson_objective_ids: Sequence[str],
) -> None:
    """Fail closed when a lesson references an objective outside its module."""

    if not set(lesson_objective_ids).issubset(set(module_objective_ids)):
        raise ValueError("lesson objective outside module")


@dataclass(frozen=True)
class StructuredDesigners:
    objective: ObjectiveDesigner
    assessment: AssessmentDesigner
    prerequisite: PrerequisiteProposer
    course: CoursePlanner
    lesson: LessonPlanner


def _generation_provenance(
    run: ExperimentRun, brief: ResearchLearningBrief
) -> GenerationProvenance:
    if run.condition is ExperimentCondition.ONE_SHOT:
        prompt_schema_versions = [
            item
            for item in run.prompt_schema_versions
            if item.prompt_id == ONE_SHOT_BASELINE_SCHEMA_ID
        ]
    else:
        prompt_schema_versions = [
            item
            for item in run.prompt_schema_versions
            if item.prompt_id != ONE_SHOT_BASELINE_SCHEMA_ID
        ]
    if not prompt_schema_versions:
        raise ValueError("run lacks prompt/schema provenance for its condition")
    return GenerationProvenance(
        research_brief_id=brief.id,
        instructional_design_policy_id=run.policy_id,
        instructional_design_policy_version=run.policy_version,
        prompt_versions={
            item.prompt_id: item.prompt_version for item in prompt_schema_versions
        },
        output_schema_versions={
            item.schema_id: item.schema_version for item in prompt_schema_versions
        },
        provider=run.model_provider,
        model=run.model_name,
        model_revision=run.model_revision,
        generated_at=run.started_at,
    )


def _completed_result(
    *,
    run: ExperimentRun,
    brief: ResearchLearningBrief,
    objectives: Sequence[LearningObjectiveSpec],
    assessments: Sequence[AssessmentSpec],
    dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
    prerequisites: Sequence[PrerequisiteSpec],
    course_outline: CourseOutline,
    lessons: Sequence[LessonSpec],
    model_audits: Sequence[InferenceAuditMetadata],
    dependency_identities: Sequence[DependencyIdentity] = (),
) -> ExperimentRunResult:
    snapshot = build_research_snapshot(
        brief=brief,
        objectives=objectives,
        assessments=assessments,
        dependency_candidates=dependency_candidates,
        prerequisites=prerequisites,
        course_outline=course_outline,
        lessons=lessons,
        generation_provenance=_generation_provenance(run, brief),
        workload_validation=_workload_validation_for_run(
            run, brief=brief, assessments=assessments, lessons=lessons
        ),
        dependency_identities=dependency_identities,
    )
    return ExperimentRunResult(
        run=run,
        status=ExperimentRunStatus.COMPLETED,
        snapshot=snapshot,
        model_audits=list(model_audits),
        completed_at=datetime.now(UTC),
    )


def _failed_result(
    *,
    run: ExperimentRun,
    stage: str,
    error: Exception,
    partial: ExperimentPartialArtifacts,
    model_audits: Sequence[InferenceAuditMetadata],
) -> ExperimentRunResult:
    return ExperimentRunResult(
        run=run,
        status=ExperimentRunStatus.FAILED,
        partial_artifacts=partial,
        model_audits=list(model_audits),
        stage_failure=StageFailure(
            stage=stage,
            failure_class=type(error).__name__,
            validation_error=str(error)[:500] or None,
            retry_count=0,
        ),
        completed_at=datetime.now(UTC),
    )


def _model_audits(caller: object) -> Sequence[InferenceAuditMetadata]:
    if isinstance(caller, AuditedModelCaller):
        return caller.model_audits
    return ()


def _is_v03_structured_run(run: ExperimentRun) -> bool:
    return run.condition in {
        ExperimentCondition.STRUCTURED_V03,
        ExperimentCondition.STRUCTURED_V031,
    } or any(
        item.prompt_version.startswith("0.3")
        and item.prompt_id != ONE_SHOT_BASELINE_SCHEMA_ID
        for item in run.prompt_schema_versions
    )


def _workload_validation_for_run(
    run: ExperimentRun,
    *,
    brief: ResearchLearningBrief,
    assessments: Sequence[AssessmentSpec],
    lessons: Sequence[LessonSpec],
) -> WorkloadValidationResult | None:
    if not any(
        item.prompt_version == "0.3.2"
        and item.prompt_id != ONE_SHOT_BASELINE_SCHEMA_ID
        for item in run.prompt_schema_versions
    ) or brief.constraints.estimated_total_minutes is None:
        return None
    pattern_category = {
        InstructionalPattern.EXPLANATION: WorkloadCategory.INSTRUCTION,
        InstructionalPattern.DEMONSTRATION: WorkloadCategory.INSTRUCTION,
        InstructionalPattern.WORKED_EXAMPLE: WorkloadCategory.INSTRUCTION,
        InstructionalPattern.GUIDED_PRACTICE: WorkloadCategory.GUIDED_PRACTICE,
        InstructionalPattern.INDEPENDENT_PRACTICE: WorkloadCategory.INDEPENDENT_PRACTICE,
        InstructionalPattern.SCENARIO: WorkloadCategory.INDEPENDENT_PRACTICE,
        InstructionalPattern.REFLECTION: WorkloadCategory.INDEPENDENT_PRACTICE,
    }
    category_values: dict[WorkloadCategory, int | None] = {}

    def add(category: WorkloadCategory, minutes: int | None) -> None:
        if minutes is None or category in category_values and category_values[category] is None:
            category_values[category] = None
            return
        current = category_values.get(category, 0)
        assert current is not None
        category_values[category] = current + minutes

    for lesson in lessons:
        category = pattern_category[lesson.instructional_pattern]
        add(category, lesson.estimated_minutes)
    for assessment in assessments:
        category = (
            WorkloadCategory.SUMMATIVE_ASSESSMENT
            if assessment.effective_role is AssessmentRole.SUMMATIVE
            else WorkloadCategory.FORMATIVE_ASSESSMENT
        )
        add(category, assessment.estimated_minutes)
    return validate_workload_allocations(
        declared_total_minutes=brief.constraints.estimated_total_minutes,
        categories=category_values,
    )


def _validate_v03_references(
    *,
    objective_output: LearningObjectiveDesignOutput,
    assessment_output: AssessmentDesignOutput,
    prerequisite_output: PrerequisiteProposalOutput,
    course_output: CoursePlanningOutput,
    lesson_output: LessonPlanningOutput,
    brief: ResearchLearningBrief,
) -> None:
    """Fail closed on unknown cross-stage references; never guess or repair IDs."""

    objective_ids = {item.id for item in objective_output.objectives}
    if len(objective_ids) != len(objective_output.objectives):
        raise ValueError("v0.3 objective IDs must be unique")
    if any(item.brief_id != brief.id for item in objective_output.objectives):
        raise ValueError("v0.3 objective brief references must be supplied brief")
    if not set(assessment_output.objective_ids).issubset(objective_ids):
        raise ValueError("v0.3 assessment output contains an unknown objective reference")
    if any(
        not set(item.objective_ids).issubset(objective_ids)
        for item in assessment_output.assessments
    ):
        raise ValueError("v0.3 assessment contains an unknown objective reference")
    assessment_ids = {item.id for item in assessment_output.assessments}
    artifact_ids = objective_ids | assessment_ids
    for assessment in assessment_output.assessments:
        legacy_capabilities = set(assessment.required_capability_refs)
        typed_capabilities = {item.capability for item in assessment.required_capabilities}
        if legacy_capabilities & artifact_ids or typed_capabilities & artifact_ids:
            raise ValueError("v0.3 assessment contains an artifact ID in capability requirement")
        if any(
            not set(item.objective_ids).issubset(set(assessment.objective_ids))
            for item in assessment.required_capabilities
        ):
            raise ValueError("v0.3 assessment capability requirement contains an unknown objective reference")
    if any(
        not set(item.required_for_refs).issubset(objective_ids | assessment_ids)
        for item in assessment_output.dependency_candidates
    ):
        raise ValueError("v0.3 assessment dependency candidate contains an unknown reference")

    prerequisite_ids = {item.id for item in prerequisite_output.prerequisites}
    if len(prerequisite_ids) != len(prerequisite_output.prerequisites):
        raise ValueError("v0.3 prerequisite IDs must be unique")
    allowed_requirement_refs = objective_ids | assessment_ids
    if any(
        not set(item.required_for_refs).issubset(allowed_requirement_refs)
        for item in prerequisite_output.prerequisites
    ):
        raise ValueError("v0.3 prerequisite required_for_refs contains an unknown reference")

    outline = course_output.course_outline
    if outline.brief_id != brief.id or not set(outline.objective_ids).issubset(objective_ids):
        raise ValueError("v0.3 course outline contains an unknown objective reference")
    if any(
        not set(module.objective_ids).issubset(objective_ids)
        for module in outline.modules
    ):
        raise ValueError("v0.3 course outline contains an unknown objective reference")
    if any(
        not set(module.prerequisite_refs).issubset(prerequisite_ids)
        for module in outline.modules
    ):
        raise ValueError("v0.3 course outline contains an unknown prerequisite reference")
    if not set(outline.prerequisite_refs).issubset(prerequisite_ids):
        raise ValueError("v0.3 course outline contains an unknown prerequisite reference")
    declared_module_minutes = sum(
        module.estimated_minutes or 0 for module in outline.modules
    )
    if (
        outline.estimated_minutes is not None
        and declared_module_minutes > outline.estimated_minutes
        and not any(
            warning.type.value == "scope_time_conflict"
            and warning.decision.value == "prioritized_core_objectives"
            for warning in outline.planning_warnings
        )
    ):
        raise ValueError("v0.3 course outline requires a scope_time_conflict planning warning")

    module_ids = {module.id for module in outline.modules}
    module_objective_scope = build_module_objective_scope(
        outline,
        objective_ids=list(objective_ids),
    )
    assessment_by_id = {item.id: item for item in assessment_output.assessments}
    for lesson in lesson_output.lessons:
        if lesson.module_id not in module_ids:
            raise ValueError("v0.3 lesson contains an unknown module reference")
        if not set(lesson.objective_ids).issubset(objective_ids):
            raise ValueError("v0.3 lesson contains an unknown objective reference")
        try:
            validate_lesson_objective_scope(
                module_objective_ids=module_objective_scope[lesson.module_id],
                lesson_objective_ids=lesson.objective_ids,
            )
        except ValueError as error:
            raise ValueError("v0.3 lesson contains an objective outside its module") from error
        if not set(lesson.prerequisite_refs).issubset(prerequisite_ids):
            raise ValueError("v0.3 lesson contains an unknown prerequisite reference")
        if not set(lesson.formative_assessment_ids).issubset(assessment_ids):
            raise ValueError("v0.3 lesson contains an unknown assessment reference")
        if any(
            assessment_by_id[item_id].effective_role.value != "formative"
            for item_id in lesson.formative_assessment_ids
        ):
            raise ValueError("v0.3 lesson contains a non-formative assessment reference")


async def execute_one_shot_run(
    *,
    run: ExperimentRun,
    brief: ResearchLearningBrief,
    generator: OneShotInstructionalDesignGenerator,
) -> ExperimentRunResult:
    """Map baseline output to the same snapshot/gate; it has no condition exemption."""

    if run.condition is not ExperimentCondition.ONE_SHOT:
        raise ValueError("one-shot execution requires one_shot experiment condition")
    try:
        output = await generator.generate(brief)
        if output.course_outline is None:
            raise ValueError("one-shot output requires a course outline")
        return _completed_result(
            run=run,
            brief=brief,
            objectives=output.objectives,
            assessments=output.assessments,
            prerequisites=output.prerequisites,
            course_outline=output.course_outline,
            lessons=output.lessons,
            model_audits=_model_audits(generator),
        )
    except Exception as error:
        return _failed_result(
            run=run,
            stage="OneShotInstructionalDesignGenerator",
            error=error,
            partial=ExperimentPartialArtifacts(),
            model_audits=_model_audits(generator),
        )


async def execute_structured_run(
    *,
    run: ExperimentRun,
    brief: ResearchLearningBrief,
    designers: StructuredDesignerSet,
    dependency_identities: Sequence[DependencyIdentity] = (),
) -> ExperimentRunResult:
    """Stop at the first failed stage; never synthesize downstream fallback artifacts."""

    if run.condition not in {
        ExperimentCondition.STRUCTURED,
        ExperimentCondition.STRUCTURED_V03,
        ExperimentCondition.STRUCTURED_V031,
    }:
        raise ValueError("structured execution requires structured experiment condition")
    partial = ExperimentPartialArtifacts()
    try:
        objective_output = await designers.objective.propose(brief)
    except Exception as error:
        return _failed_result(
            run=run,
            stage="ObjectiveDesigner",
            error=error,
            partial=partial,
            model_audits=_model_audits(designers),
        )
    partial = partial.model_copy(update={"objectives": objective_output.objectives})

    try:
        assessment_output = await designers.assessment.propose(brief, objective_output.objectives)
    except Exception as error:
        return _failed_result(
            run=run,
            stage="AssessmentDesigner",
            error=error,
            partial=partial,
            model_audits=_model_audits(designers),
        )
    partial = partial.model_copy(
        update={
            "assessments": assessment_output.assessments,
            "dependency_candidates": assessment_output.dependency_candidates,
        }
    )

    try:
        prerequisite_output = await designers.prerequisite.propose(
            brief,
            objective_output.objectives,
            assessment_output.assessments,
            assessment_output.dependency_candidates,
        )
    except Exception as error:
        return _failed_result(
            run=run,
            stage="PrerequisiteProposer",
            error=error,
            partial=partial,
            model_audits=_model_audits(designers),
        )
    resolved_prerequisites = attach_prerequisite_dependency_provenance(
        prerequisite_output.prerequisites,
        assessment_output.dependency_candidates,
        dependency_identities=dependency_identities,
    )
    partial = partial.model_copy(update={"prerequisites": resolved_prerequisites})

    try:
        workload_context = (
            build_workload_budget_context(
                declared_total_minutes=brief.constraints.estimated_total_minutes,
                assessments={item.id: item.estimated_minutes for item in assessment_output.assessments},
            )
            if brief.constraints.estimated_total_minutes is not None
            else None
        )
        course_args = (
            brief,
            objective_output.objectives,
            assessment_output.assessments,
            resolved_prerequisites,
            assessment_output.dependency_candidates,
        )
        if _supports_workload_context(designers.course.propose):
            course_output = await designers.course.propose(
                *course_args, workload_context=workload_context
            )
        else:
            course_output = await designers.course.propose(*course_args)
    except Exception as error:
        return _failed_result(
            run=run,
            stage="CoursePlanner",
            error=error,
            partial=partial,
            model_audits=_model_audits(designers),
        )
    partial = partial.model_copy(update={"course_outline": course_output.course_outline})

    try:
        module_objective_scope = build_module_objective_scope(
            course_output.course_outline,
            objective_ids=[item.id for item in objective_output.objectives],
        )
    except Exception as error:
        return _failed_result(
            run=run,
            stage="OrchestrationReferenceResolution",
            error=error,
            partial=partial,
            model_audits=_model_audits(designers),
        )

    try:
        lesson_workload_context = (
            build_workload_budget_context(
                declared_total_minutes=brief.constraints.estimated_total_minutes,
                assessments={item.id: item.estimated_minutes for item in assessment_output.assessments},
                modules={item.id: item.estimated_minutes for item in course_output.course_outline.modules},
            )
            if brief.constraints.estimated_total_minutes is not None
            else None
        )
        lesson_args = (
            brief,
            objective_output.objectives,
            assessment_output.assessments,
            resolved_prerequisites,
            course_output.course_outline,
            assessment_output.dependency_candidates,
            module_objective_scope,
        )
        if _supports_workload_context(designers.lesson.propose):
            lesson_output = await designers.lesson.propose(
                *lesson_args, workload_context=lesson_workload_context
            )
        else:
            lesson_output = await designers.lesson.propose(*lesson_args)
    except Exception as error:
        return _failed_result(
            run=run,
            stage="LessonPlanner",
            error=error,
            partial=partial,
            model_audits=_model_audits(designers),
        )
    partial = partial.model_copy(update={"lessons": lesson_output.lessons})

    try:
        if _is_v03_structured_run(run):
            _validate_v03_references(
                objective_output=objective_output,
                assessment_output=assessment_output,
                prerequisite_output=prerequisite_output,
                course_output=course_output,
                lesson_output=lesson_output,
                brief=brief,
            )
        prerequisites = deduplicate_exact_prerequisites(partial.prerequisites)
        course_outline = attach_lesson_ids(course_output.course_outline, partial.lessons)
        return _completed_result(
            run=run,
            brief=brief,
            objectives=partial.objectives,
            assessments=partial.assessments,
            dependency_candidates=partial.dependency_candidates,
            prerequisites=prerequisites,
            course_outline=course_outline,
            lessons=partial.lessons,
            model_audits=_model_audits(designers),
            dependency_identities=dependency_identities,
        )
    except Exception as error:
        return _failed_result(
            run=run,
            stage="OrchestrationReferenceResolution",
            error=error,
            partial=partial,
            model_audits=_model_audits(designers),
        )


@dataclass
class FixtureOneShotInstructionalDesignGenerator:
    """No-cost fixture generator used only to verify experiment mechanics."""

    bundle: ResearchFixtureBundle
    received_brief_id: str | None = None

    async def generate(self, brief: ResearchLearningBrief) -> OneShotInstructionalDesignOutput:
        self.received_brief_id = brief.id
        if brief.id != self.bundle.brief.id:
            raise ValueError("fixture generator received an unexpected brief")
        return OneShotInstructionalDesignOutput(
            brief_id=brief.id,
            objectives=list(self.bundle.objectives),
            assessments=list(self.bundle.assessments),
            prerequisites=list(self.bundle.prerequisites),
            course_outline=self.bundle.course_outline,
            lessons=list(self.bundle.lessons),
        )


@dataclass
class FixtureStructuredDesigners:
    """No-cost staged fixture designer set; each method exposes only its stage output."""

    bundle: ResearchFixtureBundle
    received_brief_ids: list[str] = field(default_factory=list)

    async def propose(self, brief: ResearchLearningBrief) -> LearningObjectiveDesignOutput:
        self.received_brief_ids.append(brief.id)
        if brief.id != self.bundle.brief.id:
            raise ValueError("fixture designers received an unexpected brief")
        return LearningObjectiveDesignOutput(
            brief_id=brief.id, objectives=list(self.bundle.objectives)
        )

    @property
    def objective(self) -> ObjectiveDesigner:
        return self

    @property
    def assessment(self) -> AssessmentDesigner:
        return _FixtureAssessmentDesigner(self)

    @property
    def prerequisite(self) -> PrerequisiteProposer:
        return _FixturePrerequisiteProposer(self)

    @property
    def course(self) -> CoursePlanner:
        return _FixtureCoursePlanner(self)

    @property
    def lesson(self) -> LessonPlanner:
        return _FixtureLessonPlanner(self)


@dataclass(frozen=True)
class _FixtureAssessmentDesigner:
    owner: FixtureStructuredDesigners

    async def propose(
        self, brief: ResearchLearningBrief, objectives: Sequence[LearningObjectiveSpec]
    ) -> AssessmentDesignOutput:
        self.owner.received_brief_ids.append(brief.id)
        return AssessmentDesignOutput(
            objective_ids=[objective.id for objective in objectives],
            assessments=list(self.owner.bundle.assessments),
        )


@dataclass(frozen=True)
class _FixturePrerequisiteProposer:
    owner: FixtureStructuredDesigners

    async def propose(
        self,
        brief: ResearchLearningBrief,
        objectives: Sequence[LearningObjectiveSpec],
        assessments: Sequence[AssessmentSpec],
        dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
    ) -> PrerequisiteProposalOutput:
        self.owner.received_brief_ids.append(brief.id)
        return PrerequisiteProposalOutput(
            brief_id=brief.id, prerequisites=list(self.owner.bundle.prerequisites)
        )


@dataclass(frozen=True)
class _FixtureCoursePlanner:
    owner: FixtureStructuredDesigners

    async def propose(
        self,
        brief: ResearchLearningBrief,
        objectives: Sequence[LearningObjectiveSpec],
        assessments: Sequence[AssessmentSpec],
        prerequisites: Sequence[PrerequisiteSpec],
        dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
        workload_context: object | None = None,
    ) -> CoursePlanningOutput:
        self.owner.received_brief_ids.append(brief.id)
        return CoursePlanningOutput(
            brief_id=brief.id, course_outline=self.owner.bundle.course_outline
        )


@dataclass(frozen=True)
class _FixtureLessonPlanner:
    owner: FixtureStructuredDesigners

    async def propose(
        self,
        brief: ResearchLearningBrief,
        objectives: Sequence[LearningObjectiveSpec],
        assessments: Sequence[AssessmentSpec],
        prerequisites: Sequence[PrerequisiteSpec],
        course_outline: CourseOutline,
        dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
        module_objective_scope: Mapping[str, Sequence[str]] | None = None,
        workload_context: object | None = None,
    ) -> LessonPlanningOutput:
        self.owner.received_brief_ids.append(brief.id)
        return LessonPlanningOutput(
            course_id=course_outline.id, lessons=list(self.owner.bundle.lessons)
        )
