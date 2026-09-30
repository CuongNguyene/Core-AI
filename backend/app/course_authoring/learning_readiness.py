"""Read-only learning readiness projection for capability-gap review."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.capability_analysis.schemas import TargetUsageMode
from app.learning_need_profile.schemas import LearningNeedEligibility, LearningNeedProfile

from .gap_driven_composer import (
    GapDrivenTrainingBriefComposer,
    GapDrivenTrainingBriefProjectionResult,
    ResolutionAction,
)
from .schemas import TrainingBrief


class LearningReadinessProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    usage_mode: str
    ready_for_learning_count: int = Field(ge=0)
    needs_verification_count: int = Field(ge=0)
    evidence_missing_count: int = Field(ge=0)
    context_mismatch_count: int = Field(ge=0)
    non_learning_resolution_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    generation_allowed: bool
    generation_block_reason: str | None = None
    included_learning_need_refs: tuple[str, ...]
    included_learning_items: tuple["IncludedLearningItemProjection", ...] = ()
    resolution_actions: tuple[ResolutionAction, ...]
    warnings: tuple[str, ...]
    training_brief: TrainingBrief | None = None
    candidate_reference: UUID | None = None
    target_reference: str | None = None


class IncludedLearningItemProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    learning_need_ref: str = Field(min_length=1)
    requirement_ref: str = Field(min_length=1)
    label: str = Field(min_length=1)
    assessment_status: str = Field(min_length=1)
    resolution_type: str = Field(min_length=1)


def build_learning_readiness_projection(
    learning_needs: list[LearningNeedProfile] | tuple[LearningNeedProfile, ...],
) -> LearningReadinessProjection:
    """Project generation readiness from the existing learning-need policy."""
    if not learning_needs:
        return LearningReadinessProjection(
            usage_mode=TargetUsageMode.PREVIEW,
            ready_for_learning_count=0,
            needs_verification_count=0,
            evidence_missing_count=0,
            context_mismatch_count=0,
            non_learning_resolution_count=0,
            unresolved_count=0,
            generation_allowed=False,
            generation_block_reason="no_learning_eligible_needs",
            included_learning_need_refs=(),
            resolution_actions=(),
            warnings=(),
        )

    result = GapDrivenTrainingBriefComposer().compose(learning_needs)
    return _from_composer(result, learning_needs)


def _from_composer(
    result: GapDrivenTrainingBriefProjectionResult,
    learning_needs: list[LearningNeedProfile] | tuple[LearningNeedProfile, ...],
) -> LearningReadinessProjection:
    included_by_ref = {item.id: item for item in learning_needs}
    included_items = tuple(
        IncludedLearningItemProjection(
            learning_need_ref=reference,
            requirement_ref=included_by_ref[reference].requirement_reference or included_by_ref[reference].competency.id,
            label=included_by_ref[reference].competency.name or included_by_ref[reference].competency.id,
            assessment_status=included_by_ref[reference].assessment_status or included_by_ref[reference].learning_eligibility.value,
            resolution_type=included_by_ref[reference].resolution_type.value,
        )
        for reference in result.included_learning_need_refs
        if reference in included_by_ref
    )
    return LearningReadinessProjection(
        usage_mode=result.usage_mode.value,
        ready_for_learning_count=len(result.included_learning_need_refs),
        needs_verification_count=sum(
            item.learning_eligibility is LearningNeedEligibility.NEEDS_VERIFICATION
            for item in learning_needs
        ),
        evidence_missing_count=sum(
            item.learning_eligibility is LearningNeedEligibility.EVIDENCE_MISSING
            for item in learning_needs
        ),
        context_mismatch_count=sum(
            item.projection_reason_code.startswith("context_mismatch")
            for item in learning_needs
        ),
        non_learning_resolution_count=sum(
            item.learning_eligibility is LearningNeedEligibility.NON_LEARNING_RESOLUTION
            for item in learning_needs
        ),
        unresolved_count=sum(
            item.learning_eligibility is LearningNeedEligibility.UNRESOLVED
            for item in learning_needs
        ),
        generation_allowed=result.training_brief is not None,
        generation_block_reason=(None if result.training_brief is not None else result.reason_code),
        included_learning_need_refs=result.included_learning_need_refs,
        included_learning_items=included_items,
        resolution_actions=result.resolution_actions,
        warnings=result.warnings,
        training_brief=result.training_brief,
        candidate_reference=learning_needs[0].candidate_reference,
        target_reference=learning_needs[0].target_reference,
    )
