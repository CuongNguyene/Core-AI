import asyncio
from uuid import UUID

import pytest

from app.matching.repository import InMemoryRoleProfileRepository
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)

ROLE_A = UUID("11111111-1111-4111-8111-111111111111")
ROLE_B = UUID("22222222-2222-4222-8222-222222222222")


def profile(profile_id: str, role_id: UUID) -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id=profile_id,
        version="1",
        status=RoleProfileStatus.PROVISIONAL,
        source_jd_profile_id=f"jd-{profile_id}",
        source_jd_profile_version=1,
        rule_set_version="rules-v1",
        policy_version="policy-v1",
        role_id=role_id,
        role_jd_version_id=UUID("33333333-3333-4333-8333-333333333333"),
        requirements=[
            RoleRequirement(
                id="python",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.ROLE_CRITICAL,
                evidence_terms=["Python"],
                confidence_threshold=0.8,
                assessment_recommendation="Review Python evidence.",
                rubric_version="rubric-v1",
            )
        ],
    )


def test_role_aware_profiles_allocate_monotonic_governance_versions_per_role() -> None:
    async def scenario() -> None:
        repository = InMemoryRoleProfileRepository([])

        first = await repository.save(profile("role-profile-a", ROLE_A))
        second = await repository.save(profile("role-profile-b", ROLE_A))
        other_role = await repository.save(profile("role-profile-c", ROLE_B))

        assert first.governance_version == 1
        assert second.governance_version == 2
        assert other_role.governance_version == 1

    asyncio.run(scenario())


def test_activation_targets_exact_role_profile_governance_version() -> None:
    async def scenario() -> None:
        repository = InMemoryRoleProfileRepository([])
        saved = await repository.save(profile("role-profile-a", ROLE_A))
        eligible = saved.model_copy(update={"status": RoleProfileStatus.ACTIVE})
        await repository.replace(eligible)

        activated = await repository.activate_for_role(
            ROLE_A,
            profile_id=eligible.id,
            governance_version=eligible.governance_version,
        )

        assert activated.id == eligible.id
        assert activated.governance_version == 1
        current = await repository.get_active_for_role(ROLE_A)
        assert current is not None
        assert current.id == eligible.id

    asyncio.run(scenario())


def test_older_activation_cannot_regress_newer_active_profile() -> None:
    async def scenario() -> None:
        repository = InMemoryRoleProfileRepository([])
        first = await repository.save(profile("role-profile-a", ROLE_A))
        second = await repository.save(profile("role-profile-b", ROLE_A))
        await repository.replace(first.model_copy(update={"status": RoleProfileStatus.ACTIVE}))
        await repository.replace(second.model_copy(update={"status": RoleProfileStatus.ACTIVE}))

        await repository.activate_for_role(
            ROLE_A,
            profile_id=second.id,
            governance_version=second.governance_version,
        )

        with pytest.raises(ValueError, match="older governance version"):
            await repository.activate_for_role(
                ROLE_A,
                profile_id=first.id,
                governance_version=first.governance_version,
            )

        current = await repository.get_active_for_role(ROLE_A)
        assert current is not None
        assert current.id == second.id

    asyncio.run(scenario())


def test_exact_governance_version_mismatch_fails_closed() -> None:
    async def scenario() -> None:
        repository = InMemoryRoleProfileRepository([])
        saved = await repository.save(profile("role-profile-a", ROLE_A))
        await repository.replace(saved.model_copy(update={"status": RoleProfileStatus.ACTIVE}))

        with pytest.raises(KeyError, match="governance version"):
            await repository.activate_for_role(
                ROLE_A,
                profile_id=saved.id,
                governance_version=99,
            )

    asyncio.run(scenario())
