from uuid import UUID

import pytest

from app.capability_analysis.schemas import (
    AnalysisStatus,
    AssessmentEvidenceStatus,
    CombinedGapPortfolio,
    PreliminaryPriority,
    TargetGap,
    TargetGapAnalysis,
    TargetType,
    TargetUsageMode,
)
from app.learning_need_profile.mapper import map_target_gap_to_learning_need
from app.learning_need_profile.schemas import LearningNeedProfile
from app.matching.schemas import CriterionDimension, RequirementClassification, RoleRequirement

CANDIDATE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ACTOR_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ORG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def requirement() -> RoleRequirement:
    return RoleRequirement(
        id="cap-python-cleaning",
        criterion_dimension=CriterionDimension.SKILL,
        classification=RequirementClassification.TRAINABLE_MANDATORY,
        evidence_terms=["Python data cleaning"],
        confidence_threshold=0.8,
        assessment_recommendation="Practice handling invalid tabular values with Python.",
        rubric_version="rubric-v1",
        target_level="3",
        observable_behaviors=["Handle invalid values in tabular data"],
    )


def gap() -> TargetGap:
    return TargetGap(
        id="gap-python-cleaning",
        target_id="role-data-analyst",
        target_type=TargetType.CURRENT_ROLE,
        requirement_id="cap-python-cleaning",
        matched_evidence_refs=["evidence:cv:page-2"],
        missing_signals=["data_cleaning_depth"],
        rationale="The profile shows Python usage but not structured data cleaning.",
        preliminary_priority=PreliminaryPriority.HIGH,
        missing_priority_inputs=[],
        evidence_status=AssessmentEvidenceStatus.INSUFFICIENT,
    )


def portfolio(source_gap: TargetGap | None = None) -> CombinedGapPortfolio:
    source_gap = source_gap or gap()
    return CombinedGapPortfolio(
        id="analysis-001",
        cv_profile_id="profile-001",
        cv_profile_version=4,
        current_target_version="2",
        owner_actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        correlation_id="correlation-001",
        candidate_id=CANDIDATE_ID,
        analysis_status=AnalysisStatus.READY,
        current_role=TargetGapAnalysis(
            target_id="role-data-analyst",
            target_type=TargetType.CURRENT_ROLE,
            usage_mode=TargetUsageMode.OFFICIAL,
            assessments=[],
            gaps=[source_gap],
        ),
    )


def test_maps_target_gap_to_learning_need_without_inventing_fields() -> None:
    result = map_target_gap_to_learning_need(
        portfolio=portfolio(), gap=gap(), requirement=requirement()
    )

    assert isinstance(result, LearningNeedProfile)
    assert result.id == "learning-need:analysis-001:gap-python-cleaning"
    assert result.candidate_reference == CANDIDATE_ID
    assert result.target_reference == "role-data-analyst@2"
    assert result.competency.id == "cap-python-cleaning"
    assert result.competency.name is None
    assert result.current_state.level is None
    assert result.target_state.level == "3"
    assert result.target_state.expected_behaviors == ["Handle invalid values in tabular data"]
    assert result.gap.type == "skill_gap"
    assert result.priority is PreliminaryPriority.HIGH
    assert result.confidence is None


def test_preserves_evidence_references_without_copying_raw_evidence() -> None:
    result = map_target_gap_to_learning_need(
        portfolio=portfolio(), gap=gap(), requirement=requirement()
    )

    assert result.current_state.evidence_refs == ["evidence:cv:page-2"]
    assert result.provenance.evidence_refs == ["evidence:cv:page-2"]
    assert "Python usage" not in result.model_dump_json()


def test_missing_evidence_stays_empty_and_does_not_create_capability_level() -> None:
    source_gap = gap().model_copy(update={"matched_evidence_refs": []})
    result = map_target_gap_to_learning_need(
        portfolio=portfolio(source_gap), gap=source_gap, requirement=requirement()
    )

    assert result.current_state.evidence_refs == []
    assert result.current_state.level is None


def test_provenance_is_complete() -> None:
    result = map_target_gap_to_learning_need(
        portfolio=portfolio(), gap=gap(), requirement=requirement()
    )

    assert result.source_gap_refs == ["gap-python-cleaning"]
    assert result.provenance.analysis_id == "analysis-001"
    assert result.provenance.analysis_version == 1
    assert result.provenance.target_id == "role-data-analyst"
    assert result.provenance.target_version == "2"
    assert result.provenance.source_profile_id == "profile-001"
    assert result.provenance.source_profile_version == 4
    assert result.provenance.transformation == "learning-need-profile-v1"


def test_rejects_gap_not_in_source_portfolio() -> None:
    unknown_gap = gap().model_copy(update={"id": "gap-unknown"})

    with pytest.raises(ValueError, match="source_gap_not_found"):
        map_target_gap_to_learning_need(
            portfolio=portfolio(), gap=unknown_gap, requirement=requirement()
        )


def test_rejects_missing_candidate_reference() -> None:
    source = portfolio().model_copy(update={"candidate_id": None})

    with pytest.raises(ValueError, match="candidate_reference_missing"):
        map_target_gap_to_learning_need(
            portfolio=source, gap=gap(), requirement=requirement()
        )


def test_rejects_incomplete_provenance_at_schema_boundary() -> None:
    with pytest.raises(ValueError):
        LearningNeedProfile.model_validate(
            {
                "id": "learning-need-001",
                "candidate_reference": str(CANDIDATE_ID),
                "target_reference": "role-data-analyst@2",
                "learner_context": {"role": None, "experience_level": None},
                "competency": {"id": "cap-python-cleaning", "name": None, "description": None},
                "current_state": {"level": None, "evidence_refs": []},
                "target_state": {"level": "3", "expected_behaviors": []},
                "gap": {"type": "skill_gap", "description": "A gap."},
                "missing_knowledge": [],
                "learning_constraints": {},
                "priority": "high",
                "confidence": None,
                "source_gap_refs": ["gap-python-cleaning"],
                "provenance": {
                    "analysis_id": "analysis-001",
                    "analysis_version": 1,
                },
            }
        )
