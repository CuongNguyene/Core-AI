"""Bounded bridge from a composed GAP_DRIVEN brief to course authoring."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.authorization.schemas import ActorContext

from .gap_driven_composer import GapDrivenTrainingBriefProjectionResult
from .schemas import (
    CourseAuthoringMode,
    CourseAuthoringRequestAccepted,
    CourseAuthoringRequestCreate,
)


class CourseAuthoringCreator(Protocol):
    async def create(
        self, body: CourseAuthoringRequestCreate, actor: ActorContext
    ) -> CourseAuthoringRequestAccepted: ...


class GapDrivenCourseAuthoringAdapter:
    """Map only the 04E instructional boundary into the existing request shape."""

    def to_request(
        self,
        projection: GapDrivenTrainingBriefProjectionResult,
        *,
        learner_refs: Sequence[str] = (),
    ) -> CourseAuthoringRequestCreate:
        brief = projection.training_brief
        if brief is None:
            raise ValueError("gap_driven_training_brief_required")
        if not projection.included_learning_need_refs:
            raise ValueError("gap_driven_learning_need_reference_required")

        provenance = projection.provenance
        constraints = {
            "source_usage_mode": projection.usage_mode.value,
            "learning_need_projection_policy": "learning_need_projection@0.1",
            "gap_driven_training_brief_policy": provenance.policy_reference,
            "source_candidate_reference": str(provenance.candidate_reference),
            "source_role_profile_reference": provenance.role_profile_reference,
            "source_capability_analysis_reference": provenance.capability_analysis_reference,
            "source_learning_need_references": ",".join(
                provenance.source_learning_need_refs
            ),
            # Request creation is not learner assignment, including for official input.
            "official_training_assignment": "false",
        }
        return CourseAuthoringRequestCreate(
            title=brief.goal,
            training_brief=brief,
            learner_refs=tuple(learner_refs),
            learning_need_refs=projection.included_learning_need_refs,
            # Reuse the existing learning-authoring objective projection. This
            # is an opaque reference adapter, not a generated/persisted objective.
            objective_refs=tuple(
                f"objective-{reference}"
                for reference in projection.included_learning_need_refs
            ),
            constraints=constraints,
            mode=CourseAuthoringMode.GAP_DRIVEN,
        )


@dataclass(frozen=True)
class GapDrivenCourseAuthoringResult:
    request_created: bool
    reason_code: str
    accepted: CourseAuthoringRequestAccepted | None = None


class GapDrivenCourseAuthoringIntegration:
    """Orchestrate 04E output through the existing CourseAuthoringService."""

    def __init__(
        self,
        authoring: CourseAuthoringCreator,
        adapter: GapDrivenCourseAuthoringAdapter | None = None,
    ) -> None:
        self._authoring = authoring
        self._adapter = adapter or GapDrivenCourseAuthoringAdapter()

    async def create(
        self,
        projection: GapDrivenTrainingBriefProjectionResult,
        actor: ActorContext,
        *,
        learner_refs: Sequence[str] = (),
    ) -> GapDrivenCourseAuthoringResult:
        if projection.training_brief is None:
            return GapDrivenCourseAuthoringResult(
                request_created=False,
                reason_code=projection.reason_code,
            )

        request = self._adapter.to_request(projection, learner_refs=learner_refs)
        accepted = await self._authoring.create(request, actor)
        return GapDrivenCourseAuthoringResult(
            request_created=True,
            reason_code="course_authoring_request_created",
            accepted=accepted,
        )
