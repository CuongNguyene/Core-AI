from __future__ import annotations

from builtins import list as list_type
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol, cast

from sqlalchemy.exc import IntegrityError

from app.authorization.schemas import ActorContext, Role
from app.learning_authoring.service import (
    LearningAuthoringAccessDeniedError,
    LearningAuthoringNotFoundError,
)

from .brief_revision_schemas import AuthoringBriefRevision, BriefRevisionChanges
from .brief_revision_service import AuthoringBriefRevisionService
from .conversation_schemas import AuthoringConversationResponse
from .conversation_service import AuthoringConversationService
from .errors import (
    CourseAuthoringAccessDeniedError,
    CourseAuthoringReferenceNotFoundError,
    CourseAuthoringReferenceValidationError,
    CourseAuthoringRequestNotFoundError,
)
from .repository import CourseAuthoringRepository
from .schemas import (
    AudienceSnapshot,
    AudienceSnapshotSource,
    CourseAuthoringMode,
    CourseAuthoringRequest,
    CourseAuthoringRequestAccepted,
    CourseAuthoringRequestCreate,
    CourseAuthoringStatus,
)


class LearningDesignReferenceReader(Protocol):
    async def get_learning_need(self, artifact_id: str, actor: ActorContext) -> object: ...

    async def get_learning_objective(self, artifact_id: str, actor: ActorContext) -> object: ...

    async def get_instructional_blueprint(
        self, artifact_id: str, actor: ActorContext
    ) -> object: ...


class LearningObjectiveReference(Protocol):
    learning_need_ref: str


class InstructionalBlueprintReference(Protocol):
    objective_refs: list[str]
    learning_need_ref: str


