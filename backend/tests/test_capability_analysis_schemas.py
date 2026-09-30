import pytest
from pydantic import ValidationError

from app.authorization.fixtures import LEARNER_ID, ORG_PAI_ID
from app.capability_analysis.domain_packs.contracts import DomainPackReference
from app.capability_analysis.schemas import (
    CapabilityEvidenceStatus,
    CapabilityObservation,
    CombinedGapPortfolio,
    CreateCapabilityGapAnalysisRequest,
    GapOverlapLink,
    PreliminaryPriority,
    ProvisionalCapability,
    ProvisionalCurrentCapabilityProfile,
    RequirementAssessment,
    TargetGap,
    TargetGapAnalysis,
    TargetSemanticPolicySnapshot,
    TargetType,
    TargetUsageMode,
    VerificationStatus,
)
from app.extraction.locators import SourceLocator
from app.matching.schemas import SemanticPolicySelectionSource


def observation_with_environment_and_context() -> CapabilityObservation:
    return CapabilityObservation(
        evidence_ref="evidence-python-1",
        source_locator=SourceLocator(
            document_id="cv-document-1",
            section="experience",
            start_offset=10,
            end_offset=42,
        ),
        environment="production",
        context="used_in_production",
        participation="implemented API integrations",
        confidence=0.9,
    )


def target_gap(target_type: TargetType, target_id: str | None = None) -> TargetGap:
    resolved_target_id = target_id or (
        "role-current" if target_type is TargetType.CURRENT_ROLE else "role-future"
    )
    return TargetGap(
        id=f"gap-{target_type}",
        target_id=resolved_target_id,
        target_type=target_type,
        requirement_id="python",
        matched_evidence_refs=["evidence-python-1"],
        missing_signals=["independent depth cannot be established"],
        rationale="Evidence is source-backed but requires assessment.",
        preliminary_priority=PreliminaryPriority.HIGH,
        missing_priority_inputs=[
            "business_impact",
            "risk",
            "frequency",
            "deadline",
            "manager_confirmation",
        ],
    )


def target_analysis(target_type: TargetType, target_id: str | None = None) -> TargetGapAnalysis:
    gap = target_gap(target_type, target_id)
    assessment = RequirementAssessment(
        target_id=gap.target_id,
        target_type=gap.target_type,
        requirement_id=gap.requirement_id,
        matched_evidence_refs=gap.matched_evidence_refs,
        missing_signals=gap.missing_signals,
        rationale=gap.rationale,
        preliminary_priority=gap.preliminary_priority,
        missing_priority_inputs=gap.missing_priority_inputs,
    )
    return TargetGapAnalysis(
        target_id=gap.target_id,
        target_type=target_type,
        usage_mode=TargetUsageMode.OFFICIAL,
        assessments=[assessment],
        gaps=[gap],
    )


def semantic_policy(
    target_type: TargetType,
    *,
    target_id: str | None = None,
    target_version: str = "1.0",
) -> TargetSemanticPolicySnapshot:
    return TargetSemanticPolicySnapshot(
        target_id=target_id
        or ("role-current" if target_type is TargetType.CURRENT_ROLE else "role-future"),
        target_version=target_version,
        target_type=target_type,
        core_version="semantic-core-v1",
        pack_refs=(DomainPackReference(pack_id="it_ai", version="1"),),
        selection_source=SemanticPolicySelectionSource.PROFILE_METADATA,
    )


def test_provisional_capability_requires_source_context_and_provisional_verification() -> None:
    capability = ProvisionalCapability(
        capability_id="python",
        status=CapabilityEvidenceStatus.SUPPORTED,
        verification_status=VerificationStatus.PROVISIONAL,
        observations=[observation_with_environment_and_context()],
    )

    assert capability.observations[0].environment == "production"

    with pytest.raises(ValidationError):
        ProvisionalCapability(
            capability_id="python",
            status=CapabilityEvidenceStatus.SUPPORTED,
            verification_status="verified",
            observations=[observation_with_environment_and_context()],
        )

    with pytest.raises(ValidationError):
        CapabilityObservation(
            evidence_ref="evidence-python-1",
            source_locator=SourceLocator(
                document_id="cv-document-1",
                section="experience",
                start_offset=10,
                end_offset=42,
            ),
            environment="production",
            context="used_in_production",
            confidence=0.9,
        )


