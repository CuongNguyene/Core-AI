from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from app.content_generation.prompts import (
    CURRICULUM_PLANNING_PROMPT_ID,
    CURRICULUM_PLANNING_PROMPT_VERSION,
    MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION,
)
from app.course_authoring.schemas import CourseAuthoringMode
from app.model_gateway.contracts import (
    DataClassification,
    InferenceAuditMetadata,
    InferencePurpose,
    InferenceRequest,
    ModelGateway,
    OutputContract,
)

from .microlearning import (
    MICROLEARNING_EFFORT_RANGES,
    MICROLEARNING_POLICY_VERSION,
    parse_expected_learning_effort_hours,
)
from .policy import CurriculumScopePolicy
from .schemas import (
    CurriculumLessonPlan,
    CurriculumModulePlan,
    CurriculumObjective,
    CurriculumPlan,
    CurriculumPlanningContext,
    CurriculumPlanningOutput,
    CurriculumPlanValidationIssue,
    CurriculumPlanValidationReport,
)
from .validation import (
    CurriculumPlanValidationError,
    collect_curriculum_plan_validation,
    validate_curriculum_plan,
)
from .workload import (
    ROUNDING_INCREMENT_MINUTES,
    UnsupportedLessonTypeError,
    allocate_curriculum_plan_workload,
    representable_effort_range,
)


class CurriculumPlanner(Protocol):
    async def plan(self, context: CurriculumPlanningContext) -> CurriculumPlan: ...


class CurriculumPlanningCandidateValidationError(CurriculumPlanValidationError):
    def __init__(
        self,
        *,
        candidate_plan: CurriculumPlan,
        report: CurriculumPlanValidationReport,
        audit: InferenceAuditMetadata,
    ) -> None:
        super().__init__("curriculum_plan_invalid", report=report)
        self.candidate_plan = candidate_plan
        self.audit = audit


def _goal_objective(
    objective: CurriculumObjective, request_ref: str, sequence: int
) -> CurriculumObjective:
    return objective.model_copy(
        update={
            "id": f"goal-driven-objective:{request_ref}:{sequence:03d}",
            "sequence": sequence,
            "origin": "GOAL_DRIVEN_TRAINING_BRIEF",
        }
    )


def _remap_objective_refs(
    refs: Sequence[str], source: Sequence[str], target: Sequence[str]
) -> list[str]:
    mapping = dict(zip(source, target, strict=True))
    return [mapping.get(reference, reference) for reference in refs]


def _finalize_curriculum_plan(
    plan: CurriculumPlan,
    *,
    policy: CurriculumScopePolicy | None,
) -> CurriculumPlan:
    target_hours = parse_expected_learning_effort_hours(
        plan.planning_metadata.get("target_learning_effort_hours")
    )
    if (
        target_hours is None
        and plan.planning_metadata.get("planning_strategy") == MICROLEARNING_POLICY_VERSION
    ):
        target_hours = plan.estimated_total_learning_hours
    if (
        plan.planning_metadata.get("planning_strategy") == MICROLEARNING_POLICY_VERSION
        and target_hours is not None
    ):
        envelope = representable_effort_range(plan)
        target_minutes = round(target_hours * 60)
        allowed_min_minutes = round(target_minutes * 0.8)
        allowed_max_minutes = round(target_minutes * 1.2)
        if (
            envelope.maximum_minutes < allowed_min_minutes
            or envelope.minimum_minutes > allowed_max_minutes
        ):
            report = collect_curriculum_plan_validation(plan, policy=policy)
            issue = CurriculumPlanValidationIssue(
                code="candidate_effort_not_representable",
                message=(
                    "The candidate structure cannot represent the target effort "
                    "under the current microlearning workload policy."
                ),
                path="estimated_total_learning_hours",
                actual={
                    "minimum_minutes": envelope.minimum_minutes,
                    "maximum_minutes": envelope.maximum_minutes,
                },
                expected={
                    "target_minutes": target_minutes,
                    "allowed_min_minutes": allowed_min_minutes,
                    "allowed_max_minutes": allowed_max_minutes,
                },
            )
            raise CurriculumPlanValidationError(
                "candidate_effort_not_representable",
                report=report.model_copy(
                    update={
                        "valid": False,
                        "issues": [issue, *report.issues],
                    }
                ),
            )
    try:
        allocated = allocate_curriculum_plan_workload(plan)
    except UnsupportedLessonTypeError:
        report = collect_curriculum_plan_validation(plan, policy=policy)
        raise CurriculumPlanValidationError(
            "unsupported_lesson_type",
            report=report,
        ) from None
    return validate_curriculum_plan(allocated, policy=policy)


