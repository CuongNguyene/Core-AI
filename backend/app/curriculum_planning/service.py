from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

import structlog

from app.authorization.schemas import ActorContext
from app.content_generation.repository import ContentGenerationRepository
from app.content_generation.schemas import (
    CurriculumPlanningAttempt,
    CurriculumPlanningAttemptStatus,
    GoalDerivedLearningObjective,
)
from app.course_authoring.brief_revision_repository import AuthoringBriefRevisionRepository
from app.course_authoring.brief_revision_schemas import BriefRevisionPayload
from app.course_authoring.schemas import CourseAuthoringMode, CourseAuthoringRequest
from app.course_generation.context import CourseGenerationContext, CourseGenerationContextBuilder
from app.course_generation.errors import CourseGenerationArtifactNotFoundError

from .duration import normalize_training_duration
from .planner import CurriculumPlanner, CurriculumPlanningCandidateValidationError
from .policy import CurriculumScopePolicy
from .revision import CURRICULUM_REVIEW_WORKFLOW_VERSION
from .schemas import (
    CurriculumObjective,
    CurriculumPlan,
    CurriculumPlanningContext,
    CurriculumPlanStatus,
    CurriculumPlanValidationReport,
)
from .validation import (
    CurriculumPlanValidationError,
    replay_curriculum_planning_attempt,
)

logger = structlog.get_logger(__name__)


class CurriculumAuthoringRequestReader(Protocol):
    async def get(self, request_id: str, actor: ActorContext) -> CourseAuthoringRequest: ...


def planning_context_from_generation_context(
    request: CourseAuthoringRequest,
    context: CourseGenerationContext,
) -> CurriculumPlanningContext:
    canonical = [
        CurriculumObjective(
            id=item.id,
            statement=item.statement,
            measurable_outcome=item.measurable_outcome,
            sequence=item.sequence,
            origin="CANONICAL_LEARNING_OBJECTIVE",
        )
        for item in context.learning_objectives
        if item.statement and item.measurable_outcome
    ]
    weekly_effort_raw = request.constraints.get("weekly_effort_hours")
    try:
        weekly_effort = float(weekly_effort_raw) if weekly_effort_raw else None
        if weekly_effort is not None and weekly_effort <= 0:
            weekly_effort = None
    except ValueError:
        weekly_effort = None
    return CurriculumPlanningContext(
        authoring_request_ref=request.id,
        mode=request.mode,
        course_title=request.title,
        training_goal=request.training_brief.goal,
        language=request.training_brief.language,
        audience_summary=context.audience_summary.model_dump(mode="json"),
        duration=normalize_training_duration(
            request.training_brief.duration_constraint,
            weekly_effort_hours=weekly_effort,
        ),
        target_completion_context=request.training_brief.target_completion_context,
        existing_learning_objectives=canonical if request.mode is CourseAuthoringMode.GAP_DRIVEN else [],
        learning_need_refs=list(context.learning_need_refs),
        instructional_blueprint_ref=request.instructional_blueprint_ref,
        instructional_blueprint=context.instructional_blueprint,
        learning_horizon=request.training_brief.learning_horizon,
        expected_learning_effort=request.training_brief.expected_learning_effort,
        planning_strategy=(
            "sep-08b-v1"
            if request.authoring_workflow_version == "sep-08a-v1"
            else "legacy"
        ),
    )


