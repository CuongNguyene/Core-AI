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
from app.course_generation.errors import CourseGenerationArtifactNotFoundError
from app.course_generation.hierarchical_service import require_confirmed_curriculum_for_generation
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
from app.integration.course_authoring_schemas import CurriculumPlanV1

ACTOR = ActorContext(
    actor_id=UUID("11111111-1111-1111-1111-111111111111"),
    organization_id=UUID("22222222-2222-2222-2222-222222222222"),
    roles=frozenset({Role.SME}),
)


def plan() -> CurriculumPlan:
    objective = CurriculumObjective(
        id="objective-1",
        statement="Build API testing capability",
        measurable_outcome="Create API tests",
        sequence=1,
        origin="GOAL_DRIVEN_TRAINING_BRIEF",
    )
    return CurriculumPlan(
        id="curriculum-plan:v1",
        authoring_request_ref="request-1",
        version=1,
        course_title="Backend course",
        course_description="Learn backend testing",
        normalized_duration=normalize_training_duration(None),
        learning_objectives=[objective],
        modules=[CurriculumModulePlan(
            id="module-1",
            title="API testing",
            order=1,
            objective_refs=[objective.id],
            estimated_hours=2,
            lessons=[
                CurriculumLessonPlan(
                    id="lesson-1", title="Test foundations", order=1,
                    objective_refs=[objective.id], estimated_minutes=15,
                    lesson_type="foundation", workload_category=LessonWorkloadCategory.FOUNDATION,
                    estimated_instruction_minutes=9, estimated_practice_minutes=6,
                    estimated_total_effort_minutes=15,
                ),
                CurriculumLessonPlan(
                    id="lesson-2", title="API test practice", order=2,
                    objective_refs=[objective.id], estimated_minutes=30,
                    lesson_type="practice", workload_category=LessonWorkloadCategory.PRACTICE,
                    estimated_instruction_minutes=8, estimated_practice_minutes=22,
                    estimated_total_effort_minutes=30,
                ),
                CurriculumLessonPlan(
                    id="lesson-3", title="Backend capstone", order=3,
                    objective_refs=[objective.id], estimated_minutes=75,
                    lesson_type="capstone", workload_category=LessonWorkloadCategory.CAPSTONE,
                    estimated_instruction_minutes=11, estimated_practice_minutes=64,
                    estimated_total_effort_minutes=75,
                ),
            ],
        )],
        estimated_total_learning_hours=2,
        planning_metadata={
            "planning_strategy": "sep-08b-v1",
            "curriculum_review_workflow_version": CURRICULUM_REVIEW_WORKFLOW_VERSION,
            "authoring_brief_revision_ref": "brief-1",
        },
        status=CurriculumPlanStatus.READY_FOR_REVIEW,
    )


@pytest.mark.asyncio
async def test_revision_creates_immutable_next_version_and_confirmation_requires_latest() -> None:
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
    await plans.create_curriculum_plan(plan())
    service = CurriculumRevisionService(repository=plans, brief_revisions=briefs)

    revised = await service.revise("curriculum-plan:v1", [{
        "op": "UPDATE_UNIT_EFFORT", "target_ref": "lesson-2",
        "fields": {"estimated_minutes": 45},
    }, {
        "op": "UPDATE_UNIT_EFFORT", "target_ref": "lesson-3",
        "fields": {"estimated_minutes": 60},
    }], "Increase testing practice", ACTOR)

    assert revised.version == 2
    assert revised.supersedes_plan_ref == "curriculum-plan:v1"
    assert (await plans.get_curriculum_plan("curriculum-plan:v1")).modules[0].lessons[1].estimated_minutes == 30
    with pytest.raises(ValueError, match="curriculum_plan_not_latest"):
        await service.confirm("curriculum-plan:v1", ACTOR)
    confirmed = await service.confirm(revised.id, ACTOR)
    assert confirmed.status is CurriculumPlanStatus.CONFIRMED


