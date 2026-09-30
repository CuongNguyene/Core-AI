from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.content_generation.schemas import ContentGenerationResult
from app.course_authoring.brief_revision_schemas import (
    AuthoringBriefRevision,
    BriefRevisionChanges,
)
from app.course_authoring.conversation_schemas import AuthoringConversationResponse
from app.course_authoring.revision_schemas import CourseDraftRevisionRequest
from app.course_authoring.schemas import (
    AudienceSnapshot,
    AudienceSnapshotSource,
    CourseAuthoringMode,
    CourseAuthoringRequest,
    CourseAuthoringRequestAccepted,
    CourseAuthoringRequestCreate,
    CourseAuthoringStatus,
    TrainingBrief,
)
from app.course_generation.schemas import CourseGenerationAccepted, CourseGenerationProgress
from app.curriculum_planning.schemas import (
    CurriculumPlan,
    CurriculumPlanProjection,
    CurriculumPlanStatus,
)

from .schemas import IntegrationEnvelopeV1


class TrainingBriefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    language: str | None = None
    target_completion_context: str | None = None
    duration_constraint: str | None = None
    notes: str | None = None
    desired_outcomes: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    learning_horizon: str | None = None
    expected_learning_effort: str | None = None

    def to_domain(self) -> TrainingBrief:
        values = self.model_dump()
        values["desired_outcomes"] = tuple(self.desired_outcomes)
        values["prerequisites"] = tuple(self.prerequisites)
        return TrainingBrief.model_validate(values)

    @classmethod
    def from_domain(cls, brief: TrainingBrief) -> "TrainingBriefV1":
        return cls.model_validate(brief.model_dump())


class AuthoringConversationRespondV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_message: str = Field(min_length=1)


class AuthoringConversationResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant_message: str
    conversation_state: str
    questions: list[dict[str, Any]]
    proposed_changes: list[dict[str, Any]]
    unresolved_items: list[str]
    readiness: str

    @classmethod
    def from_domain(cls, response: AuthoringConversationResponse) -> "AuthoringConversationResponseV1":
        return cls.model_validate(response.model_dump(mode="json"))


class CourseAuthoringRequestCreateV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    training_brief: TrainingBriefV1
    learner_refs: list[str]
    learning_need_refs: list[str] = Field(default_factory=list)
    objective_refs: list[str] = Field(default_factory=list)
    instructional_blueprint_ref: str | None = None
    constraints: dict[str, str] = Field(default_factory=dict)
    mode: CourseAuthoringMode = CourseAuthoringMode.GOAL_DRIVEN

    def to_domain(self) -> CourseAuthoringRequestCreate:
        return CourseAuthoringRequestCreate(
            title=self.title,
            training_brief=self.training_brief.to_domain(),
            learner_refs=tuple(self.learner_refs),
            learning_need_refs=tuple(self.learning_need_refs),
            objective_refs=tuple(self.objective_refs),
            instructional_blueprint_ref=self.instructional_blueprint_ref,
            constraints=self.constraints,
            mode=self.mode,
        )


class CourseAuthoringRequestAcceptedV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    status: CourseAuthoringStatus
    audience_snapshot_id: str = Field(min_length=1)

    @classmethod
    def from_domain(cls, accepted: CourseAuthoringRequestAccepted) -> "CourseAuthoringRequestAcceptedV1":
        return cls.model_validate(accepted.model_dump())


class AudienceSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    learner_refs: list[str]
    learner_count: int = Field(ge=0)
    captured_at: datetime
    source: AudienceSnapshotSource
    metadata: dict[str, str]

    @classmethod
    def from_domain(cls, audience: AudienceSnapshot) -> "AudienceSnapshotV1":
        return cls.model_validate(audience.model_dump())


class CourseAuthoringRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str
    training_brief: TrainingBriefV1
    audience_snapshot: AudienceSnapshotV1
    learning_need_refs: list[str]
    objective_refs: list[str]
    instructional_blueprint_ref: str | None = None
    constraints: dict[str, str]
    mode: CourseAuthoringMode
    status: CourseAuthoringStatus
    authoring_workflow_version: str | None = None
    created_by_actor_ref: UUID
    created_at: datetime

    @classmethod
    def from_domain(cls, request: CourseAuthoringRequest) -> "CourseAuthoringRequestV1":
        return cls(
            id=request.id,
            title=request.title,
            training_brief=TrainingBriefV1.from_domain(request.training_brief),
            audience_snapshot=AudienceSnapshotV1.from_domain(request.audience_snapshot),
            learning_need_refs=list(request.learning_need_refs),
            objective_refs=list(request.objective_refs),
            instructional_blueprint_ref=request.instructional_blueprint_ref,
            constraints=dict(request.constraints),
            mode=request.mode,
            status=request.status,
            authoring_workflow_version=request.authoring_workflow_version,
            created_by_actor_ref=request.created_by_actor_ref,
            created_at=request.created_at,
        )


CourseAuthoringCreateEnvelopeV1 = IntegrationEnvelopeV1[CourseAuthoringRequestCreateV1]
CourseAuthoringAcceptedEnvelopeV1 = IntegrationEnvelopeV1[CourseAuthoringRequestAcceptedV1]
CourseAuthoringRequestEnvelopeV1 = IntegrationEnvelopeV1[CourseAuthoringRequestV1]
CourseAuthoringRequestListV1 = list[CourseAuthoringRequestV1]
CourseAuthoringRequestListEnvelopeV1 = IntegrationEnvelopeV1[CourseAuthoringRequestListV1]


