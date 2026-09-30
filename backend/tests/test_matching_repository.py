import pytest

from app.authorization.fixtures import LEARNER_ID
from app.matching.repository import (
    InMemoryPreliminaryMatchRepository,
    InMemoryRoleProfileRepository,
)
from app.matching.schemas import (
    CriterionDimension,
    CriterionResult,
    CriterionStatus,
    EvidenceAllocation,
    MandatoryStatus,
    PreliminaryMatch,
    PreliminaryMatchStatus,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)


def active_role() -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id="role-ai-engineer",
        version="1.0",
        status=RoleProfileStatus.ACTIVE,
        source_jd_profile_id="jd-profile-1",
        source_jd_profile_version=1,
        rule_set_version="1.0",
        policy_version="matching-v1",
        requirements=[
            RoleRequirement(
                id="critical-python",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.ROLE_CRITICAL,
                evidence_terms=["Python"],
                confidence_threshold=0.8,
                assessment_recommendation="practical_task",
                rubric_version="1.0",
            )
        ],
    )


def match(allocations: list[EvidenceAllocation]) -> PreliminaryMatch:
    return PreliminaryMatch(
        id="match-1",
        cv_profile_id="cv-profile-1",
        cv_profile_version=1,
        jd_profile_id="jd-profile-1",
        jd_profile_version=1,
        role_profile_id="role-ai-engineer",
        role_profile_version="1.0",
        rule_set_version="1.0",
        policy_version="matching-v1",
        actor_id=LEARNER_ID,
        correlation_id="corr-1",
        status=PreliminaryMatchStatus.COMPLETED,
        criterion_results=[
            CriterionResult(
                requirement_id="critical-python",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.ROLE_CRITICAL,
                status=CriterionStatus.MATCHED,
                source_evidence=[],
                mandatory_status=MandatoryStatus.SATISFIED,
                recommended_next_assessment="practical_task",
            )
        ],
        evidence_allocations=allocations,
        preliminary_skill_gaps=[],
    )


@pytest.mark.asyncio
async def test_active_role_profile_is_resolved_by_id_and_version() -> None:
    repository = InMemoryRoleProfileRepository([active_role()])

    profile = await repository.get_active("role-ai-engineer")

    assert profile is not None
    assert profile.version == "1.0"


@pytest.mark.asyncio
async def test_match_persists_exact_input_versions_and_safe_audit() -> None:
    repository = InMemoryPreliminaryMatchRepository()
    saved = await repository.create(
        match([EvidenceAllocation(evidence_id="evidence-1", requirement_id="critical-python")])
    )

    assert saved.cv_profile_version == 1
    assert saved.role_profile_version == "1.0"
    assert [event["action"] for event in repository.audit_events] == [
        "MATCHING_STARTED",
        "MATCHING_COMPLETED",
    ]
    assert "document" not in repository.audit_events[0]


@pytest.mark.asyncio
async def test_duplicate_decisive_evidence_allocation_is_rejected() -> None:
    repository = InMemoryPreliminaryMatchRepository()

    with pytest.raises(ValueError, match="decisive evidence"):
        await repository.create(
            match(
                [
                    EvidenceAllocation(evidence_id="evidence-1", requirement_id="critical-python"),
                    EvidenceAllocation(
                        evidence_id="evidence-1", requirement_id="other-requirement"
                    ),
                ]
            )
        )
