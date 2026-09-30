import pytest

from app.authorization.fixtures import LEARNER_ID, ORG_PAI_ID
from app.capability_analysis.repository import InMemoryCapabilityGapPortfolioRepository
from app.capability_analysis.schemas import (
    CombinedGapPortfolio,
    GapOverlapLink,
    PreliminaryPriority,
    RequirementAssessment,
    TargetGap,
    TargetGapAnalysis,
    TargetType,
    TargetUsageMode,
)
from app.matching.repository import InMemoryRoleProfileRepository
from app.matching.schemas import RoleProfileStatus
from tests.test_matching_repository import active_role


def portfolio() -> CombinedGapPortfolio:
    current_gap = TargetGap(
        id="current-python-gap",
        target_id="role-current",
        target_type=TargetType.CURRENT_ROLE,
        requirement_id="python",
        matched_evidence_refs=["evidence-python"],
        missing_signals=["Evidence is below the target confidence threshold."],
        rationale="Current role Python requires a provisional gap.",
        preliminary_priority=PreliminaryPriority.HIGH,
        missing_priority_inputs=["business_impact"],
        overlap_keys=["python"],
    )
    future_gap = current_gap.model_copy(
        update={
            "id": "future-python-gap",
            "target_id": "role-future",
            "target_type": TargetType.FUTURE_ROLE,
            "rationale": "Future role Python requires a provisional gap.",
        }
    )
    current_assessment = RequirementAssessment(
        **current_gap.model_dump(exclude={"id", "overlap_keys"})
    )
    future_assessment = RequirementAssessment(
        **future_gap.model_dump(exclude={"id", "overlap_keys"})
    )
    return CombinedGapPortfolio(
        id="portfolio-1",
        cv_profile_id="accepted-cv-1",
        cv_profile_version=3,
        current_target_version="2.1",
        future_target_version="1.4",
        owner_actor_id=LEARNER_ID,
        organization_id=ORG_PAI_ID,
        correlation_id="capability-correlation-1",
        current_role=TargetGapAnalysis(
            target_id="role-current",
            target_type=TargetType.CURRENT_ROLE,
            usage_mode=TargetUsageMode.OFFICIAL,
            assessments=[current_assessment],
            gaps=[current_gap],
        ),
        future_role=TargetGapAnalysis(
            target_id="role-future",
            target_type=TargetType.FUTURE_ROLE,
            usage_mode=TargetUsageMode.PREVIEW,
            assessments=[future_assessment],
            gaps=[future_gap],
            warning_codes=["future_target_profile_provisional"],
        ),
        overlap_links=[
            GapOverlapLink(
                source_gap_id=current_gap.id,
                target_gap_id=future_gap.id,
                shared_theme="python",
            )
        ],
    )


@pytest.mark.asyncio
async def test_target_resolver_prefers_active_target_over_provisional() -> None:
    provisional = active_role().model_copy(
        update={"version": "0.9", "status": RoleProfileStatus.PROVISIONAL}
    )
    active = active_role().model_copy(update={"version": "1.0"})
    roles = InMemoryRoleProfileRepository([provisional, active])

    target = await roles.get_preferred_target("role-ai-engineer")

    assert target is not None
    assert target.status is RoleProfileStatus.ACTIVE
    assert target.version == "1.0"


@pytest.mark.asyncio
async def test_portfolio_is_immutable_and_preserves_separate_target_gaps() -> None:
    repository = InMemoryCapabilityGapPortfolioRepository()
    saved = await repository.create(portfolio())

    restored = await repository.get(saved.id)

    assert restored == saved
    assert restored is not None
    assert restored.current_role.gaps[0].id != restored.future_role.gaps[0].id  # type: ignore[union-attr]
    assert len(restored.overlap_links) == 1
    with pytest.raises(ValueError, match="immutable"):
        await repository.create(saved)