class CourseAuthoringService:
    def __init__(
        self,
        *,
        repository: CourseAuthoringRepository,
        references: LearningDesignReferenceReader,
        brief_revisions: AuthoringBriefRevisionService | None = None,
        conversation: AuthoringConversationService | None = None,
    ) -> None:
        self._repository = repository
        self._references = references
        self._brief_revisions = brief_revisions
        self._conversation = conversation

    async def create(
        self,
        body: CourseAuthoringRequestCreate,
        actor: ActorContext,
        *,
        idempotency_key: str | None = None,
    ) -> CourseAuthoringRequestAccepted:
        if idempotency_key:
            existing = await self._repository.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return self._idempotent_acceptance(existing, body, actor)

        blueprint = await self._validate_references(body, actor)
        del blueprint

        audience_id, request_id = self._repository.allocate_ids()
        audience = AudienceSnapshot(
            id=audience_id,
            learner_refs=body.learner_refs,
            learner_count=len(body.learner_refs),
            captured_at=datetime.now(UTC),
            source=AudienceSnapshotSource.MANUAL_SELECTION,
        )
        request = CourseAuthoringRequest(
            id=request_id,
            title=body.title,
            training_brief=body.training_brief,
            audience_snapshot=audience,
            learning_need_refs=body.learning_need_refs,
            objective_refs=body.objective_refs,
            instructional_blueprint_ref=body.instructional_blueprint_ref,
            constraints=body.constraints,
            mode=body.mode,
            status=CourseAuthoringStatus.DRAFT,
            authoring_workflow_version=(
                "sep-08a-v1" if body.mode is CourseAuthoringMode.GOAL_DRIVEN else None
            ),
            created_by_actor_ref=actor.actor_id,
            created_at=audience.captured_at,
        )
        try:
            await self._repository.create(request, idempotency_key=idempotency_key)
        except IntegrityError:
            if not idempotency_key:
                raise
            existing = await self._repository.get_by_idempotency_key(idempotency_key)
            if existing is None:
                raise
            return self._idempotent_acceptance(existing, body, actor)
        if self._brief_revisions is not None and body.mode is CourseAuthoringMode.GOAL_DRIVEN:
            await self._brief_revisions.create_initial(request, actor)
        return CourseAuthoringRequestAccepted(
            request_id=request.id,
            status=request.status,
            audience_snapshot_id=audience.id,
        )

    @staticmethod
    def _idempotent_acceptance(
        existing: CourseAuthoringRequest,
        body: CourseAuthoringRequestCreate,
        actor: ActorContext,
    ) -> CourseAuthoringRequestAccepted:
        if existing.created_by_actor_ref != actor.actor_id:
            raise CourseAuthoringAccessDeniedError("course_authoring_access_denied")
        if not CourseAuthoringService._matches_idempotent_request(existing, body):
            raise ValueError("course_authoring_idempotency_conflict")
        return CourseAuthoringRequestAccepted(
            request_id=existing.id,
            status=existing.status,
            audience_snapshot_id=existing.audience_snapshot.id,
        )

    @staticmethod
    def _matches_idempotent_request(
        existing: CourseAuthoringRequest, body: CourseAuthoringRequestCreate
    ) -> bool:
        return (
            existing.title == body.title
            and existing.training_brief == body.training_brief
            and existing.audience_snapshot.learner_refs == body.learner_refs
            and existing.learning_need_refs == body.learning_need_refs
            and existing.objective_refs == body.objective_refs
            and existing.instructional_blueprint_ref == body.instructional_blueprint_ref
            and existing.constraints == body.constraints
            and existing.mode == body.mode
        )

    async def get(self, request_id: str, actor: ActorContext) -> CourseAuthoringRequest:
        request = await self._repository.get(request_id)
        if request is None:
            raise CourseAuthoringRequestNotFoundError("course_authoring_request_not_found")
        if request.created_by_actor_ref != actor.actor_id and Role.ADMIN not in actor.roles:
            raise CourseAuthoringAccessDeniedError("course_authoring_access_denied")
        return request

    async def list(self, actor: ActorContext) -> list[CourseAuthoringRequest]:
        requests = await self._repository.list()
        if Role.ADMIN in actor.roles:
            return requests
        return [request for request in requests if request.created_by_actor_ref == actor.actor_id]

    async def list_brief_revisions(
        self, request_id: str, actor: ActorContext
    ) -> list_type[AuthoringBriefRevision]:
        request = await self.get(request_id, actor)
        if self._brief_revisions is None or request.authoring_workflow_version != "sep-08a-v1":
            return []
        return await self._brief_revisions.list(request_id)

    async def conversation_respond(
        self, request_id: str, user_message: str, actor: ActorContext
    ) -> AuthoringConversationResponse:
        request = await self.get(request_id, actor)
        if self._brief_revisions is None or self._conversation is None:
            raise ValueError("authoring_conversation_not_required")
        revision = await self._brief_revisions.latest(request.id)
        if revision is None:
            raise ValueError("authoring_revision_not_found")
        return await self._conversation.respond(
            revision.payload,
            user_message,
            request_id=request.id,
        )

    async def clarify_brief(self, request_id: str, actor: ActorContext) -> AuthoringBriefRevision:
        request = await self.get(request_id, actor)
        if self._brief_revisions is None or request.authoring_workflow_version != "sep-08a-v1":
            raise ValueError("authoring_revision_not_required")
        return await self._brief_revisions.clarify(request.id, actor)

    async def create_brief_revision(
        self, request_id: str, changes: BriefRevisionChanges, actor: ActorContext
    ) -> AuthoringBriefRevision:
        request = await self.get(request_id, actor)
        if self._brief_revisions is None or request.authoring_workflow_version != "sep-08a-v1":
            raise ValueError("authoring_revision_not_required")
        return await self._brief_revisions.create_revision(request.id, changes, actor)

    async def confirm_brief(
        self, request_id: str, revision_id: str, actor: ActorContext
    ) -> AuthoringBriefRevision:
        request = await self.get(request_id, actor)
        if self._brief_revisions is None or request.authoring_workflow_version != "sep-08a-v1":
            raise ValueError("authoring_revision_not_required")
        return await self._brief_revisions.confirm(request.id, revision_id, actor)

    async def _validate_references(
        self, body: CourseAuthoringRequestCreate, actor: ActorContext
    ) -> object | None:
        blueprint: InstructionalBlueprintReference | None = None
        if body.instructional_blueprint_ref is not None:
            blueprint = cast(
                InstructionalBlueprintReference,
                await self._read_reference(
                    self._references.get_instructional_blueprint,
                    body.instructional_blueprint_ref,
                    actor,
                ),
            )

        objectives: list[LearningObjectiveReference] = []
        for objective_ref in body.objective_refs:
            objective = cast(
                LearningObjectiveReference,
                await self._read_reference(
                    self._references.get_learning_objective, objective_ref, actor
                ),
            )
            objectives.append(objective)
            if blueprint is not None and objective_ref not in blueprint.objective_refs:
                raise CourseAuthoringReferenceValidationError(
                    "objective_not_in_instructional_blueprint"
                )

        for learning_need_ref in body.learning_need_refs:
            await self._read_reference(self._references.get_learning_need, learning_need_ref, actor)

        if (
            blueprint is not None
            and body.learning_need_refs
            and blueprint.learning_need_ref not in body.learning_need_refs
        ):
            raise CourseAuthoringReferenceValidationError(
                "learning_need_not_in_instructional_blueprint"
            )

        if (
            body.learning_need_refs
            and objectives
            and any(
                objective.learning_need_ref not in body.learning_need_refs
                for objective in objectives
            )
        ):
            raise CourseAuthoringReferenceValidationError(
                "objective_learning_need_relationship_invalid"
            )
        return blueprint

    async def _read_reference(
        self,
        reader: Callable[[str, ActorContext], Awaitable[object]],
        artifact_id: str,
        actor: ActorContext,
    ) -> object:
        try:
            return await reader(artifact_id, actor)
        except LearningAuthoringAccessDeniedError as exc:
            raise CourseAuthoringAccessDeniedError("course_authoring_access_denied") from exc
        except (LearningAuthoringNotFoundError, KeyError, ValueError) as exc:
            raise CourseAuthoringReferenceNotFoundError(
                f"course_authoring_reference_not_found:{artifact_id}"
            ) from exc