@dataclass
class ModelGatewayCurriculumPlanner:
    gateway: ModelGateway
    requested_provider: str
    correlation_id: str
    output_token_budget: int | None = None
    temperature: float | None = None
    scope_policy: CurriculumScopePolicy = field(default_factory=CurriculumScopePolicy)
    _audits: list[InferenceAuditMetadata] = field(default_factory=list, init=False)

    @property
    def model_audits(self) -> Sequence[InferenceAuditMetadata]:
        return self._audits

    async def plan(self, context: CurriculumPlanningContext) -> CurriculumPlan:
        if context.mode is CourseAuthoringMode.GAP_DRIVEN:
            return DeterministicCurriculumPlanner(scope_policy=self.scope_policy).plan_gap(context)
        prompt_version = (
            MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION
            if context.planning_strategy == MICROLEARNING_POLICY_VERSION
            else CURRICULUM_PLANNING_PROMPT_VERSION
        )
        response = await self.gateway.infer_structured(
            InferenceRequest(
                purpose=InferencePurpose.CURRICULUM_PLANNING,
                data_classification=DataClassification.PUBLIC,
                prompt_template_id=CURRICULUM_PLANNING_PROMPT_ID,
                prompt_template_version=prompt_version,
                payload=self._planning_payload(context),
                output_contract=OutputContract(
                    schema_id=CURRICULUM_PLANNING_PROMPT_ID,
                    schema_version=prompt_version,
                ),
                requested_provider=self.requested_provider,
                temperature=self.temperature,
                output_token_budget=self.output_token_budget,
                correlation_id=self.correlation_id,
            ),
            CurriculumPlanningOutput,
        )
        self._audits.append(response.audit)
        return self._from_model_output(context, response.parsed, response.audit)

    def _planning_payload(self, context: CurriculumPlanningContext) -> dict[str, object]:
        bounds = self.scope_policy.bounds_for(context.duration, strategy=context.planning_strategy)
        payload = context.model_dump(mode="json")
        payload["estimated_total_learning_hours"] = (
            parse_expected_learning_effort_hours(context.expected_learning_effort)
            if context.planning_strategy == MICROLEARNING_POLICY_VERSION
            else context.duration.estimated_total_learning_hours
        )
        payload["required_scope"] = {
            "modules": {
                "min": bounds.minimum_modules,
                "max": bounds.maximum_modules,
            },
            "lessons": {
                "min": bounds.minimum_lessons,
                "max": bounds.maximum_lessons,
            },
        }
        if context.planning_strategy == MICROLEARNING_POLICY_VERSION:
            payload["workload_policy"] = {
                category.value.lower(): {
                    "minimum_minutes": item.minimum_minutes,
                    "maximum_minutes": (item.maximum_minutes // ROUNDING_INCREMENT_MINUTES)
                    * ROUNDING_INCREMENT_MINUTES,
                }
                for category, item in MICROLEARNING_EFFORT_RANGES.items()
            }
            payload["target_learning_effort_minutes"] = (
                round(target_hours * 60)
                if (
                    target_hours := parse_expected_learning_effort_hours(
                        context.expected_learning_effort
                    )
                )
                is not None
                else None
            )
            payload["representability_guidance"] = (
                "Generate enough units and a category mix so the target effort is "
                "representable within the supplied workload policy before allocation."
            )
        return payload

    def _from_model_output(
        self,
        context: CurriculumPlanningContext,
        output: CurriculumPlanningOutput,
        audit: InferenceAuditMetadata,
    ) -> CurriculumPlan:
        objectives = [
            CurriculumObjective(
                id=f"goal-driven-objective:{context.authoring_request_ref}:{item.sequence:03d}",
                statement=item.statement,
                measurable_outcome=item.measurable_outcome,
                sequence=item.sequence,
                origin="GOAL_DRIVEN_TRAINING_BRIEF",
            )
            for item in sorted(output.objectives, key=lambda item: item.sequence)
        ]
        source_ids = [
            f"objective-{item.sequence}"
            for item in sorted(output.objectives, key=lambda item: item.sequence)
        ]
        target_ids = [item.id for item in objectives]
        modules = [
            CurriculumModulePlan(
                id=f"curriculum-module:{context.authoring_request_ref}:{item.order:03d}",
                title=item.title,
                order=item.order,
                objective_refs=_remap_objective_refs(item.objective_refs, source_ids, target_ids),
                estimated_hours=item.estimated_hours,
                lessons=[
                    CurriculumLessonPlan(
                        id=f"curriculum-lesson:{context.authoring_request_ref}:{item.order:03d}:{lesson.order:03d}",
                        title=lesson.title,
                        order=lesson.order,
                        objective_refs=_remap_objective_refs(
                            lesson.objective_refs, source_ids, target_ids
                        ),
                        estimated_minutes=lesson.estimated_minutes,
                        lesson_type=lesson.lesson_type,
                    )
                    for lesson in item.lessons
                ],
            )
            for item in output.modules
        ]
        target_hours = parse_expected_learning_effort_hours(context.expected_learning_effort)
        plan = CurriculumPlan(
            id=f"curriculum-plan:{uuid4().hex}",
            authoring_request_ref=context.authoring_request_ref,
            version=1,
            course_title=context.course_title,
            course_description=context.training_goal,
            normalized_duration=context.duration,
            learning_objectives=objectives,
            modules=modules,
            estimated_total_learning_hours=(
                target_hours
                if context.planning_strategy == MICROLEARNING_POLICY_VERSION
                and target_hours is not None
                else context.duration.estimated_total_learning_hours
                or output.estimated_total_learning_hours
            ),
            planning_metadata={
                "prompt_version": (
                    MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION
                    if context.planning_strategy == MICROLEARNING_POLICY_VERSION
                    else CURRICULUM_PLANNING_PROMPT_VERSION
                ),
                "planning_strategy": context.planning_strategy,
                "microlearning_policy_version": (
                    MICROLEARNING_POLICY_VERSION
                    if context.planning_strategy == MICROLEARNING_POLICY_VERSION
                    else "legacy"
                ),
                "learning_horizon": context.learning_horizon or "",
                "target_learning_effort_hours": str(
                    f"{target_hours} hours" if target_hours is not None else ""
                ),
                "target_learning_effort_minutes": str(
                    round(target_hours * 60) if target_hours is not None else ""
                ),
                "weekly_effort_source": context.duration.weekly_effort_source.value,
            },
        )
        try:
            return _finalize_curriculum_plan(plan, policy=self.scope_policy)
        except CurriculumPlanValidationError as exc:
            raise CurriculumPlanningCandidateValidationError(
                candidate_plan=plan,
                report=exc.report,
                audit=audit,
            ) from exc


@dataclass
class DeterministicCurriculumPlanner:
    scope_policy: CurriculumScopePolicy = field(default_factory=CurriculumScopePolicy)

    async def plan(self, context: CurriculumPlanningContext) -> CurriculumPlan:
        if context.mode is CourseAuthoringMode.GAP_DRIVEN:
            return self.plan_gap(context)
        return self.plan_goal(context)

    def plan_gap(self, context: CurriculumPlanningContext) -> CurriculumPlan:
        objectives = list(context.existing_learning_objectives)
        if context.instructional_blueprint is not None:
            objective_ids = {item.id for item in objectives}
            blueprint_modules: list[CurriculumModulePlan] = []
            for module in sorted(
                context.instructional_blueprint.modules,
                key=lambda item: getattr(item, "sequence", getattr(item, "order", 1)),
            ):
                module_order = getattr(module, "sequence", getattr(module, "order", 1))
                selected = [
                    lesson
                    for lesson in context.instructional_blueprint.lessons
                    if lesson.id in module.lesson_refs
                ]
                lessons = [
                    CurriculumLessonPlan(
                        id=lesson.id,
                        title=lesson.title,
                        order=index,
                        objective_refs=[
                            ref for ref in lesson.objective_refs if ref in objective_ids
                        ],
                        estimated_minutes=lesson.estimated_minutes,
                        lesson_type=lesson.lesson_type.value,
                    )
                    for index, lesson in enumerate(selected, start=1)
                ]
                if lessons:
                    blueprint_modules.append(
                        CurriculumModulePlan(
                            id=module.id,
                            title=module.title,
                            order=module_order,
                            objective_refs=sorted(
                                {ref for lesson in lessons for ref in lesson.objective_refs}
                            ),
                            estimated_hours=sum(lesson.estimated_minutes for lesson in lessons)
                            / 60,
                            lessons=lessons,
                        )
                    )
            plan = self._make_plan(
                context,
                objectives,
                blueprint_modules,
                sum(module.estimated_hours for module in blueprint_modules),
            )
            return _finalize_curriculum_plan(plan, policy=None)
        modules: list[CurriculumModulePlan] = []
        lesson_number = 0
        for index, objective in enumerate(objectives, start=1):
            lesson_number += 1
            modules.append(
                CurriculumModulePlan(
                    id=f"curriculum-module:{context.authoring_request_ref}:{index:03d}",
                    title=f"Apply {objective.statement}",
                    order=index,
                    objective_refs=[objective.id],
                    estimated_hours=1.0,
                    lessons=[
                        CurriculumLessonPlan(
                            id=f"curriculum-lesson:{context.authoring_request_ref}:{index:03d}:001",
                            title=objective.statement,
                            order=1,
                            objective_refs=[objective.id],
                            estimated_minutes=60,
                            lesson_type="skill_practice",
                        )
                    ],
                )
            )
        plan = self._make_plan(context, objectives, modules, 1.0 * lesson_number)
        return _finalize_curriculum_plan(plan, policy=None)

    def plan_goal(self, context: CurriculumPlanningContext) -> CurriculumPlan:
        goal = context.training_goal
        statements = [
            (
                f"Explain the foundations required for {goal}",
                f"Describe the foundational concepts of {goal} and when to use them.",
            ),
            (
                f"Apply {goal} in realistic workflows",
                f"Complete a realistic workflow for {goal} and produce the expected deliverable.",
            ),
            (
                f"Integrate {goal} into an end-to-end solution",
                f"Build an integrated solution for {goal} that satisfies stated constraints.",
            ),
            (
                f"Evaluate and improve outcomes for {goal}",
                f"Evaluate a {goal} solution against criteria and implement an improvement.",
            ),
        ]
        objectives = [
            CurriculumObjective(
                id=f"goal-driven-objective:{context.authoring_request_ref}:{index:03d}",
                statement=statement,
                measurable_outcome=outcome,
                sequence=index,
                origin="GOAL_DRIVEN_TRAINING_BRIEF",
            )
            for index, (statement, outcome) in enumerate(statements, start=1)
        ]
        bounds = self.scope_policy.bounds_for(context.duration)
        module_count = min(max(bounds.minimum_modules, 1), bounds.maximum_modules)
        lesson_count = min(max(bounds.minimum_lessons, module_count), bounds.maximum_lessons)
        modules = []
        for module_order in range(1, module_count + 1):
            start = ((module_order - 1) * len(objectives)) // module_count
            end = (module_order * len(objectives)) // module_count
            assigned = objectives[start:end] or [objectives[(module_order - 1) % len(objectives)]]
            base_lessons = lesson_count // module_count
            remainder = lesson_count % module_count
            lesson_count_for_module = base_lessons + (1 if module_order <= remainder else 0)
            modules.append(
                CurriculumModulePlan(
                    id=f"curriculum-module:{context.authoring_request_ref}:{module_order:03d}",
                    title=f"{assigned[0].statement.split(' for ')[0]}",
                    order=module_order,
                    objective_refs=[item.id for item in assigned],
                    estimated_hours=lesson_count_for_module,
                    lessons=[
                        CurriculumLessonPlan(
                            id=f"curriculum-lesson:{context.authoring_request_ref}:{module_order:03d}:{lesson_order:03d}",
                            title=f"{assigned[(lesson_order - 1) % len(assigned)].statement}",
                            order=lesson_order,
                            objective_refs=[item.id for item in assigned],
                            estimated_minutes=60,
                            lesson_type="skill_practice",
                        )
                        for lesson_order in range(1, lesson_count_for_module + 1)
                    ],
                )
            )
        total_hours = context.duration.estimated_total_learning_hours or float(
            sum(len(item.lessons) for item in modules)
        )
        plan = self._make_plan(context, objectives, modules, total_hours)
        return _finalize_curriculum_plan(plan, policy=self.scope_policy)

    @staticmethod
    def _make_plan(
        context: CurriculumPlanningContext,
        objectives: list[CurriculumObjective],
        modules: list[CurriculumModulePlan],
        total_hours: float,
    ) -> CurriculumPlan:
        return CurriculumPlan(
            id=f"curriculum-plan:{uuid4().hex}",
            authoring_request_ref=context.authoring_request_ref,
            version=1,
            course_title=context.course_title,
            course_description=context.training_goal,
            normalized_duration=context.duration,
            learning_objectives=objectives,
            modules=modules,
            estimated_total_learning_hours=total_hours,
            planning_metadata={"policy_version": "sep-02.3-v1"},
        )
