import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.authorization.schemas import ActorContext, Role
from app.content_generation.repository import InMemoryContentGenerationRepository
from app.course_authoring.brief_revision_repository import InMemoryAuthoringBriefRevisionRepository
from app.course_authoring.brief_revision_schemas import (
    AuthoringBriefRevision,
    AuthoringBriefRevisionStatus,
    BriefRevisionPayload,
)
from app.curriculum_planning.duration import normalize_training_duration
from app.curriculum_planning.revision import CURRICULUM_REVIEW_WORKFLOW_VERSION
from app.curriculum_planning.revision_service import CurriculumRevisionService
from app.curriculum_planning.schemas import (
    CurriculumLessonPlan,
    CurriculumModulePlan,
    CurriculumObjective,
    CurriculumPlan,
    CurriculumPlanStatus,
    LessonWorkloadCategory,
)

ACTOR = ActorContext(
    actor_id=UUID("11111111-1111-1111-1111-111111111111"),
    organization_id=UUID("22222222-2222-2222-2222-222222222222"),
    roles=frozenset({Role.SME}),
)


async def service() -> tuple[CurriculumRevisionService, InMemoryContentGenerationRepository]:
    plans = InMemoryContentGenerationRepository()
    briefs = InMemoryAuthoringBriefRevisionRepository()
    await briefs.create(AuthoringBriefRevision(
        id="brief-1", request_id="request-1", version=1,
        status=AuthoringBriefRevisionStatus.CONFIRMED,
        payload=BriefRevisionPayload(
            training_goal="Build API testing capability",
            desired_outcomes=("Create API tests",),
        ),
        confirmed_at=datetime.now(UTC), confirmed_by=ACTOR.actor_id,
        created_at=datetime.now(UTC), created_by=ACTOR.actor_id,
    ))
    objective = CurriculumObjective(
        id="objective-1", statement="Build API testing capability",
        measurable_outcome="Create API tests", sequence=1,
        origin="GOAL_DRIVEN_TRAINING_BRIEF",
    )
    source = CurriculumPlan(
        id="curriculum-plan:v1", authoring_request_ref="request-1", version=1,
        course_title="Backend course", course_description="Learn backend testing",
        normalized_duration=normalize_training_duration(None),
        learning_objectives=[objective], estimated_total_learning_hours=2,
        planning_metadata={
            "planning_strategy": "sep-08b-v1",
            "curriculum_review_workflow_version": CURRICULUM_REVIEW_WORKFLOW_VERSION,
            "authoring_brief_revision_ref": "brief-1",
        }, status=CurriculumPlanStatus.READY_FOR_REVIEW,
        modules=[CurriculumModulePlan(
            id="module-1", title="API testing", order=1,
            objective_refs=[objective.id], estimated_hours=2,
            lessons=[CurriculumLessonPlan(
                id="lesson-1", title="Test foundations", order=1,
                objective_refs=[objective.id], estimated_minutes=15,
                lesson_type="foundation", workload_category=LessonWorkloadCategory.FOUNDATION,
                estimated_instruction_minutes=9, estimated_practice_minutes=6,
                estimated_total_effort_minutes=15,
            ), CurriculumLessonPlan(
                id="lesson-2", title="API test practice", order=2,
                objective_refs=[objective.id], estimated_minutes=30,
                lesson_type="practice", workload_category=LessonWorkloadCategory.PRACTICE,
                estimated_instruction_minutes=8, estimated_practice_minutes=22,
                estimated_total_effort_minutes=30,
            ), CurriculumLessonPlan(
                id="lesson-3", title="Backend capstone", order=3,
                objective_refs=[objective.id], estimated_minutes=75,
                lesson_type="capstone", workload_category=LessonWorkloadCategory.CAPSTONE,
                estimated_instruction_minutes=11, estimated_practice_minutes=64,
                estimated_total_effort_minutes=75,
            )],
        )],
    )
    await plans.create_curriculum_plan(source)
    return CurriculumRevisionService(repository=plans, brief_revisions=briefs), plans


def test_effort_feedback_returns_existing_operation_and_preview_without_mutation() -> None:
    async def run() -> None:
        revision_service, plans = await service()

        preview = await revision_service.adapt_curriculum_feedback(
            "curriculum-plan:v1",
            {"kind": "ADJUST_EFFORT", "target_ref": "lesson-2", "estimated_minutes": 45},
            ACTOR,
        )

        assert preview.operations == ({
            "op": "UPDATE_UNIT_EFFORT",
            "target_ref": "lesson-2",
            "fields": {"estimated_minutes": 45},
        },)
        assert preview.before["estimated_minutes"] == 30
        assert preview.after["estimated_minutes"] == 45
        assert len(await plans.list_curriculum_plans("request-1")) == 1
    asyncio.run(run())


def test_scope_expansion_escalates_without_mutating_plan() -> None:
    async def run() -> None:
        revision_service, plans = await service()

        with pytest.raises(ValueError, match="SCOPE_EXPANSION_REQUIRES_BRIEF_REVISION"):
            await revision_service.adapt_curriculum_feedback(
                "curriculum-plan:v1",
                {"kind": "ADD_UNIT", "target_ref": "new", "title": "Kubernetes deployment"},
                ACTOR,
            )

        assert len(await plans.list_curriculum_plans("request-1")) == 1
    asyncio.run(run())


def test_apply_curriculum_feedback_delegates_to_immutable_revision() -> None:
    async def run() -> None:
        revision_service, plans = await service()

        revised = await revision_service.apply_curriculum_feedback(
            "curriculum-plan:v1",
            {"kind": "ADJUST_EFFORT", "target_ref": "lesson-2", "estimated_minutes": 45},
            "Increase practice time",
            ACTOR,
        )

        assert revised.version == 2
        assert revised.status is CurriculumPlanStatus.READY_FOR_CONFIRMATION
        assert revised.supersedes_plan_ref == "curriculum-plan:v1"
        assert len(await plans.list_curriculum_plans("request-1")) == 2
    asyncio.run(run())
