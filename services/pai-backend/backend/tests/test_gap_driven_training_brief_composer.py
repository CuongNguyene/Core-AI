from uuid import UUID

from app.capability_analysis.schemas import PreliminaryPriority, TargetUsageMode
from app.course_authoring.gap_driven_composer import (
    GapDrivenTrainingBriefComposer,
    ResolutionActionType,
)
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

CANDIDATE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def need(
    *,
    gap_id: str,
    eligibility: LearningNeedEligibility,
    resolution: LearningNeedResolution,
    competency_id: str,
    priority: PreliminaryPriority = PreliminaryPriority.MEDIUM,
    usage_mode: str = "preview",
) -> LearningNeedProfile:
    return LearningNeedProfile(
        id=f"learning-need:analysis-1:{gap_id}",
        candidate_reference=CANDIDATE_ID,
        target_reference="role-1@3",
        learner_context=LearnerContext(role=None, experience_level=None),
        competency=LearningNeedCompetency(id=competency_id, name=None, description=None),
        current_state=LearningNeedCurrentState(level=None, evidence_refs=[f"evidence:{gap_id}"]),
        target_state=LearningNeedTargetState(
            level="3", expected_behaviors=[f"behavior-{gap_id}"]
        ),
        gap=LearningNeedGap(type="skill_gap", description=f"gap-{gap_id}"),
        missing_knowledge=[],
        learning_constraints={},
        priority=priority,
        confidence=None,
        source_gap_refs=[gap_id],
        provenance=LearningNeedProvenance(
            analysis_id="analysis-1",
            analysis_version=2,
            target_id="role-1",
            target_version="3",
            source_profile_id="profile-1",
            source_profile_version=4,
            evidence_refs=[f"evidence:{gap_id}"],
            transformation="learning-need-profile-v1",
        ),
        assessment_status="insufficient",
        requirement_reference=competency_id,
        learning_eligibility=eligibility,
        resolution_type=resolution,
        usage_mode=usage_mode,
        warning_codes=["source_capability_analysis_preview"]
        if usage_mode == "preview"
        else [],
        projection_reason_code="test_reason",
    )


def test_evidence_missing_needs_produce_no_training_brief() -> None:
    result = GapDrivenTrainingBriefComposer().compose(
        [
            need(
                gap_id="gap-a",
                eligibility=LearningNeedEligibility.EVIDENCE_MISSING,
                resolution=LearningNeedResolution.VERIFICATION,
                competency_id="cap-a",
            ),
            need(
                gap_id="gap-b",
                eligibility=LearningNeedEligibility.EVIDENCE_MISSING,
                resolution=LearningNeedResolution.VERIFICATION,
                competency_id="cap-b",
            ),
        ]
    )

    assert result.training_brief is None
    assert result.included_learning_need_refs == ()
    assert len(result.resolution_actions) == 2
    assert result.reason_code == "no_learning_eligible_needs"
    assert all(action.type is ResolutionActionType.VERIFICATION for action in result.resolution_actions)


def test_mixed_needs_only_include_learning_eligible_item() -> None:
    result = GapDrivenTrainingBriefComposer().compose(
        [
            need(
                gap_id="skill",
                eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
                resolution=LearningNeedResolution.LEARNING,
                competency_id="cap-sql",
                priority=PreliminaryPriority.HIGH,
            ),
            need(
                gap_id="education",
                eligibility=LearningNeedEligibility.NEEDS_VERIFICATION,
                resolution=LearningNeedResolution.VERIFICATION,
                competency_id="degree",
            ),
            need(
                gap_id="credential",
                eligibility=LearningNeedEligibility.UNRESOLVED,
                resolution=LearningNeedResolution.CREDENTIAL,
                competency_id="pmp",
            ),
            need(
                gap_id="experience",
                eligibility=LearningNeedEligibility.UNRESOLVED,
                resolution=LearningNeedResolution.EXPERIENCE_EXPOSURE,
                competency_id="production",
            ),
        ]
    )

    assert result.training_brief is not None
    assert result.included_learning_need_refs == ("learning-need:analysis-1:skill",)
    assert len(result.resolution_actions) == 3
    assert result.training_brief.desired_outcomes == ("behavior-skill",)
    assert result.training_brief.language is None
    assert result.training_brief.duration_constraint is None


def test_preview_and_provenance_are_preserved_without_raw_data() -> None:
    result = GapDrivenTrainingBriefComposer().compose(
        [
            need(
                gap_id="sql",
                eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
                resolution=LearningNeedResolution.LEARNING,
                competency_id="cap-sql",
            )
        ]
    )

    assert result.usage_mode is TargetUsageMode.PREVIEW
    assert result.provenance.capability_analysis_reference == "analysis-1@2"
    assert result.provenance.role_profile_reference == "role-1@3"
    assert result.provenance.source_learning_need_refs == (
        "learning-need:analysis-1:sql",
    )
    payload = result.model_dump_json()
    assert "raw CV" not in payload
    assert "provider response" not in payload
    assert "prompt" not in payload


def test_priority_order_is_stable_and_no_dependency_is_invented() -> None:
    result = GapDrivenTrainingBriefComposer().compose(
        [
            need(
                gap_id="preferred",
                eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
                resolution=LearningNeedResolution.LEARNING,
                competency_id="cap-power-bi",
                priority=PreliminaryPriority.LOW,
            ),
            need(
                gap_id="critical",
                eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
                resolution=LearningNeedResolution.LEARNING,
                competency_id="cap-sql",
                priority=PreliminaryPriority.HIGH,
            ),
        ]
    )

    assert result.included_learning_need_refs == (
        "learning-need:analysis-1:critical",
        "learning-need:analysis-1:preferred",
    )
    assert result.provenance.policy_reference == "gap_driven_training_brief@0.1"


def test_composition_is_deterministic() -> None:
    items = [
        need(
            gap_id="b",
            eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
            resolution=LearningNeedResolution.LEARNING,
            competency_id="cap-b",
        ),
        need(
            gap_id="a",
            eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
            resolution=LearningNeedResolution.LEARNING,
            competency_id="cap-a",
        ),
    ]

    first = GapDrivenTrainingBriefComposer().compose(items)
    second = GapDrivenTrainingBriefComposer().compose(items)

    assert first == second
