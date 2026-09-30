from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.authorization.schemas import ActorContext
from app.content_generation.repository import ContentGenerationRepository
from app.course_authoring.brief_revision_repository import AuthoringBriefRevisionRepository
from app.course_generation.errors import CourseGenerationArtifactNotFoundError

from .revision import (
    CURRICULUM_REVIEW_WORKFLOW_VERSION,
    apply_curriculum_patch,
    validate_patch_scope,
    validate_revised_plan,
)
from .schemas import CurriculumPlan, CurriculumPlanStatus
from .validation import collect_curriculum_plan_validation


@dataclass(frozen=True)
class CurriculumConversationPreview:
    operations: tuple[dict[str, Any], ...]
    before: dict[str, Any]
    after: dict[str, Any]


class CurriculumRevisionService:
    def __init__(
        self,
        *,
        repository: ContentGenerationRepository,
        brief_revisions: AuthoringBriefRevisionRepository,
    ) -> None:
        self._repository = repository
        self._brief_revisions = brief_revisions

    async def list_for_request(self, request_id: str) -> list[CurriculumPlan]:
        return await self._repository.list_curriculum_plans(request_id)

    async def get(self, plan_id: str) -> CurriculumPlan:
        """Load a plan so the API layer can authorize its parent request."""
        return await self._require_plan(plan_id)

    async def adapt_curriculum_feedback(
        self,
        plan_id: str,
        feedback: dict[str, Any],
        _actor: ActorContext,
    ) -> CurriculumConversationPreview:
        """Translate bounded structured feedback into an SEP-08D preview.

        Conversation text is intentionally not parsed here. Any future AI adapter
        must produce this small structured shape before it reaches revision logic.
        """
        source = await self._require_latest(plan_id)
        self._require_workflow(source)
        await self._require_confirmed_brief(source)
        kind = feedback.get("kind")
        if kind == "ADD_UNIT":
            raise ValueError("SCOPE_EXPANSION_REQUIRES_BRIEF_REVISION")
        if kind != "ADJUST_EFFORT":
            raise ValueError("curriculum_revision_operation_not_supported")
        target_ref = feedback.get("target_ref")
        minutes = feedback.get("estimated_minutes")
        if not isinstance(target_ref, str) or not target_ref or not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0:
            raise ValueError("curriculum_revision_invalid")
        target = next(
            (lesson for module in source.modules for lesson in module.lessons if lesson.id == target_ref),
            None,
        )
        if target is None:
            raise ValueError("curriculum_revision_invalid")
        operation = {
            "op": "UPDATE_UNIT_EFFORT",
            "target_ref": target_ref,
            "fields": {"estimated_minutes": minutes},
        }
        candidate = apply_curriculum_patch(source, [operation])
        updated = next(
            lesson for module in candidate.modules for lesson in module.lessons if lesson.id == target_ref
        )
        return CurriculumConversationPreview(
            operations=(operation,),
            before={"estimated_minutes": target.estimated_minutes},
            after={"estimated_minutes": updated.estimated_minutes},
        )

    async def apply_curriculum_feedback(
        self,
        plan_id: str,
        feedback: dict[str, Any],
        rationale: str | None,
        actor: ActorContext,
    ) -> CurriculumPlan:
        preview = await self.adapt_curriculum_feedback(plan_id, feedback, actor)
        return await self.revise(plan_id, list(preview.operations), rationale, actor)

    async def review(self, plan_id: str) -> CurriculumPlan:
        plan = await self._require_plan(plan_id)
        self._require_workflow(plan)
        report = collect_curriculum_plan_validation(plan)
        status = (
            CurriculumPlanStatus.READY_FOR_CONFIRMATION
            if report.valid
            else CurriculumPlanStatus.NEEDS_REVISION
        )
        metadata = {
            **plan.planning_metadata,
            "curriculum_review_workflow_version": CURRICULUM_REVIEW_WORKFLOW_VERSION,
            "review_status": status.value,
            "review_issue_codes": ",".join(report.issue_codes),
        }
        return await self._repository.update_curriculum_plan(
            plan.model_copy(update={"status": status, "planning_metadata": metadata})
        )

    async def revise(
        self,
        plan_id: str,
        operations: list[dict[str, Any]],
        rationale: str | None,
        actor: ActorContext,
    ) -> CurriculumPlan:
        source = await self._require_latest(plan_id)
        self._require_workflow(source)
        brief_ref = source.planning_metadata.get("authoring_brief_revision_ref")
        if not brief_ref:
            raise ValueError("curriculum_revision_invalid")
        brief = await self._brief_revisions.get(brief_ref)
        if brief is None or brief.status.value != "CONFIRMED":
            raise ValueError("curriculum_revision_invalid")
        validate_patch_scope(operations, brief.payload)
        candidate = apply_curriculum_patch(source, operations)
        validate_revised_plan(candidate)
        metadata = {
            **candidate.planning_metadata,
            "curriculum_review_workflow_version": CURRICULUM_REVIEW_WORKFLOW_VERSION,
            "review_status": CurriculumPlanStatus.READY_FOR_CONFIRMATION.value,
            "revision_rationale": rationale or "",
            "revision_operation_count": str(len(operations)),
            "revision_created_by": str(actor.actor_id),
        }
        revised = candidate.model_copy(update={
            "id": f"curriculum-plan:{uuid4().hex}",
            "version": source.version + 1,
            "supersedes_plan_ref": source.id,
            "status": CurriculumPlanStatus.READY_FOR_CONFIRMATION,
            "planning_metadata": metadata,
        })
        return await self._repository.create_curriculum_plan(revised)

    async def _require_confirmed_brief(self, plan: CurriculumPlan) -> None:
        brief_ref = plan.planning_metadata.get("authoring_brief_revision_ref")
        brief = await self._brief_revisions.get(brief_ref) if brief_ref else None
        if brief is None or brief.status.value != "CONFIRMED":
            raise ValueError("curriculum_revision_invalid")

    async def confirm(self, plan_id: str, actor: ActorContext) -> CurriculumPlan:
        plan = await self._require_latest(plan_id)
        self._require_workflow(plan)
        if plan.status is not CurriculumPlanStatus.READY_FOR_CONFIRMATION:
            raise ValueError("curriculum_review_blocking_findings")
        metadata = {
            **plan.planning_metadata,
            "confirmed_at": datetime.now(UTC).isoformat(),
            "confirmed_by": str(actor.actor_id),
            "review_status": CurriculumPlanStatus.CONFIRMED.value,
        }
        return await self._repository.update_curriculum_plan(
            plan.model_copy(update={"status": CurriculumPlanStatus.CONFIRMED, "planning_metadata": metadata})
        )

    async def _require_plan(self, plan_id: str) -> CurriculumPlan:
        plan = await self._repository.get_curriculum_plan(plan_id)
        if plan is None:
            raise CourseGenerationArtifactNotFoundError("curriculum_plan_not_found")
        return plan

    async def _require_latest(self, plan_id: str) -> CurriculumPlan:
        plan = await self._require_plan(plan_id)
        plans = await self._repository.list_curriculum_plans(plan.authoring_request_ref)
        if not plans or plans[0].id != plan.id:
            raise ValueError("curriculum_plan_not_latest")
        return plan

    @staticmethod
    def _require_workflow(plan: CurriculumPlan) -> None:
        is_gap_driven_plan = any(
            objective.origin == "CANONICAL_LEARNING_OBJECTIVE"
            for objective in plan.learning_objectives
        )
        if (
            plan.planning_metadata.get("curriculum_review_workflow_version")
            != CURRICULUM_REVIEW_WORKFLOW_VERSION
            and not is_gap_driven_plan
        ):
            raise ValueError("curriculum_review_not_required")
