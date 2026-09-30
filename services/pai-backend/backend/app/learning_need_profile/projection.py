"""Deterministic projection from capability-gap truth to learning needs."""

from typing import NoReturn, cast

from app.capability_analysis.schemas import (
    AssessmentEvidenceStatus,
    CombinedGapPortfolio,
    TargetGap,
    TargetType,
    TargetUsageMode,
)
from app.matching.schemas import CriterionDimension, RoleCompetencyProfile, RoleRequirement

from .schemas import (
    LearnerContext,
    LearningNeedCompetency,
    LearningNeedCurrentState,
    LearningNeedEligibility,
    LearningNeedGap,
    LearningNeedGapType,
    LearningNeedProfile,
    LearningNeedProvenance,
    LearningNeedResolution,
    LearningNeedTargetState,
)

POLICY_VERSION = "learning_need_projection@0.1"


class LearningNeedProjectionService:
    """Project canonical gaps without recomputing analysis or inventing learner state."""

    def project(
        self,
        *,
        portfolio: CombinedGapPortfolio,
        role_profile: RoleCompetencyProfile,
    ) -> list[LearningNeedProfile]:
        if role_profile.id != portfolio.current_role.target_id:
            raise ValueError("role_profile_target_mismatch")

        requirements = {item.id: item for item in role_profile.requirements}
        projected: list[LearningNeedProfile] = []
        for gap in sorted(self._gaps(portfolio), key=lambda item: item.id):
            requirement = requirements.get(gap.requirement_id)
            if requirement is None:
                raise ValueError("source_requirement_not_found")
            item = self._project_gap(portfolio, gap, requirement)
            if item is not None:
                projected.append(item)
        return projected

    def project_one(
        self,
        *,
        portfolio: CombinedGapPortfolio,
        gap: TargetGap,
        requirement: RoleRequirement,
    ) -> LearningNeedProfile | None:
        """Project one source gap; ``None`` means no active learning need."""
        if not any(item.id == gap.id for item in self._gaps(portfolio)):
            raise ValueError("source_gap_not_found")
        return self._project_gap(portfolio, gap, requirement)

    @staticmethod
    def _gaps(portfolio: CombinedGapPortfolio) -> list[TargetGap]:
        gaps = list(portfolio.current_role.gaps)
        if portfolio.future_role is not None:
            gaps.extend(portfolio.future_role.gaps)
        return gaps

    def _project_gap(
        self,
        portfolio: CombinedGapPortfolio,
        gap: TargetGap,
        requirement: RoleRequirement,
    ) -> LearningNeedProfile | None:
        status = gap.evidence_status
        dimension = requirement.criterion_dimension

        # A supported requirement is not an active learning need. OR groups are
        # already resolved by capability analysis and therefore never reopened here.
        if status is AssessmentEvidenceStatus.SUPPORTED:
            return None
        if dimension is None:
            raise ValueError("non_scoreable_requirement_cannot_be_learning_need")

        eligibility, resolution, reason = self._classify(dimension, status, gap)
        target_version = self._target_version(portfolio, gap)
        warnings = (
            ["source_capability_analysis_preview"]
            if self._usage_mode(portfolio, gap) is TargetUsageMode.PREVIEW
            else []
        )
        evidence_refs = list(gap.matched_evidence_refs)
        return LearningNeedProfile(
            id=f"learning-need:{portfolio.id}:{gap.id}",
            candidate_reference=portfolio.candidate_id
            if portfolio.candidate_id is not None
            else self._missing_candidate(),
            target_reference=f"{gap.target_id}@{target_version}",
            learner_context=LearnerContext(role=None, experience_level=None),
            competency=LearningNeedCompetency(id=requirement.id, name=None, description=None),
            current_state=LearningNeedCurrentState(level=None, evidence_refs=evidence_refs),
            target_state=LearningNeedTargetState(
                level=requirement.target_level,
                expected_behaviors=list(requirement.observable_behaviors),
            ),
            gap=LearningNeedGap(
                type=self._gap_type(dimension),
                description=", ".join(gap.missing_signals) or gap.rationale,
            ),
            missing_knowledge=[],
            learning_constraints={},
            priority=gap.preliminary_priority,
            confidence=gap.decision_details.observed_confidence,
            source_gap_refs=[gap.id],
            provenance=LearningNeedProvenance(
                analysis_id=portfolio.id,
                analysis_version=portfolio.analysis_version,
                target_id=gap.target_id,
                target_version=target_version,
                source_profile_id=portfolio.cv_profile_id,
                source_profile_version=portfolio.cv_profile_version,
                evidence_refs=evidence_refs,
                transformation="learning-need-profile-v1",
                policy_version=POLICY_VERSION,
            ),
            assessment_status=status.value,
            requirement_reference=requirement.id,
            learning_eligibility=eligibility,
            resolution_type=resolution,
            usage_mode=self._usage_mode(portfolio, gap).value,
            warning_codes=warnings,
            projection_reason_code=reason,
        )

    @staticmethod
    def _classify(
        dimension: CriterionDimension,
        status: AssessmentEvidenceStatus,
        gap: TargetGap,
    ) -> tuple[LearningNeedEligibility, LearningNeedResolution, str]:
        if status is AssessmentEvidenceStatus.REQUIRES_VERIFICATION:
            return (
                LearningNeedEligibility.NEEDS_VERIFICATION,
                LearningNeedResolution.VERIFICATION,
                "requires_verification",
            )
        if status is AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE:
            return (
                LearningNeedEligibility.EVIDENCE_MISSING,
                LearningNeedResolution.VERIFICATION,
                "not_found_in_evidence",
            )
        if status is AssessmentEvidenceStatus.CONTEXT_MISMATCH:
            if gap.matched_evidence_refs:
                return (
                    LearningNeedEligibility.UNRESOLVED,
                    LearningNeedResolution.EXPERIENCE_EXPOSURE,
                    "context_mismatch_experience_exposure",
                )
            return (
                LearningNeedEligibility.UNRESOLVED,
                LearningNeedResolution.UNRESOLVED,
                "context_mismatch_unresolved",
            )
        if status is AssessmentEvidenceStatus.INSUFFICIENT:
            if dimension is CriterionDimension.SKILL:
                return (
                    LearningNeedEligibility.READY_FOR_LEARNING,
                    LearningNeedResolution.LEARNING,
                    "insufficient_skill_learning_eligible",
                )
            if dimension is CriterionDimension.QUALIFICATION:
                return (
                    LearningNeedEligibility.READY_FOR_LEARNING,
                    LearningNeedResolution.LEARNING,
                    "insufficient_qualification_learning_eligible",
                )
            if dimension is CriterionDimension.EXPERIENCE:
                return (
                    LearningNeedEligibility.UNRESOLVED,
                    LearningNeedResolution.EXPERIENCE_EXPOSURE,
                    "insufficient_experience_exposure",
                )
            if dimension in {CriterionDimension.CREDENTIAL, CriterionDimension.EDUCATION}:
                return (
                    LearningNeedEligibility.UNRESOLVED,
                    LearningNeedResolution.VERIFICATION,
                    "insufficient_qualification_unresolved",
                )
        if dimension is CriterionDimension.CREDENTIAL:
            return (
                LearningNeedEligibility.UNRESOLVED,
                LearningNeedResolution.CREDENTIAL,
                "credential_resolution_required",
            )
        if dimension is CriterionDimension.EDUCATION:
            return (
                LearningNeedEligibility.UNRESOLVED,
                LearningNeedResolution.NON_LEARNING,
                "education_resolution_required",
            )
        return (
            LearningNeedEligibility.UNRESOLVED,
            LearningNeedResolution.UNRESOLVED,
            "assessment_unresolved",
        )

    @staticmethod
    def _gap_type(dimension: CriterionDimension) -> LearningNeedGapType:
        return cast(
            LearningNeedGapType,
            {
            CriterionDimension.SKILL: "skill_gap",
            CriterionDimension.EXPERIENCE: "experience_gap",
            CriterionDimension.EDUCATION: "education_gap",
            CriterionDimension.CREDENTIAL: "credential_gap",
            CriterionDimension.QUALIFICATION: "qualification_gap",
            }[dimension],
        )

    @staticmethod
    def _usage_mode(
        portfolio: CombinedGapPortfolio, gap: TargetGap
    ) -> TargetUsageMode:
        if gap.target_type is TargetType.CURRENT_ROLE:
            return portfolio.current_role.usage_mode
        if portfolio.future_role is None:
            raise ValueError("future_role_missing")
        return portfolio.future_role.usage_mode

    @staticmethod
    def _target_version(portfolio: CombinedGapPortfolio, gap: TargetGap) -> str:
        if gap.target_type is TargetType.CURRENT_ROLE:
            return portfolio.current_target_version
        if portfolio.future_target_version is None:
            raise ValueError("target_version_missing")
        return portfolio.future_target_version

    @staticmethod
    def _missing_candidate() -> NoReturn:
        raise ValueError("candidate_reference_missing")
