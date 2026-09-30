import asyncio

import pytest

from app.authorization.fixtures import LEARNER_ID, ORG_PAI_ID
from app.capability_analysis import schemas as capability_schemas
from app.capability_analysis.repository import InMemoryCapabilityGapPortfolioRepository
from app.capability_analysis.schemas import (
    AssessmentEvidenceStatus,
    CombinedGapPortfolio,
    PreliminaryPriority,
    RequirementAssessment,
    TargetGap,
    TargetGapAnalysis,
    TargetType,
    TargetUsageMode,
    VerificationQueueItem,
    VerificationQueueStatus,
)


def legacy_portfolio() -> CombinedGapPortfolio:
    gap = TargetGap(
        id="current-python-gap",
        target_id="role-current",
        target_type=TargetType.CURRENT_ROLE,
        requirement_id="python",
        matched_evidence_refs=["evidence-python"],
        missing_signals=["Production evidence is required."],
        rationale="Python production evidence is not sufficient.",
        preliminary_priority=PreliminaryPriority.HIGH,
        missing_priority_inputs=["business_impact"],
        overlap_keys=["python"],
        decision_details={
            "reason_codes": ["production_evidence_missing"],
            "supported_signals": ["Python"],
            "missing_signals": ["production"],
            "observed_confidence": 0.6,
            "required_confidence": 0.8,
            "evidence_directness": "project",
            "verification_required": True,
            "threshold_source": "role-policy",
            "threshold_policy_id": "policy-python",
            "threshold_policy_version": "1",
        },
        recommendation="practical_task",
    )
    assessment = RequirementAssessment(**gap.model_dump(exclude={"id", "overlap_keys"}))
    return CombinedGapPortfolio(
        id="portfolio-canonical-roundtrip",
        cv_profile_id="accepted-cv-1",
        cv_profile_version=2,
        current_target_version="1.0",
        owner_actor_id=LEARNER_ID,
        organization_id=ORG_PAI_ID,
        correlation_id="portfolio-canonical-roundtrip",
        current_role=TargetGapAnalysis(
            target_id="role-current",
            target_type=TargetType.CURRENT_ROLE,
            usage_mode=TargetUsageMode.OFFICIAL,
            assessments=[assessment],
            gaps=[gap],
        ),
    )


def test_canonical_profile_round_trips_existing_portfolio_without_semantic_loss() -> None:
    legacy = legacy_portfolio()

    restored = (
        capability_schemas.CapabilityGapProfile.from_combined_gap_portfolio(legacy)
        .to_combined_gap_portfolio()
    )

    assert restored == legacy


def test_target_gap_projection_preserves_stable_identity_and_evidence_contract() -> None:
    profile = capability_schemas.CapabilityGapProfile.from_combined_gap_portfolio(legacy_portfolio())

    projected_gap = profile.to_combined_gap_portfolio().current_role.gaps[0]

    assert projected_gap.id == "current-python-gap"
    assert projected_gap.matched_evidence_refs == ["evidence-python"]
    assert projected_gap.evidence_status.value == "not_found_in_evidence"
    assert projected_gap.preliminary_priority.value == "high"
    assert projected_gap.decision_details.reason_codes == ["production_evidence_missing"]
    assert projected_gap.decision_details.threshold_policy_id == "policy-python"


def test_canonical_profile_adaptation_is_a_pure_projection_not_another_analysis_pass() -> None:
    legacy = legacy_portfolio()

    profile = capability_schemas.CapabilityGapProfile.from_combined_gap_portfolio(legacy)

    assert profile.id == legacy.id
    assert profile.current_role.entries[0].requirement_id == "python"
    assert len(profile.current_role.entries) == 1


def test_canonical_profile_fails_closed_when_legacy_gap_has_no_requirement_assessment() -> None:
    legacy = legacy_portfolio().model_copy(
        update={
            "current_role": legacy_portfolio().current_role.model_copy(
                update={"assessments": []}
            )
        }
    )

    with pytest.raises(ValueError, match="gap without requirement assessment"):
        capability_schemas.CapabilityGapProfile.from_combined_gap_portfolio(legacy)


def test_canonical_profile_preserves_historical_preview_verification_queue() -> None:
    legacy = legacy_portfolio().model_copy(
        update={
            "current_role": legacy_portfolio().current_role.model_copy(
                update={
                    "usage_mode": TargetUsageMode.PREVIEW,
                    "warning_codes": ["current_target_profile_provisional"],
                }
            ),
            "snapshot_schema_version": "capability-gap-preview-v1",
            "preview_readiness": None,
            "verification_queue": [
                VerificationQueueItem(
                    requirement_id="python",
                    target_type=TargetType.CURRENT_ROLE,
                    evidence_status=AssessmentEvidenceStatus.REQUIRES_VERIFICATION,
                    status=VerificationQueueStatus.RECOMMENDED,
                    evidence_refs=("evidence-python",),
                )
            ],
        }
    )

    projected = capability_schemas.CapabilityGapProfile.from_combined_gap_portfolio(
        legacy
    ).to_combined_gap_portfolio()

    assert projected.preview_readiness is None
    assert projected.verification_queue == legacy.verification_queue


def test_repository_persists_canonical_profile_and_returns_the_same_legacy_projection() -> None:
    repository = InMemoryCapabilityGapPortfolioRepository()
    profile = capability_schemas.CapabilityGapProfile.from_combined_gap_portfolio(legacy_portfolio())

    async def persist() -> tuple[object, object]:
        return await repository.create_profile(profile), await repository.get_profile(profile.id)

    saved, restored = asyncio.run(persist())

    assert saved == profile
    assert restored == profile
    assert restored is not None
    assert restored.to_combined_gap_portfolio() == legacy_portfolio()