class CurriculumPlanningService:
    def __init__(
        self,
        *,
        authoring: CurriculumAuthoringRequestReader,
        context_builder: CourseGenerationContextBuilder,
        planner: CurriculumPlanner,
        repository: ContentGenerationRepository,
        scope_policy: CurriculumScopePolicy | None = None,
        brief_revisions: AuthoringBriefRevisionRepository | None = None,
    ) -> None:
        self._authoring = authoring
        self._context_builder = context_builder
        self._planner = planner
        self._repository = repository
        self._scope_policy = scope_policy or CurriculumScopePolicy()
        self._brief_revisions = brief_revisions

    async def plan(self, request_id: str, actor: ActorContext) -> CurriculumPlan:
        request = await self._authoring.get(request_id, actor)
        revision = None
        if request.authoring_workflow_version == "sep-08a-v1":
            if self._brief_revisions is None:
                raise ValueError("authoring_brief_not_confirmed")
            revision = await self._brief_revisions.latest(request.id)
            if revision is None or revision.status.value != "CONFIRMED":
                raise ValueError("authoring_brief_not_confirmed")
            request = self._request_from_confirmed_payload(request, revision.payload)
        context = await self._context_builder.build(request, actor)
        planning_context = planning_context_from_generation_context(request, context)
        try:
            plan = await self._planner.plan(planning_context)
        except CurriculumPlanningCandidateValidationError as exc:
            attempt = await self._persist_failed_attempt(
                request=request,
                context=planning_context,
                failure=exc,
            )
            logger.error(
                "curriculum_planning_validation_failed",
                request_ref=request.id,
                attempt_ref=attempt.id,
                correlation_id=attempt.correlation_id,
                provider=attempt.provider,
                model=attempt.model,
                prompt_version=attempt.prompt_version,
                duration=attempt.original_duration_constraint,
                total_hours=attempt.estimated_total_learning_hours,
                module_count=attempt.module_count,
                lesson_count=attempt.lesson_count,
                issue_codes=attempt.issue_codes,
            )
            raise CurriculumPlanValidationError(
                "curriculum_plan_invalid",
                report=exc.report,
            ) from exc
        previous = await self._repository.list_curriculum_plans(request.id)
        version = previous[0].version + 1 if previous else 1
        plan = plan.model_copy(update={
            "id": f"curriculum-plan:{uuid4().hex}",
            "version": version,
            "supersedes_plan_ref": previous[0].id if previous else None,
            "planning_metadata": {
                **plan.planning_metadata,
                **({"curriculum_review_workflow_version": CURRICULUM_REVIEW_WORKFLOW_VERSION,
                    "review_status": "READY_FOR_REVIEW"}
                    if request.mode is CourseAuthoringMode.GAP_DRIVEN
                    or request.authoring_workflow_version == "sep-08a-v1"
                    else {}),
                **({"authoring_brief_revision_ref": revision.id} if revision else {}),
            },
            "status": (
                CurriculumPlanStatus.READY_FOR_REVIEW
                if request.mode is CourseAuthoringMode.GAP_DRIVEN
                or request.authoring_workflow_version == "sep-08a-v1"
                else plan.status
            ),
        })
        return await self._repository.create_curriculum_plan(plan)

    @staticmethod
    def _request_from_confirmed_payload(
        request: CourseAuthoringRequest, payload: BriefRevisionPayload
    ) -> CourseAuthoringRequest:
        brief = request.training_brief.model_copy(update={
            "goal": payload.training_goal,
            "desired_outcomes": payload.desired_outcomes,
            "prerequisites": payload.prerequisites,
            "duration_constraint": payload.learning_horizon or request.training_brief.duration_constraint,
            "learning_horizon": payload.learning_horizon,
            "expected_learning_effort": payload.expected_learning_effort,
        })
        return request.model_copy(update={
            "training_brief": brief,
            "constraints": payload.constraints,
        })

    async def _persist_failed_attempt(
        self,
        *,
        request: CourseAuthoringRequest,
        context: CurriculumPlanningContext,
        failure: CurriculumPlanningCandidateValidationError,
    ) -> CurriculumPlanningAttempt:
        audit = failure.audit
        bounds = self._scope_policy.bounds_for(context.duration)
        now = datetime.now(UTC)
        attempt = CurriculumPlanningAttempt(
            id=f"curriculum-planning-attempt:{uuid4().hex}",
            authoring_request_ref=request.id,
            correlation_id=audit.correlation_id,
            provider=audit.provider,
            model=audit.model,
            prompt_id=audit.prompt_template_id,
            prompt_version=audit.prompt_template_version,
            created_at=now,
            completed_at=now,
            status=CurriculumPlanningAttemptStatus.FAILED,
            original_duration_constraint=request.training_brief.duration_constraint,
            normalized_duration=context.duration,
            weekly_effort_hours=context.duration.weekly_effort_hours,
            weekly_effort_source=context.duration.weekly_effort_source,
            estimated_total_learning_hours=context.duration.estimated_total_learning_hours,
            min_modules=bounds.minimum_modules,
            max_modules=bounds.maximum_modules,
            min_lessons=bounds.minimum_lessons,
            max_lessons=bounds.maximum_lessons,
            objective_count=failure.report.objective_count,
            module_count=failure.report.module_count,
            lesson_count=failure.report.lesson_count,
            estimated_candidate_hours=failure.report.estimated_total_hours,
            covered_objective_count=failure.report.covered_objective_count,
            validation_issues=failure.report.issues,
            uncovered_objective_refs=failure.report.uncovered_objective_refs,
            unknown_objective_refs=failure.report.unknown_objective_refs,
            sanitized_parsed_candidate=failure.candidate_plan.model_dump(mode="json"),
        )
        return await self._repository.create_curriculum_planning_attempt(attempt)

    async def get_latest(self, request_id: str) -> CurriculumPlan:
        plans = await self._repository.list_curriculum_plans(request_id)
        if not plans:
            raise CourseGenerationArtifactNotFoundError("curriculum_plan_not_found")
        return plans[0]

    async def get(self, plan_id: str) -> CurriculumPlan:
        plan = await self._repository.get_curriculum_plan(plan_id)
        if plan is None:
            raise CourseGenerationArtifactNotFoundError("curriculum_plan_not_found")
        return plan

    async def get_latest_attempt(self, request_id: str) -> CurriculumPlanningAttempt:
        attempts = await self._repository.list_curriculum_planning_attempts(request_id)
        if not attempts:
            raise CourseGenerationArtifactNotFoundError("curriculum_planning_attempt_not_found")
        return attempts[0]

    async def replay_attempt(self, attempt_id: str) -> CurriculumPlanValidationReport:
        attempt = await self._repository.get_curriculum_planning_attempt(attempt_id)
        if attempt is None:
            raise CourseGenerationArtifactNotFoundError("curriculum_planning_attempt_not_found")
        return replay_curriculum_planning_attempt(attempt, policy=self._scope_policy)

    @staticmethod
    def goal_objectives_for_context(plan: CurriculumPlan) -> list[GoalDerivedLearningObjective]:
        return [
            GoalDerivedLearningObjective(
                id=item.id,
                statement=item.statement,
                measurable_outcome=item.measurable_outcome,
                sequence=item.sequence,
                origin="GOAL_DRIVEN_TRAINING_BRIEF",
            )
            for item in plan.learning_objectives
            if item.origin == "GOAL_DRIVEN_TRAINING_BRIEF"
        ]