class BriefRevisionChangesV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_goal: str | None = None
    desired_outcomes: list[str] | None = None
    prerequisites: list[str] | None = None
    constraints: dict[str, str] | None = None
    learning_horizon: str | None = None
    expected_learning_effort: str | None = None
    excluded_scope: list[str] | None = None
    emphasis: list[str] | None = None
    author_feedback: str | None = None

    def to_domain(self) -> BriefRevisionChanges:
        return BriefRevisionChanges.model_validate({
            "training_goal": self.training_goal,
            "desired_outcomes": tuple(self.desired_outcomes) if self.desired_outcomes is not None else None,
            "prerequisites": tuple(self.prerequisites) if self.prerequisites is not None else None,
            "constraints": self.constraints,
            "learning_horizon": self.learning_horizon,
            "expected_learning_effort": self.expected_learning_effort,
            "excluded_scope": tuple(self.excluded_scope) if self.excluded_scope is not None else None,
            "emphasis": tuple(self.emphasis) if self.emphasis is not None else None,
            "author_feedback": self.author_feedback,
        })


class AuthoringBriefRevisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    request_id: str
    version: int
    status: str
    payload: dict[str, object]
    clarification: dict[str, object]
    author_feedback: str | None = None
    supersedes_revision_id: str | None = None
    confirmed_at: datetime | None = None
    confirmed_by: UUID | None = None
    created_at: datetime
    created_by: UUID

    @classmethod
    def from_domain(cls, revision: AuthoringBriefRevision) -> "AuthoringBriefRevisionV1":
        return cls(
            id=revision.id,
            request_id=revision.request_id,
            version=revision.version,
            status=revision.status.value,
            payload=revision.payload.model_dump(mode="json"),
            clarification=revision.clarification.model_dump(mode="json"),
            author_feedback=revision.author_feedback,
            supersedes_revision_id=revision.supersedes_revision_id,
            confirmed_at=revision.confirmed_at,
            confirmed_by=revision.confirmed_by,
            created_at=revision.created_at,
            created_by=revision.created_by,
        )


AuthoringBriefRevisionListV1 = list[AuthoringBriefRevisionV1]
AuthoringBriefRevisionListEnvelopeV1 = IntegrationEnvelopeV1[AuthoringBriefRevisionListV1]
AuthoringBriefRevisionEnvelopeV1 = IntegrationEnvelopeV1[AuthoringBriefRevisionV1]
CourseGenerationAcceptedV1 = CourseGenerationAccepted
CourseGenerationProgressV1 = CourseGenerationProgress
CourseGenerationResponseV1 = CourseGenerationAcceptedV1 | CourseGenerationProgressV1
CourseGenerationAcceptedEnvelopeV1 = IntegrationEnvelopeV1[CourseGenerationResponseV1]


class CurriculumPlanV1(CurriculumPlanProjection):
    version: int = Field(ge=1)
    supersedes_plan_ref: str | None = None

    @classmethod
    def from_domain(cls, plan: CurriculumPlan) -> "CurriculumPlanV1":
        planning_metadata = dict(plan.planning_metadata)
        is_legacy_gap_plan = any(
            objective.origin == "CANONICAL_LEARNING_OBJECTIVE"
            for objective in plan.learning_objectives
        )
        projected_status = plan.status
        if is_legacy_gap_plan:
            planning_metadata.setdefault(
                "curriculum_review_workflow_version", "sep-08d-v1"
            )
            if projected_status is CurriculumPlanStatus.PLANNED:
                projected_status = CurriculumPlanStatus.READY_FOR_REVIEW
        return cls(
            plan_ref=plan.id,
            version=plan.version,
            supersedes_plan_ref=plan.supersedes_plan_ref,
            status=projected_status,
            duration=plan.normalized_duration,
            objective_count=len(plan.learning_objectives),
            module_count=len(plan.modules),
            lesson_count=sum(len(module.lessons) for module in plan.modules),
            objectives=plan.learning_objectives,
            modules=plan.modules,
            planning_metadata=planning_metadata,
        )


CurriculumPlanEnvelopeV1 = IntegrationEnvelopeV1[CurriculumPlanV1]
CurriculumPlanListEnvelopeV1 = IntegrationEnvelopeV1[list[CurriculumPlanV1]]


class CurriculumPatchOperationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    fields: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None


class CurriculumPlanRevisionRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: list[CurriculumPatchOperationV1] = Field(min_length=1)
    rationale: str | None = None


class CourseDraftRevisionRequestV1(CourseDraftRevisionRequest):
    pass


class ContentReviewRejectV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str | None = Field(default=None, min_length=1)


class CourseAuthoringResultVersionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_ref: str = Field(min_length=1)
    version: int = Field(ge=1)
    status: str
    supersedes_result_ref: str | None = None
    created_at: datetime | None = None
    generation_run_ref: str | None = None
    revision_metadata: dict[str, object] | None = None

    @classmethod
    def from_domain(cls, result: ContentGenerationResult) -> "CourseAuthoringResultVersionV1":
        return cls(
            result_ref=result.id,
            version=result.version,
            status=result.status,
            supersedes_result_ref=result.supersedes_result_ref,
            created_at=result.created_at or result.generation_metadata.created_at,
            generation_run_ref=(
                result.generation_run.run_id if result.generation_run is not None else None
            ),
            revision_metadata=(
                result.revision_metadata.model_dump(mode="json")
                if result.revision_metadata is not None
                else None
            ),
        )


CourseDraftRevisionEnvelopeV1 = IntegrationEnvelopeV1[CourseDraftRevisionRequestV1]
ContentReviewRejectEnvelopeV1 = IntegrationEnvelopeV1[ContentReviewRejectV1]
CourseAuthoringResultVersionListV1 = list[CourseAuthoringResultVersionV1]
