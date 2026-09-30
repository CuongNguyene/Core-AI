from uuid import UUID

from app.capability_analysis.schemas import PreliminaryPriority, TargetUsageMode
from app.course_authoring.learning_readiness import build_learning_readiness_projection
from app.learning_need_profile.schemas import (
    LearnerContext,
    LearningNeedCompetency,
    LearningNeedCurrentState,
    LearningNeedEligibility,
    LearningNeedGap,
    LearningNeedProfile,
    LearningNeedProvenance,
    LearningNeedResolution,
    LearningNeedTargetState,
)


def learning_need(
    ref: str,
    *,
    eligibility: LearningNeedEligibility,
    resolution: LearningNeedResolution,
) -> LearningNeedProfile:
    return LearningNeedProfile(
        id=ref,
        candidate_reference=UUID("00000000-0000-0000-0000-000000000001"),
        target_reference="role-profile-1@1",
        learner_context=LearnerContext(role=None, experience_level=None),
        competency=LearningNeedCompetency(id=ref, name=ref, description=None),
        current_state=LearningNeedCurrentState(level=None, evidence_refs=[]),
        target_state=LearningNeedTargetState(level="1", expected_behaviors=[f"Do {ref}"]),
        gap=LearningNeedGap(type="skill_gap", description=f"Gap for {ref}"),
        missing_knowledge=[],
        learning_constraints={},
        priority=PreliminaryPriority.MEDIUM,
        confidence=0.8,
        source_gap_refs=[f"gap:{ref}"],
        provenance=LearningNeedProvenance(
            analysis_id="analysis-1",
            analysis_version=1,
            target_id="role-profile-1",
            target_version="1",
            source_profile_id="cv-1",
            source_profile_version=1,
            evidence_refs=[],
            transformation="learning-need-profile-v1",
        ),
        learning_eligibility=eligibility,
        resolution_type=resolution,
        usage_mode=TargetUsageMode.PREVIEW.value,
    )


def test_zero_eligible_needs_blocks_generation_and_preserves_excluded_actions() -> None:
    needs = [
        learning_need(
            "need-evidence",
            eligibility=LearningNeedEligibility.EVIDENCE_MISSING,
            resolution=LearningNeedResolution.VERIFICATION,
        ),
        learning_need(
            "need-verification",
            eligibility=LearningNeedEligibility.NEEDS_VERIFICATION,
            resolution=LearningNeedResolution.VERIFICATION,
        ),
    ]

    projection = build_learning_readiness_projection(needs)

    assert projection.ready_for_learning_count == 0
    assert projection.generation_allowed is False
    assert projection.generation_block_reason == "no_learning_eligible_needs"
    assert projection.included_learning_need_refs == ()
    assert len(projection.resolution_actions) == 2
    assert projection.usage_mode == "preview"
    assert projection.training_brief is None


def test_positive_projection_includes_only_learning_eligible_needs() -> None:
    needs = [
        learning_need(
            "need-sql",
            eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
            resolution=LearningNeedResolution.LEARNING,
        ),
        learning_need(
            "need-rest",
            eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
            resolution=LearningNeedResolution.LEARNING,
        ),
        learning_need(
            "need-degree",
            eligibility=LearningNeedEligibility.UNRESOLVED,
            resolution=LearningNeedResolution.VERIFICATION,
        ),
    ]

    projection = build_learning_readiness_projection(needs)

    assert projection.ready_for_learning_count == 2
    assert projection.generation_allowed is True
    assert projection.generation_block_reason is None
    assert projection.included_learning_need_refs == ("need-rest", "need-sql")
    assert [item.source_learning_need_ref for item in projection.resolution_actions] == ["need-degree"]
    assert projection.training_brief is not None
    assert projection.usage_mode == "preview"


def test_positive_projection_exposes_only_included_learning_item_details() -> None:
    eligible = learning_need(
        "learning-need:analysis-1:gap-python",
        eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
        resolution=LearningNeedResolution.LEARNING,
    ).model_copy(
        update={
            "competency": LearningNeedCompetency(
                id="req-16", name="Python", description=None
            ),
            "requirement_reference": "req-16",
            "assessment_status": "INSUFFICIENT",
        }
    )
    excluded = learning_need(
        "learning-need:analysis-1:gap-degree",
        eligibility=LearningNeedEligibility.UNRESOLVED,
        resolution=LearningNeedResolution.VERIFICATION,
    ).model_copy(
        update={
            "competency": LearningNeedCompetency(
                id="req-14", name="Degree", description=None
            ),
            "requirement_reference": "req-14",
            "assessment_status": "INSUFFICIENT",
        }
    )

    projection = build_learning_readiness_projection([eligible, excluded])

    assert [item.model_dump(mode="json") for item in projection.included_learning_items] == [
        {
            "learning_need_ref": "learning-need:analysis-1:gap-python",
            "requirement_ref": "req-16",
            "label": "Python",
            "assessment_status": "INSUFFICIENT",
            "resolution_type": "learning",
        }
    ]


def test_blocked_projection_has_no_included_learning_items() -> None:
    projection = build_learning_readiness_projection(
        [
            learning_need(
                "learning-need:analysis-1:gap-missing",
                eligibility=LearningNeedEligibility.EVIDENCE_MISSING,
                resolution=LearningNeedResolution.VERIFICATION,
            )
        ]
    )

    assert projection.included_learning_items == ()