def test_provisional_current_capability_profile_is_immutable_and_source_referenced() -> None:
    snapshot = ProvisionalCurrentCapabilityProfile(
        source_profile_id="accepted-cv-profile-1",
        source_profile_version=2,
        capabilities=[
            ProvisionalCapability(
                capability_id="python",
                status=CapabilityEvidenceStatus.SUPPORTED,
                verification_status=VerificationStatus.PROVISIONAL,
                observations=[observation_with_environment_and_context()],
            )
        ],
    )

    assert snapshot.source_profile_id == "accepted-cv-profile-1"
    assert snapshot.capabilities[0].verification_status is VerificationStatus.PROVISIONAL

    with pytest.raises(ValidationError):
        ProvisionalCurrentCapabilityProfile(
            source_profile_id="accepted-cv-profile-1",
            source_profile_version=2,
            capabilities=[],
        )

    with pytest.raises(ValidationError):
        snapshot.source_profile_id = "other-profile"


def test_provisional_capability_snapshot_is_deeply_immutable() -> None:
    snapshot = ProvisionalCurrentCapabilityProfile(
        source_profile_id="accepted-cv-profile-1",
        source_profile_version=2,
        capabilities=[
            ProvisionalCapability(
                capability_id="python",
                status=CapabilityEvidenceStatus.SUPPORTED,
                verification_status=VerificationStatus.PROVISIONAL,
                observations=[observation_with_environment_and_context()],
            )
        ],
    )

    with pytest.raises(AttributeError):
        snapshot.capabilities.append(snapshot.capabilities[0])

    with pytest.raises(ValidationError):
        snapshot.capabilities[0].capability_id = "java"

    with pytest.raises(AttributeError):
        snapshot.capabilities[0].observations.append(observation_with_environment_and_context())

    with pytest.raises(ValidationError):
        snapshot.capabilities[0].observations[0].environment = "staging"

    with pytest.raises(ValidationError):
        snapshot.capabilities[0].observations[0].source_locator.document_id = "other-cv"


def test_gap_is_target_aware_and_priority_records_missing_inputs() -> None:
    gap = target_gap(TargetType.CURRENT_ROLE)

    assert gap.target_id == "role-current"
    assert gap.missing_priority_inputs == [
        "business_impact",
        "risk",
        "frequency",
        "deadline",
        "manager_confirmation",
    ]

    with pytest.raises(ValidationError):
        TargetGap(
            id="gap-missing-target",
            requirement_id="python",
            matched_evidence_refs=[],
            missing_signals=["evidence not found"],
            rationale="No source-backed evidence matched.",
            preliminary_priority=PreliminaryPriority.HIGH,
            missing_priority_inputs=[],
        )


def test_combined_portfolio_keeps_target_tracks_separate_without_readiness_score() -> None:
    current = target_analysis(TargetType.CURRENT_ROLE)
    future = target_analysis(TargetType.FUTURE_ROLE)
    portfolio = CombinedGapPortfolio(
        id="portfolio-1",
        cv_profile_id="cv-profile-1",
        cv_profile_version=1,
        current_target_version="1.0",
        future_target_version="1.0",
        owner_actor_id=LEARNER_ID,
        organization_id=ORG_PAI_ID,
        correlation_id="correlation-1",
        current_role=current,
        future_role=future,
        overlap_links=[
            GapOverlapLink(
                source_gap_id=current.gaps[0].id,
                target_gap_id=future.gaps[0].id,
                shared_theme="python",
            )
        ],
    )

    assert portfolio.future_role is not None
    assert not hasattr(portfolio, "readiness_score")


