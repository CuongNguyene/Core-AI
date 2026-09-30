from datetime import UTC, datetime
from uuid import uuid4

from app.authorization.schemas import ActorContext

from .brief_revision_repository import AuthoringBriefRevisionRepository
from .brief_revision_schemas import (
    AuthoringBriefRevision,
    AuthoringBriefRevisionStatus,
    BriefClarificationResult,
    BriefRevisionChanges,
    BriefRevisionPayload,
    ClarificationItem,
)
from .schemas import CourseAuthoringRequest


class AuthoringBriefRevisionService:
    def __init__(self, repository: AuthoringBriefRevisionRepository) -> None:
        self._repository = repository

    async def create_initial(
        self, request: CourseAuthoringRequest, actor: ActorContext
    ) -> AuthoringBriefRevision:
        if request.authoring_workflow_version != "sep-08a-v1":
            raise ValueError("authoring_revision_not_required")
        payload = BriefRevisionPayload(
            training_goal=request.training_brief.goal,
            audience_summary={
                "learner_count": request.audience_snapshot.learner_count,
                "source": request.audience_snapshot.source.value,
            },
            desired_outcomes=request.training_brief.desired_outcomes,
            prerequisites=request.training_brief.prerequisites,
            constraints=request.constraints,
            learning_horizon=request.training_brief.learning_horizon,
            expected_learning_effort=request.training_brief.expected_learning_effort,
            legacy_duration_constraint=request.training_brief.duration_constraint,
        )
        revision = AuthoringBriefRevision(
            id=f"authoring-brief-revision:{uuid4().hex}",
            request_id=request.id,
            version=1,
            status=AuthoringBriefRevisionStatus.DRAFT,
            payload=payload,
            created_at=datetime.now(UTC),
            created_by=actor.actor_id,
        )
        return await self._repository.create(revision)

    async def latest(self, request_id: str) -> AuthoringBriefRevision | None:
        return await self._repository.latest(request_id)

    async def list(self, request_id: str) -> list[AuthoringBriefRevision]:
        return await self._repository.list(request_id)

    async def clarify(
        self, request_id: str, actor: ActorContext
    ) -> AuthoringBriefRevision:
        revision = await self._owned_latest(request_id, actor)
        clarification = self._deterministic_clarification(revision.payload)
        status = (
            AuthoringBriefRevisionStatus.NEEDS_CLARIFICATION
            if clarification.questions
            else AuthoringBriefRevisionStatus.READY_FOR_CONFIRMATION
        )
        updated = revision.model_copy(update={"status": status, "clarification": clarification})
        return await self._repository.update(updated)

    async def create_revision(
        self,
        request_id: str,
        changes: BriefRevisionChanges,
        actor: ActorContext,
    ) -> AuthoringBriefRevision:
        previous = await self._owned_latest(request_id, actor)
        values = {
            key: value
            for key, value in changes.model_dump().items()
            if value is not None and key != "author_feedback"
        }
        payload = previous.payload.model_copy(update=values)
        revision = AuthoringBriefRevision(
            id=f"authoring-brief-revision:{uuid4().hex}",
            request_id=request_id,
            version=previous.version + 1,
            status=AuthoringBriefRevisionStatus.READY_FOR_CONFIRMATION,
            payload=payload,
            author_feedback=changes.author_feedback,
            supersedes_revision_id=previous.id,
            created_at=datetime.now(UTC),
            created_by=actor.actor_id,
        )
        revision = revision.model_copy(update={
            "clarification": self._deterministic_clarification(payload)
        })
        if revision.clarification.questions:
            revision = revision.model_copy(update={
                "status": AuthoringBriefRevisionStatus.NEEDS_CLARIFICATION
            })
        return await self._repository.create(revision)

    async def confirm(
        self, request_id: str, revision_id: str, actor: ActorContext
    ) -> AuthoringBriefRevision:
        revision = await self._repository.get(revision_id)
        if revision is None:
            raise ValueError("revision_not_found")
        if revision.request_id != request_id:
            raise ValueError("revision_request_mismatch")
        latest = await self._repository.latest(request_id)
        if latest is None or latest.id != revision.id:
            raise ValueError("revision_not_latest")
        if revision.clarification.questions:
            raise ValueError("required_clarification_unresolved")
        if revision.status is not AuthoringBriefRevisionStatus.READY_FOR_CONFIRMATION:
            raise ValueError("revision_not_ready_for_confirmation")
        confirmed = revision.model_copy(update={
            "status": AuthoringBriefRevisionStatus.CONFIRMED,
            "confirmed_at": datetime.now(UTC),
            "confirmed_by": actor.actor_id,
        })
        return await self._repository.update(confirmed)

    async def planning_revision(
        self, request: CourseAuthoringRequest
    ) -> AuthoringBriefRevision | None:
        if request.authoring_workflow_version != "sep-08a-v1":
            return None
        revision = await self._repository.latest(request.id)
        if revision is None or revision.status is not AuthoringBriefRevisionStatus.CONFIRMED:
            raise ValueError("authoring_brief_not_confirmed")
        return revision

    async def _owned_latest(
        self, request_id: str, actor: ActorContext
    ) -> AuthoringBriefRevision:
        revision = await self._repository.latest(request_id)
        if revision is None:
            raise ValueError("revision_not_found")
        if revision.created_by != actor.actor_id:
            raise ValueError("authoring_revision_access_denied")
        return revision

    @staticmethod
    def _deterministic_clarification(payload: BriefRevisionPayload) -> BriefClarificationResult:
        questions: list[ClarificationItem] = []
        if not payload.training_goal.strip():
            questions.append(ClarificationItem(
                code="training_goal_missing",
                field="training_goal",
                question="What capability should learners develop?",
            ))
        if not payload.desired_outcomes:
            questions.append(ClarificationItem(
                code="desired_outcome_missing",
                field="desired_outcomes",
                question="What should learners be able to demonstrate after the program?",
            ))
        if payload.legacy_duration_constraint and not (
            payload.learning_horizon or payload.expected_learning_effort
        ):
            questions.append(ClarificationItem(
                code="duration_semantics_ambiguous",
                field="learning_horizon",
                question="Does the stated duration describe the completion window or active learning effort?",
            ))
        return BriefClarificationResult(
            readiness="READY_FOR_CONFIRMATION" if not questions else "NEEDS_CLARIFICATION",
            questions=tuple(questions),
            ambiguities=tuple(item.code for item in questions),
            duration_risks=("duration_semantics_ambiguous",) if any(
                item.code == "duration_semantics_ambiguous" for item in questions
            ) else (),
        )