@pytest.mark.asyncio
async def test_revision_rejects_unconfirmed_scope_expansion_without_persisting_v2() -> None:
    plans = InMemoryContentGenerationRepository()
    briefs = InMemoryAuthoringBriefRevisionRepository()
    await briefs.create(AuthoringBriefRevision(
        id="brief-1", request_id="request-1", version=1,
        status=AuthoringBriefRevisionStatus.CONFIRMED,
        payload=BriefRevisionPayload(training_goal="Build API testing capability"),
        confirmed_at=datetime.now(UTC), confirmed_by=ACTOR.actor_id,
        created_at=datetime.now(UTC), created_by=ACTOR.actor_id,
    ))
    await plans.create_curriculum_plan(plan())
    service = CurriculumRevisionService(repository=plans, brief_revisions=briefs)

    with pytest.raises(ValueError, match="SCOPE_EXPANSION_REQUIRES_BRIEF_REVISION"):
        await service.revise("curriculum-plan:v1", [{
            "op": "ADD_UNIT", "target_ref": "new",
            "fields": {"title": "Kubernetes deployment"},
        }], None, ACTOR)

    assert len(await plans.list_curriculum_plans("request-1")) == 1


def test_downstream_generation_requires_latest_confirmed_sep08d_plan() -> None:
    source = plan()
    with pytest.raises(CourseGenerationArtifactNotFoundError, match="curriculum_plan_not_confirmed"):
        require_confirmed_curriculum_for_generation(source)

    confirmed = source.model_copy(update={"status": CurriculumPlanStatus.CONFIRMED})
    require_confirmed_curriculum_for_generation(confirmed)

    legacy = source.model_copy(update={"planning_metadata": {}})
    require_confirmed_curriculum_for_generation(legacy)


def test_gap_driven_generation_requires_confirmation_even_without_legacy_marker() -> None:
    source = plan().model_copy(update={
        "learning_objectives": [
            plan().learning_objectives[0].model_copy(
                update={"origin": "CANONICAL_LEARNING_OBJECTIVE"}
            )
        ],
        "planning_metadata": {},
        "status": CurriculumPlanStatus.PLANNED,
    })

    with pytest.raises(CourseGenerationArtifactNotFoundError, match="curriculum_plan_not_confirmed"):
        require_confirmed_curriculum_for_generation(source, required=True)

    require_confirmed_curriculum_for_generation(
        source.model_copy(update={"status": CurriculumPlanStatus.CONFIRMED}),
        required=True,
    )


@pytest.mark.asyncio
async def test_gap_driven_plan_without_marker_enters_explicit_review_workflow() -> None:
    repository = InMemoryContentGenerationRepository()
    briefs = InMemoryAuthoringBriefRevisionRepository()
    source = plan().model_copy(update={
        "learning_objectives": [
            plan().learning_objectives[0].model_copy(
                update={"origin": "CANONICAL_LEARNING_OBJECTIVE"}
            )
        ],
        "planning_metadata": {},
        "status": CurriculumPlanStatus.PLANNED,
    })
    await repository.create_curriculum_plan(source)
    service = CurriculumRevisionService(repository=repository, brief_revisions=briefs)

    reviewed = await service.review(source.id)

    assert reviewed.status is CurriculumPlanStatus.READY_FOR_CONFIRMATION
    assert reviewed.planning_metadata["curriculum_review_workflow_version"] == "sep-08d-v1"


def test_legacy_gap_plan_projection_exposes_review_workflow_without_mutating_source() -> None:
    source = plan().model_copy(update={
        "learning_objectives": [
            plan().learning_objectives[0].model_copy(
                update={"origin": "CANONICAL_LEARNING_OBJECTIVE"}
            )
        ],
        "planning_metadata": {},
        "status": CurriculumPlanStatus.PLANNED,
    })

    projected = CurriculumPlanV1.from_domain(source)

    assert projected.status is CurriculumPlanStatus.READY_FOR_REVIEW
    assert projected.planning_metadata["curriculum_review_workflow_version"] == "sep-08d-v1"
    assert source.status is CurriculumPlanStatus.PLANNED
    assert source.planning_metadata == {}