def test_portfolio_semantic_policy_tracks_must_match_analysis_tracks_exactly() -> None:
    current = target_analysis(TargetType.CURRENT_ROLE)
    future = target_analysis(TargetType.FUTURE_ROLE)
    base = {
        "id": "portfolio-policy",
        "cv_profile_id": "cv-profile-1",
        "cv_profile_version": 1,
        "current_target_version": "1.0",
        "future_target_version": "1.0",
        "owner_actor_id": LEARNER_ID,
        "organization_id": ORG_PAI_ID,
        "correlation_id": "correlation-policy",
        "current_role": current,
        "future_role": future,
    }
    valid = (
        semantic_policy(TargetType.CURRENT_ROLE),
        semantic_policy(TargetType.FUTURE_ROLE),
    )

    assert CombinedGapPortfolio(**base, semantic_policies=valid).semantic_policies == valid
    for invalid in (
        (),
        (valid[0],),
        (valid[0], valid[0], valid[1]),
        (valid[0].model_copy(update={"target_id": "wrong"}), valid[1]),
        (valid[0].model_copy(update={"target_version": "wrong"}), valid[1]),
        (valid[0].model_copy(update={"target_type": TargetType.FUTURE_ROLE}), valid[1]),
    ):
        if invalid == ():
            # Empty is the explicit compatibility form for historical portfolios.
            assert CombinedGapPortfolio(**base, semantic_policies=invalid).semantic_policies == ()
            continue
        with pytest.raises(ValidationError):
            CombinedGapPortfolio(**base, semantic_policies=invalid)


def test_portfolio_rejects_future_policy_without_future_track() -> None:
    current = target_analysis(TargetType.CURRENT_ROLE)
    with pytest.raises(ValidationError):
        CombinedGapPortfolio(
            id="portfolio-extra-future-policy",
            cv_profile_id="cv-profile-1",
            cv_profile_version=1,
            current_target_version="1.0",
            owner_actor_id=LEARNER_ID,
            organization_id=ORG_PAI_ID,
            correlation_id="correlation-extra-future",
            current_role=current,
            semantic_policies=(
                semantic_policy(TargetType.CURRENT_ROLE),
                semantic_policy(TargetType.FUTURE_ROLE),
            ),
        )


def test_target_analysis_rejects_assessments_and_gaps_from_another_target() -> None:
    current = target_analysis(TargetType.CURRENT_ROLE)
    future = target_analysis(TargetType.FUTURE_ROLE)

    with pytest.raises(ValidationError):
        TargetGapAnalysis(
            **current.model_dump(exclude={"assessments"}),
            assessments=[future.assessments[0]],
        )

    with pytest.raises(ValidationError):
        TargetGapAnalysis(
            **current.model_dump(exclude={"assessments"}),
            assessments=[current.assessments[0].model_copy(update={"target_id": "role-other"})],
        )

    with pytest.raises(ValidationError):
        TargetGapAnalysis(
            **current.model_dump(exclude={"gaps"}),
            gaps=[future.gaps[0]],
        )

    with pytest.raises(ValidationError):
        TargetGapAnalysis(
            **current.model_dump(exclude={"gaps"}),
            gaps=[current.gaps[0].model_copy(update={"target_id": "role-other"})],
        )


def test_combined_portfolio_requires_current_and_future_track_types() -> None:
    current = target_analysis(TargetType.CURRENT_ROLE)
    future = target_analysis(TargetType.FUTURE_ROLE)

    with pytest.raises(ValidationError):
        CombinedGapPortfolio(
            id="portfolio-current-wrong-type",
            cv_profile_id="cv-profile-1",
            cv_profile_version=1,
            current_target_version="1.0",
            owner_actor_id=LEARNER_ID,
            organization_id=ORG_PAI_ID,
            correlation_id="correlation-1",
            current_role=future,
            overlap_links=[],
        )

    with pytest.raises(ValidationError):
        CombinedGapPortfolio(
            id="portfolio-future-wrong-type",
            cv_profile_id="cv-profile-1",
            cv_profile_version=1,
            current_target_version="1.0",
            future_target_version="1.0",
            owner_actor_id=LEARNER_ID,
            organization_id=ORG_PAI_ID,
            correlation_id="correlation-1",
            current_role=current,
            future_role=current,
            overlap_links=[],
        )


def test_create_request_accepts_managed_ids_only() -> None:
    request = CreateCapabilityGapAnalysisRequest(
        cv_profile_id="cv-profile-1",
        current_target_profile_id="role-current",
        future_target_profile_id="role-future",
        correlation_id="correlation-1",
    )

    assert request.current_target_profile_id == "role-current"

    with pytest.raises(ValidationError):
        CreateCapabilityGapAnalysisRequest(
            cv_profile_id="cv-profile-1",
            current_target_profile_id="role-current",
            correlation_id="correlation-1",
            candidate_profile={"skills": []},
        )
