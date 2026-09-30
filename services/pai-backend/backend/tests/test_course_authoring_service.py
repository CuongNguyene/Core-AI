from types import SimpleNamespace
from uuid import UUID

import pytest

from app.authorization.schemas import ActorContext, Role
from app.course_authoring.errors import (
    CourseAuthoringAccessDeniedError,
    CourseAuthoringReferenceNotFoundError,
    CourseAuthoringReferenceValidationError,
    CourseAuthoringRequestNotFoundError,
)
from app.course_authoring.repository import InMemoryCourseAuthoringRepository
from app.course_authoring.schemas import (
    CourseAuthoringMode,
    CourseAuthoringRequestCreate,
    TrainingBrief,
)
from app.course_authoring.service import CourseAuthoringService

ACTOR_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
OTHER_ACTOR_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ORG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def actor(actor_id: UUID = ACTOR_ID) -> ActorContext:
    return ActorContext(
        actor_id=actor_id,
        organization_id=ORG_ID,
        roles=frozenset(),
    )


def goal_request() -> CourseAuthoringRequestCreate:
    return CourseAuthoringRequestCreate(
        title="Python onboarding",
        training_brief=TrainingBrief(goal="Improve Python data cleaning"),
        learner_refs=["lms-2", "lms-1"],
        mode=CourseAuthoringMode.GOAL_DRIVEN,
    )


def gap_request(**overrides: object) -> CourseAuthoringRequestCreate:
    values: dict[str, object] = {
        "title": "Close Python gap",
        "training_brief": TrainingBrief(goal="Close a Python skill gap"),
        "learner_refs": ["lms-1"],
        "objective_refs": ["objective-1"],
        "mode": CourseAuthoringMode.GAP_DRIVEN,
    }
    values.update(overrides)
    return CourseAuthoringRequestCreate.model_validate(values)


class ReferenceReader:
    def __init__(self) -> None:
        self.objectives = {
            "objective-1": SimpleNamespace(
                id="objective-1", learning_need_ref="learning-need-1"
            ),
            "objective-2": SimpleNamespace(
                id="objective-2", learning_need_ref="learning-need-2"
            ),
        }
        self.learning_needs = {
            "learning-need-1": SimpleNamespace(id="learning-need-1"),
            "learning-need-2": SimpleNamespace(id="learning-need-2"),
        }
        self.blueprints = {
            "blueprint-1": SimpleNamespace(
                id="blueprint-1",
                objective_refs=["objective-1"],
                learning_need_ref="learning-need-1",
            )
        }

    async def get_learning_need(self, artifact_id: str, actor: ActorContext) -> object:
        del actor
        try:
            return self.learning_needs[artifact_id]
        except KeyError as exc:
            raise KeyError(artifact_id) from exc

    async def get_learning_objective(self, artifact_id: str, actor: ActorContext) -> object:
        del actor
        try:
            return self.objectives[artifact_id]
        except KeyError as exc:
            raise KeyError(artifact_id) from exc

    async def get_instructional_blueprint(
        self, artifact_id: str, actor: ActorContext
    ) -> object:
        del actor
        try:
            return self.blueprints[artifact_id]
        except KeyError as exc:
            raise KeyError(artifact_id) from exc


class NotFoundReferenceReader(ReferenceReader):
    async def get_learning_objective(self, artifact_id: str, actor: ActorContext) -> object:
        del actor
        raise KeyError(artifact_id)


def service(reader: object | None = None) -> CourseAuthoringService:
    return CourseAuthoringService(
        repository=InMemoryCourseAuthoringRepository(),
        references=reader or ReferenceReader(),
    )


@pytest.mark.asyncio
async def test_create_goal_driven_request_persists_snapshot_and_actor() -> None:
    authoring = service()

    accepted = await authoring.create(goal_request(), actor())
    request = await authoring.get(accepted.request_id, actor())

    assert accepted.request_id == "course-authoring-request-001"
    assert accepted.audience_snapshot_id == "audience-snapshot-001"
    assert request.audience_snapshot.learner_refs == ("lms-2", "lms-1")
    assert request.audience_snapshot.learner_count == 2
    assert request.created_by_actor_ref == ACTOR_ID
    assert request.learning_need_refs == ()
    assert request.objective_refs == ()
    assert request.instructional_blueprint_ref is None


@pytest.mark.asyncio
async def test_create_is_idempotent_for_the_same_actor_and_payload() -> None:
    authoring = service()

    first = await authoring.create(goal_request(), actor(), idempotency_key="lms-request-001")
    replay = await authoring.create(goal_request(), actor(), idempotency_key="lms-request-001")

    assert replay.request_id == first.request_id
    assert len(await authoring._repository.list()) == 1


@pytest.mark.asyncio
async def test_create_rejects_idempotency_key_reused_with_different_payload() -> None:
    authoring = service()

    await authoring.create(goal_request(), actor(), idempotency_key="lms-request-001")
    with pytest.raises(ValueError, match="course_authoring_idempotency_conflict"):
        await authoring.create(
            goal_request().model_copy(update={"title": "Different course"}),
            actor(),
            idempotency_key="lms-request-001",
        )


@pytest.mark.asyncio
async def test_gap_driven_request_preserves_explicit_refs_without_inference() -> None:
    authoring = service()

    accepted = await authoring.create(
        gap_request(objective_refs=["objective-1"], learning_need_refs=[]), actor()
    )
    request = await authoring.get(accepted.request_id, actor())

    assert request.objective_refs == ("objective-1",)
    assert request.learning_need_refs == ()
    assert request.instructional_blueprint_ref is None


@pytest.mark.asyncio
async def test_unknown_supplied_reference_fails_closed() -> None:
    authoring = service(NotFoundReferenceReader())

    with pytest.raises(CourseAuthoringReferenceNotFoundError):
        await authoring.create(gap_request(objective_refs=["objective-missing"]), actor())


@pytest.mark.asyncio
async def test_blueprint_objective_membership_is_checked_without_inference() -> None:
    authoring = service()

    with pytest.raises(CourseAuthoringReferenceValidationError):
        await authoring.create(
            gap_request(
                instructional_blueprint_ref="blueprint-1",
                objective_refs=["objective-2"],
            ),
            actor(),
        )


@pytest.mark.asyncio
async def test_learning_need_relationship_is_checked_when_explicitly_supplied() -> None:
    authoring = service()

    with pytest.raises(CourseAuthoringReferenceValidationError):
        await authoring.create(
            gap_request(
                objective_refs=["objective-1"],
                learning_need_refs=["learning-need-2"],
            ),
            actor(),
        )


@pytest.mark.asyncio
async def test_unknown_request_and_non_creator_retrieval_fail_closed() -> None:
    authoring = service()
    accepted = await authoring.create(goal_request(), actor())

    with pytest.raises(CourseAuthoringRequestNotFoundError):
        await authoring.get("course-authoring-request-missing", actor())
    with pytest.raises(CourseAuthoringAccessDeniedError):
        await authoring.get(accepted.request_id, actor(OTHER_ACTOR_ID))


@pytest.mark.asyncio
async def test_admin_can_retrieve_a_manager_created_request() -> None:
    authoring = service()
    accepted = await authoring.create(goal_request(), actor())
    admin = actor(OTHER_ACTOR_ID).model_copy(update={"roles": frozenset({Role.ADMIN})})

    request = await authoring.get(accepted.request_id, admin)

    assert request.created_by_actor_ref == ACTOR_ID
