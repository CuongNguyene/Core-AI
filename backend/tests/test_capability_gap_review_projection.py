import pytest

from app.capability_analysis.review_projection import build_capability_gap_review_projection
from app.capability_analysis.schemas import (
    AssessmentDecisionDetails,
    AssessmentEvidenceStatus,
    PreviewReadiness,
    TargetUsageMode,
)
from app.matching.schemas import CriterionDimension, RequirementClassification, RoleRequirement
from tests.test_capability_gap_profile import legacy_portfolio


def test_review_projection_is_assessment_centered_and_preserves_preview_governance() -> None:
    portfolio = legacy_portfolio().model_copy(
        update={
            "snapshot_schema_version": "capability-gap-preview-v1",
            "preview_readiness": PreviewReadiness(),
            "current_role": legacy_portfolio().current_role.model_copy(
                update={
                    "usage_mode": TargetUsageMode.PREVIEW,
                    "warning_codes": ["current_target_profile_provisional"],
                    "assessments": [
                        legacy_portfolio().current_role.assessments[0].model_copy(
                            update={
                                "evidence_status": AssessmentEvidenceStatus.REQUIRES_VERIFICATION,
                                "decision_details": AssessmentDecisionDetails(
                                    reason_codes=["explicit_mention_only"],
                                    supported_signals=["Python"],
                                    missing_signals=["work evidence"],
                                    observed_confidence=0.6,
                                    required_confidence=0.8,
                                    verification_required=True,
                                ),
                            }
                        )
                    ],
                }
            ),
        }
    )
    role = type("Role", (), {})()
    role.id = "role-current"
    role.version = "1.0"
    role.status = type("Status", (), {"value": "provisional"})()
    role.requirements = [
        RoleRequirement(
            id="python",
            criterion_dimension=CriterionDimension.SKILL,
            classification=RequirementClassification.ROLE_CRITICAL,
            evidence_terms=["Python"],
            modality="must",
            priority="high",
            target_level="production",
            observable_behaviors=["Build Python services"],
            confidence_threshold=0.8,
            assessment_recommendation="practical_task",
            rubric_version="rubric-v1",
            source_requirement_ref="jd-requirement:python",
        )
    ]

    projection = build_capability_gap_review_projection(portfolio, role, {})

    assert len(projection.assessments) == 1
    item = projection.assessments[0]
    assert item.requirement.statement == "Python"
    assert item.requirement.criterion_dimension == "skill"
    assert item.requirement.modality == "must"
    assert item.status == "requires_verification"
    assert item.decision.reason_codes == ["explicit_mention_only"]
    assert item.verification.required is True
    assert projection.summary.total_assessments == 1
    assert projection.summary.requires_verification == 1
    assert projection.usage_mode == "preview"
    assert projection.warnings == ["current_target_profile_provisional"]
    assert projection.preview_readiness is not None
    assert projection.learning_readiness.ready_for_learning_count == 0
    assert projection.learning_readiness.generation_allowed is False
    assert projection.learning_readiness.generation_block_reason == "no_learning_eligible_needs"
    assert not hasattr(projection, "official_score")


def test_review_projection_does_not_fabricate_evidence_or_expose_raw_profile() -> None:
    portfolio = legacy_portfolio()
    role = type("Role", (), {})()
    role.id = "role-current"
    role.version = "1.0"
    role.status = type("Status", (), {"value": "active"})()
    role.requirements = [
        RoleRequirement(
            id="python",
            criterion_dimension=CriterionDimension.SKILL,
            classification=RequirementClassification.ROLE_CRITICAL,
            evidence_terms=["Python"],
            confidence_threshold=0.8,
            assessment_recommendation="review",
            rubric_version="rubric-v1",
        )
    ]

    projection = build_capability_gap_review_projection(portfolio, role, {})

    assert projection.assessments[0].candidate_evidence == []
    serialized = str(projection.model_dump(mode="json"))
    assert "raw_cv" not in serialized
    assert "prompt" not in serialized


def test_review_projection_fails_closed_for_a_different_role_profile_version() -> None:
    portfolio = legacy_portfolio()
    role = type("Role", (), {})()
    role.id = "role-other"
    role.version = "9.0"
    role.status = type("Status", (), {"value": "active"})()
    role.requirements = []

    with pytest.raises(ValueError, match="analyzed role profile version"):
        build_capability_gap_review_projection(portfolio, role, {})
