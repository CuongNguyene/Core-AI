from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.authorization.schemas import ActorContext, Role
from app.candidate.schemas import Candidate, CandidateReviewState, CandidateStatus
from app.capability_analysis.service import CapabilityGapAnalysisService
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)
from app.role_registry.schemas import Role as RoleRecord

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
ACTOR_ID = UUID("00000000-0000-0000-0000-000000000004")
CANDIDATE_ID = UUID("11111111-1111-4111-8111-111111111111")
ROLE_ID = UUID("22222222-2222-4222-8222-222222222222")


def actor() -> ActorContext:
    return ActorContext(
        actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        roles=frozenset({Role.REVIEWER}),
    )


def role() -> RoleRecord:
    return RoleRecord(
        id=ROLE_ID,
        organization_id=ORG_ID,
        role_code="ROLE-000001",
        title="Head of Project",
        created_by=ACTOR_ID,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        active_role_profile_id="role-profile-2",
    )


def profile(status: RoleProfileStatus = RoleProfileStatus.ACTIVE) -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id="role-profile-2",
        version="7",
        status=status,
        source_jd_profile_id="jd-profile-1",
        source_jd_profile_version=1,
        rule_set_version="rules@1",
        policy_version="policy@1",
        requirements=[
            RoleRequirement(
                id="req-1",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.ROLE_CRITICAL,
                evidence_terms=["project delivery"],
                confidence_threshold=0.7,
                assessment_recommendation="review evidence",
                rubric_version="rubric@1",
            )
        ],
        role_id=ROLE_ID,
        governance_version=2,
    )


def service() -> CapabilityGapAnalysisService:
    instance = CapabilityGapAnalysisService(
        extraction_profiles=AsyncMock(),
        role_profiles=AsyncMock(),
        portfolios=AsyncMock(),
        candidates=AsyncMock(),
        domain_pack_registry=AsyncMock(),
        role_registry=AsyncMock(),
    )
    instance._candidates.get = AsyncMock(return_value=Candidate(
        candidate_id=CANDIDATE_ID,
        candidate_code="CAN-000001",
        organization_id=ORG_ID,
        created_by_actor_id=ACTOR_ID,
        status=CandidateStatus.ACTIVE,
        review_state=CandidateReviewState.ACCEPTED,
        current_profile_id="cv-profile-1",
        current_profile_version=1,
    ))
    return instance


@pytest.mark.asyncio
async def test_product_adapter_resolves_exact_current_and_active_snapshots() -> None:
    instance = service()
    instance._role_registry.get_role = AsyncMock(return_value=role())
    instance._role_profiles.get_active_for_role = AsyncMock(return_value=profile())
    expected = object()
    instance.create_for_candidate = AsyncMock(return_value=expected)

    result = await instance.create_for_candidate_role(
        candidate_id=CANDIDATE_ID,
        role_id=ROLE_ID,
        idempotency_key="analysis-key-1",
        actor=actor(),
    )

    assert result.portfolio is expected
    assert result.candidate.candidate_id == CANDIDATE_ID
    assert result.role_profile.id == "role-profile-2"
    instance.create_for_candidate.assert_awaited_once_with(
        candidate_id=CANDIDATE_ID,
        current_target_reference="role-profile-2@7",
        future_target_reference=None,
        idempotency_key="analysis-key-1",
        actor=actor(),
    )


@pytest.mark.asyncio
async def test_product_adapter_blocks_role_without_active_profile() -> None:
    instance = service()
    instance._role_registry.get_role = AsyncMock(return_value=role().model_copy(update={"active_role_profile_id": None}))
    instance.create_for_candidate = AsyncMock()

    with pytest.raises(ValueError, match="role_profile_not_active"):
        await instance.create_for_candidate_role(
            candidate_id=CANDIDATE_ID,
            role_id=ROLE_ID,
            idempotency_key="analysis-key-2",
            actor=actor(),
        )

    instance.create_for_candidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_product_adapter_blocks_role_outside_actor_organization() -> None:
    instance = service()
    instance._role_registry.get_role = AsyncMock(return_value=None)
    instance.create_for_candidate = AsyncMock()

    with pytest.raises(ValueError, match="role_not_found"):
        await instance.create_for_candidate_role(
            candidate_id=CANDIDATE_ID,
            role_id=ROLE_ID,
            idempotency_key="analysis-key-3",
            actor=actor(),
        )

    instance.create_for_candidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_product_adapter_blocks_candidate_without_current_profile() -> None:
    instance = service()
    instance._candidates.get = AsyncMock(return_value=Candidate(
        candidate_id=CANDIDATE_ID,
        candidate_code="CAN-000001",
        organization_id=ORG_ID,
        created_by_actor_id=ACTOR_ID,
        status=CandidateStatus.ACTIVE,
        review_state=CandidateReviewState.PENDING_REVIEW,
        current_profile_id=None,
        current_profile_version=None,
    ))
    instance._role_registry.get_role = AsyncMock(return_value=role())
    instance._role_profiles.get_active_for_role = AsyncMock(return_value=profile())
    instance.create_for_candidate = AsyncMock()

    with pytest.raises(ValueError, match="candidate_profile_not_ready"):
        await instance.create_for_candidate_role(
            candidate_id=CANDIDATE_ID,
            role_id=ROLE_ID,
            idempotency_key="analysis-key-4",
            actor=actor(),
        )

    instance.create_for_candidate.assert_not_awaited()
