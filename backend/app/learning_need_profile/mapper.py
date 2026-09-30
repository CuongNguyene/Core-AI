from app.capability_analysis.schemas import CombinedGapPortfolio, TargetGap, TargetType
from app.matching.schemas import RoleRequirement

from .schemas import (
    LearnerContext,
    LearningNeedCompetency,
    LearningNeedCurrentState,
    LearningNeedGap,
    LearningNeedProfile,
    LearningNeedProvenance,
    LearningNeedTargetState,
)


def _source_gap_exists(portfolio: CombinedGapPortfolio, gap: TargetGap) -> bool:
    analyses = [portfolio.current_role]
    if portfolio.future_role is not None:
        analyses.append(portfolio.future_role)
    return any(source_gap.id == gap.id for analysis in analyses for source_gap in analysis.gaps)


def _target_version(portfolio: CombinedGapPortfolio, gap: TargetGap) -> str:
    if gap.target_type is TargetType.CURRENT_ROLE:
        return portfolio.current_target_version

    if portfolio.future_role is None or portfolio.future_target_version is None:
        raise ValueError("target_version_missing")
    return portfolio.future_target_version


def map_target_gap_to_learning_need(
    *,
    portfolio: CombinedGapPortfolio,
    gap: TargetGap,
    requirement: RoleRequirement,
) -> LearningNeedProfile:
    if not _source_gap_exists(portfolio, gap):
        raise ValueError("source_gap_not_found")
    if portfolio.candidate_id is None:
        raise ValueError("candidate_reference_missing")

    evidence_refs = list(gap.matched_evidence_refs)
    target_version = _target_version(portfolio, gap)
    return LearningNeedProfile(
        id=f"learning-need:{portfolio.id}:{gap.id}",
        candidate_reference=portfolio.candidate_id,
        target_reference=f"{gap.target_id}@{target_version}",
        learner_context=LearnerContext(role=None, experience_level=None),
        competency=LearningNeedCompetency(
            id=requirement.id,
            name=None,
            description=None,
        ),
        current_state=LearningNeedCurrentState(
            level=None,
            evidence_refs=evidence_refs,
        ),
        target_state=LearningNeedTargetState(
            level=requirement.target_level,
            expected_behaviors=list(requirement.observable_behaviors),
        ),
        gap=LearningNeedGap(
            type="skill_gap",
            description=", ".join(gap.missing_signals) or requirement.assessment_recommendation,
        ),
        missing_knowledge=list(gap.missing_signals),
        learning_constraints={},
        priority=gap.preliminary_priority,
        confidence=None,
        source_gap_refs=[gap.id],
        provenance=LearningNeedProvenance(
            analysis_id=portfolio.id,
            analysis_version=portfolio.analysis_version,
            target_id=gap.target_id,
            target_version=target_version,
            source_profile_id=portfolio.cv_profile_id,
            source_profile_version=portfolio.cv_profile_version,
            evidence_refs=list(evidence_refs),
            transformation="learning-need-profile-v1",
        ),
    )
