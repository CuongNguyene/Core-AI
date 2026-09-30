from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.authorization.schemas import ActorContext, Role
from app.course_authoring.brief_revision_repository import InMemoryAuthoringBriefRevisionRepository, latest_revision_statement
from app.course_authoring.brief_revision_schemas import (
    AuthoringBriefRevisionStatus,
    BriefRevisionChanges,
)
from app.course_authoring.brief_revision_service import AuthoringBriefRevisionService
from app.course_authoring.schemas import (
    AudienceSnapshot,
    AudienceSnapshotSource,
    CourseAuthoringMode,
    CourseAuthoringRequest,
    CourseAuthoringStatus,
    TrainingBrief,
)

ACTOR = ActorContext(
    actor_id=UUID("11111111-1111-1111-1111-111111111111"),
    organization_id=UUID("22222222-2222-2222-2222-222222222222"),
    roles=frozenset({Role.SME}),
)


def test_latest_revision_statement_is_bounded_to_one_highest_version() -> None:
    statement = latest_revision_statement('request-1')
    assert statement._limit_clause is not None
    assert statement._limit_clause.value == 1


def request(mode: CourseAuthoringMode = CourseAuthoringMode.GOAL_DRIVEN) -> CourseAuthoringRequest:
    return CourseAuthoringRequest(
        id="request-revision-001",
        title="Python onboarding",
        training_brief=TrainingBrief(
            goal="Improve Python backend delivery",
            duration_constraint="12 months",
        ),
        audience_snapshot=AudienceSnapshot(
            id="audience-001",
            learner_refs=("learner-1",),
            learner_count=1,
            captured_at=datetime.now(UTC),
            source=AudienceSnapshotSource.MANUAL_SELECTION,
        ),
        mode=mode,
        status=CourseAuthoringStatus.DRAFT,
        authoring_workflow_version="sep-08a-v1" if mode is CourseAuthoringMode.GOAL_DRIVEN else None,
        created_by_actor_ref=ACTOR.actor_id,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_initial_revision_copies_explicit_fields_without_inference() -> None:
    service = AuthoringBriefRevisionService(InMemoryAuthoringBriefRevisionRepository())
    revision = await service.create_initial(request(), ACTOR)

    assert revision.version == 1
    assert revision.status is AuthoringBriefRevisionStatus.DRAFT
    assert revision.payload.training_goal == "Improve Python backend delivery"
    assert revision.payload.prerequisites == ()
    assert revision.payload.learning_horizon is None
    assert revision.payload.expected_learning_effort is None


@pytest.mark.asyncio
async def test_clarification_flags_ambiguous_legacy_duration() -> None:
    service = AuthoringBriefRevisionService(InMemoryAuthoringBriefRevisionRepository())
    await service.create_initial(request(), ACTOR)

    revision = await service.clarify(request().id, ACTOR)

    assert revision.status is AuthoringBriefRevisionStatus.NEEDS_CLARIFICATION
    assert "duration_semantics_ambiguous" in revision.clarification.issue_codes
    assert "desired_outcome_missing" in revision.clarification.issue_codes


@pytest.mark.asyncio
async def test_feedback_creates_immutable_v2_and_confirmation_requires_latest() -> None:
    repository = InMemoryAuthoringBriefRevisionRepository()
    service = AuthoringBriefRevisionService(repository)
    first = await service.create_initial(request(), ACTOR)
    await service.clarify(request().id, ACTOR)
    second = await service.create_revision(
        request().id,
        BriefRevisionChanges(
            desired_outcomes=("Deliver a tested backend service",),
            learning_horizon="12 months",
            expected_learning_effort="48 hours",
        ),
        ACTOR,
    )

    assert first.version == 1
    assert second.version == 2
    assert second.supersedes_revision_id == first.id
    assert (await repository.get(first.id)).payload.desired_outcomes == ()

    with pytest.raises(ValueError, match="revision_not_latest"):
        await service.confirm(first.request_id, first.id, ACTOR)

    confirmed = await service.confirm(second.request_id, second.id, ACTOR)
    assert confirmed.status is AuthoringBriefRevisionStatus.CONFIRMED


@pytest.mark.asyncio
async def test_confirmation_rejects_unresolved_required_clarification() -> None:
    service = AuthoringBriefRevisionService(InMemoryAuthoringBriefRevisionRepository())
    revision = await service.create_initial(request(), ACTOR)
    await service.clarify(request().id, ACTOR)

    with pytest.raises(ValueError, match="required_clarification_unresolved"):
        await service.confirm(request().id, revision.id, ACTOR)
