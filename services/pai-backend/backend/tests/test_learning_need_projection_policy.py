from uuid import UUID

import pytest

from app.capability_analysis.schemas import (
    AnalysisStatus,
    AssessmentEvidenceStatus,
    CombinedGapPortfolio,
    PreliminaryPriority,
    TargetGap,
    TargetGapAnalysis,
    TargetType,
    TargetUsageMode,
)
from app.learning_need_profile.projection import LearningNeedProjectionService
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)

CANDIDATE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ACTOR_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ORG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def requirement(
    *, dimension: CriterionDimension, requirement_id: str = "requirement-1"
) -> RoleRequirement:
    return RoleRequirement(
        id=requirement_id,
        criterion_dimension=dimension,
        classification=RequirementClassification.TRAINABLE_MANDATORY,
        evidence_terms=["source evidence"],
        confidence_threshold=0.8,
        assessment_recommendation="Review the requirement.",
        rubric_version="rubric-v1",
        target_level="3",
        observable_behaviors=["Demonstrate the required behavior"],
    )


def gap(
    *,
    status: AssessmentEvidenceStatus,
    requirement_id: str = "requirement-1",
    gap_id: str = "gap-1",
) -> TargetGap:
    return TargetGap(
        id=gap_id,
        target_id="role-1",
        target_type=TargetType.CURRENT_ROLE,
        requirement_id=requirement_id,
        matched_evidence_refs=["evidence:cv:page-1"],
        missing_signals=["missing-signal"],
        rationale="The assessment requires reviewer follow-up.",
        preliminary_priority=PreliminaryPriority.HIGH,
        missing_priority_inputs=[],
        evidence_status=status,
    )


def portfolio(source_gap: TargetGap) -> CombinedGapPortfolio:
    return CombinedGapPortfolio(
        id="analysis-1",
        cv_profile_id="profile-1",
        cv_profile_version=2,
        current_target_version="3",
        owner_actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        correlation_id="correlation-1",
        candidate_id=CANDIDATE_ID,
        analysis_status=AnalysisStatus.READY,
        current_role=TargetGapAnalysis(
            target_id="role-1",
            target_type=TargetType.CURRENT_ROLE,
            usage_mode=TargetUsageMode.PREVIEW,
            assessments=[],
            gaps=[source_gap],
        ),
        preview_readiness={
            "analysis_mode": "preview",
            "capability_verification_status": "provisional",
            "final_competency_decision_prohibited": True,
        },
    )


def role_profile(source_requirement: RoleRequirement) -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id="role-1",
        version="3",
        status=RoleProfileStatus.PROVISIONAL,
        source_jd_profile_id="jd-1",
        source_jd_profile_version=1,
        rule_set_version="rules-v1",
        policy_version="policy-v1",
        requirements=[source_requirement],
    )


def project(
    status: AssessmentEvidenceStatus, dimension: CriterionDimension
):
    source_gap = gap(status=status)
    return LearningNeedProjectionService().project(
        portfolio=portfolio(source_gap),
        role_profile=role_profile(requirement(dimension=dimension)),
    )


def test_matched_gap_does_not_create_active_learning_need() -> None:
    assert project(AssessmentEvidenceStatus.SUPPORTED, CriterionDimension.SKILL) == []


def test_insufficient_skill_is_ready_for_learning() -> None:
    result = project(AssessmentEvidenceStatus.INSUFFICIENT, CriterionDimension.SKILL)

    assert len(result) == 1
    assert result[0].learning_eligibility == "READY_FOR_LEARNING"
    assert result[0].resolution_type == "learning"
    assert result[0].usage_mode == TargetUsageMode.PREVIEW


@pytest.mark.parametrize(
    "dimension",
    [CriterionDimension.CREDENTIAL, CriterionDimension.EDUCATION],
)
def test_verification_status_does_not_become_training(dimension: CriterionDimension) -> None:
    result = project(AssessmentEvidenceStatus.REQUIRES_VERIFICATION, dimension)

    assert result[0].learning_eligibility == "NEEDS_VERIFICATION"
    assert result[0].resolution_type == "verification"


def test_not_found_is_evidence_missing_and_does_not_invent_knowledge() -> None:
    result = project(AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE, CriterionDimension.SKILL)

    assert result[0].learning_eligibility == "EVIDENCE_MISSING"
    assert result[0].resolution_type == "verification"
    assert result[0].missing_knowledge == []


def test_not_found_credential_remains_verification_only() -> None:
    result = project(
        AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
        CriterionDimension.CREDENTIAL,
    )

    assert result[0].learning_eligibility == "EVIDENCE_MISSING"
    assert result[0].resolution_type == "verification"
    assert result[0].gap.type == "credential_gap"


def test_experience_gap_prefers_experience_exposure() -> None:
    result = project(AssessmentEvidenceStatus.INSUFFICIENT, CriterionDimension.EXPERIENCE)

    assert result[0].resolution_type == "experience_exposure"
    assert result[0].learning_eligibility == "UNRESOLVED"


def test_non_scoreable_requirement_fails_closed() -> None:
    source_gap = gap(status=AssessmentEvidenceStatus.INSUFFICIENT)
    with pytest.raises(ValueError, match="non_scoreable_requirement"):
        LearningNeedProjectionService().project(
            portfolio=portfolio(source_gap),
            role_profile=role_profile(
                requirement(dimension=None)  # type: ignore[arg-type]
            ),
        )


def test_preview_provenance_and_source_versions_are_preserved() -> None:
    result = project(AssessmentEvidenceStatus.INSUFFICIENT, CriterionDimension.SKILL)[0]

    assert result.provenance.analysis_id == "analysis-1"
    assert result.provenance.analysis_version == 1
    assert result.provenance.target_id == "role-1"
    assert result.provenance.target_version == "3"
    assert result.provenance.source_profile_id == "profile-1"
    assert result.provenance.source_profile_version == 2
    assert result.source_gap_refs == ["gap-1"]
    assert result.warning_codes == ["source_capability_analysis_preview"]
    assert result.projection_reason_code == "insufficient_skill_learning_eligible"


def test_projection_is_deterministic() -> None:
    first = project(AssessmentEvidenceStatus.INSUFFICIENT, CriterionDimension.SKILL)
    second = project(AssessmentEvidenceStatus.INSUFFICIENT, CriterionDimension.SKILL)

    assert first == second
    assert first[0].id == "learning-need:analysis-1:gap-1"


def test_raw_source_data_is_not_projected() -> None:
    result = project(AssessmentEvidenceStatus.INSUFFICIENT, CriterionDimension.SKILL)[0]

    payload = result.model_dump_json()
    assert "raw CV" not in payload
    assert "provider response" not in payload
    assert "prompt" not in payload
