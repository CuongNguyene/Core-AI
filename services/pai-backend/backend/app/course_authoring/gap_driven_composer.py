"""Bounded composition from learning needs to a future GAP_DRIVEN request."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.capability_analysis.schemas import PreliminaryPriority, TargetUsageMode
from app.learning_need_profile.schemas import (
    LearningNeedEligibility,
    LearningNeedProfile,
    LearningNeedResolution,
)

from .schemas import TrainingBrief

POLICY_VERSION = "gap_driven_training_brief@0.1"


class ResolutionActionType(StrEnum):
    VERIFICATION = "verification"
    EVIDENCE_MISSING = "evidence_missing"
    CREDENTIAL = "credential"
    EXPERIENCE_EXPOSURE = "experience_exposure"
    ASSESSMENT = "assessment"
    NON_LEARNING = "non_learning"
    UNRESOLVED = "unresolved"


class ResolutionAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_learning_need_ref: str = Field(min_length=1)
    type: ResolutionActionType
    priority: PreliminaryPriority
    reason_code: str = Field(min_length=1)
    source_gap_refs: tuple[str, ...] = Field(min_length=1)


class GapDrivenTrainingBriefProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_reference: UUID
    role_profile_reference: str = Field(min_length=1)
    capability_analysis_reference: str = Field(min_length=1)
    source_learning_need_refs: tuple[str, ...] = Field(min_length=1)
    policy_reference: str = Field(min_length=1)


class GapDrivenTrainingBriefProjectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    training_brief: TrainingBrief | None
    included_learning_need_refs: tuple[str, ...]
    resolution_actions: tuple[ResolutionAction, ...]
    warnings: tuple[str, ...]
    usage_mode: TargetUsageMode
    reason_code: str = Field(min_length=1)
    provenance: GapDrivenTrainingBriefProvenance


class GapDrivenTrainingBriefComposer:
    """Compose only source-grounded learning scope; never call generation."""

    def compose(
        self,
        learning_needs: list[LearningNeedProfile] | tuple[LearningNeedProfile, ...],
    ) -> GapDrivenTrainingBriefProjectionResult:
        if not learning_needs:
            raise ValueError("learning_needs_required")

        ordered = sorted(learning_needs, key=self._sort_key)
        self._validate_common_source(ordered)
        included = tuple(
            item
            for item in ordered
            if item.learning_eligibility is LearningNeedEligibility.READY_FOR_LEARNING
            and item.resolution_type is LearningNeedResolution.LEARNING
        )
        actions = tuple(
            self._resolution_action(item)
            for item in ordered
            if item not in included
        )
        mode = self._usage_mode(ordered)
        warnings = tuple(
            sorted(
                {
                    warning
                    for item in ordered
                    for warning in item.warning_codes
                }
                | ({"source_learning_need_preview"} if mode is TargetUsageMode.PREVIEW else set())
            )
        )
        provenance = self._provenance(ordered)
        if not included:
            return GapDrivenTrainingBriefProjectionResult(
                training_brief=None,
                included_learning_need_refs=(),
                resolution_actions=actions,
                warnings=warnings,
                usage_mode=mode,
                reason_code="no_learning_eligible_needs",
                provenance=provenance,
            )

        included_refs = tuple(item.id for item in included)
        outcomes = tuple(
            behavior
            for item in included
            for behavior in item.target_state.expected_behaviors
        )
        brief = TrainingBrief(
            goal=f"Develop eligible capabilities for {ordered[0].target_reference}",
            desired_outcomes=outcomes,
        )
        return GapDrivenTrainingBriefProjectionResult(
            training_brief=brief,
            included_learning_need_refs=included_refs,
            resolution_actions=actions,
            warnings=warnings,
            usage_mode=mode,
            reason_code="learning_needs_composed",
            provenance=provenance,
        )

    @staticmethod
    def _sort_key(item: LearningNeedProfile) -> tuple[int, str]:
        priority = {
            PreliminaryPriority.HIGH: 0,
            PreliminaryPriority.MEDIUM: 1,
            PreliminaryPriority.LOW: 2,
        }[item.priority]
        return priority, item.id

    @staticmethod
    def _usage_mode(items: list[LearningNeedProfile]) -> TargetUsageMode:
        values = {item.usage_mode for item in items}
        if len(values) != 1:
            raise ValueError("learning_need_usage_mode_mismatch")
        try:
            return TargetUsageMode(next(iter(values)))
        except ValueError as exc:
            raise ValueError("learning_need_usage_mode_invalid") from exc

    @staticmethod
    def _validate_common_source(items: list[LearningNeedProfile]) -> None:
        refs = [item.id for item in items]
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate_learning_need_reference")
        candidates = {item.candidate_reference for item in items}
        analyses = {f"{item.provenance.analysis_id}@{item.provenance.analysis_version}" for item in items}
        targets = {item.target_reference for item in items}
        if len(candidates) != 1 or len(analyses) != 1 or len(targets) != 1:
            raise ValueError("learning_need_source_mismatch")

    @staticmethod
    def _resolution_action(item: LearningNeedProfile) -> ResolutionAction:
        if item.learning_eligibility is LearningNeedEligibility.EVIDENCE_MISSING:
            # CAP-DEMO-04D uses verification as the conservative resolution
            # for missing evidence; keep that contract in the action route.
            action_type = ResolutionActionType.VERIFICATION
        else:
            try:
                action_type = ResolutionActionType(item.resolution_type.value)
            except ValueError:
                action_type = ResolutionActionType.UNRESOLVED
        return ResolutionAction(
            source_learning_need_ref=item.id,
            type=action_type,
            priority=item.priority,
            reason_code=item.projection_reason_code,
            source_gap_refs=tuple(item.source_gap_refs),
        )

    @staticmethod
    def _provenance(items: list[LearningNeedProfile]) -> GapDrivenTrainingBriefProvenance:
        first = items[0]
        return GapDrivenTrainingBriefProvenance(
            candidate_reference=first.candidate_reference,
            role_profile_reference=first.target_reference,
            capability_analysis_reference=(
                f"{first.provenance.analysis_id}@{first.provenance.analysis_version}"
            ),
            source_learning_need_refs=tuple(item.id for item in items),
            policy_reference=POLICY_VERSION,
        )
