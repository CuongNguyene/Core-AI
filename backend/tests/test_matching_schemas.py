from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)


def test_role_profile_supports_provisional_lifecycle_without_changing_stable_fields() -> None:
    profile = RoleCompetencyProfile(
        id="role-engineer",
        version="1.0",
        status=RoleProfileStatus.PROVISIONAL,
        source_jd_profile_id="jd-profile-1",
        source_jd_profile_version=1,
        rule_set_version="matching-v1",
        policy_version="policy-v1",
        requirements=[
            RoleRequirement(
                id="python",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.ROLE_CRITICAL,
                evidence_terms=["Python"],
                confidence_threshold=0.8,
                assessment_recommendation="practical_task",
                rubric_version="rubric-v1",
            )
        ],
    )

    assert profile.status is RoleProfileStatus.PROVISIONAL
    assert profile.id == "role-engineer"
    assert profile.version == "1.0"
    assert profile.source_jd_profile_id == "jd-profile-1"
