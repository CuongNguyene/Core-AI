from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.capability_analysis.rules import build_provisional_capability_profile, evaluate_target
from app.capability_analysis.schemas import (
    HumanAssistedEvidenceSelection,
    HumanAssistedReanalysisContext,
    TargetType,
    TargetUsageMode,
)
from app.extraction.evidence import EvidenceContext, EvidenceItem
from app.extraction.locators import SourceLocator
from app.extraction.profile import CandidateProfile, SkillEntity
from app.extraction.schemas import (
    CVExtractionOutput,
    DocumentKind,
    ExtractionProfile,
    ReviewState,
)
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)


def _profile() -> ExtractionProfile:
    evidence = EvidenceItem(
        context=EvidenceContext.USED_IN_EMPLOYMENT,
        usage="implemented",
        source_excerpt="Built SQL reporting pipelines.",
        confidence=0.95,
        source_type="cv_section",
        source_locator=SourceLocator(
            document_id="cv-document-1",
            section="experience",
            start_offset=10,
            end_offset=42,
        ),
    )
    return ExtractionProfile(
        id="accepted-cv-1",
        job_id="cv-job-1",
        document_id="cv-document-1",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        version=1,
        review_state=ReviewState.ACCEPTED,
        accepted_by=REVIEWER_ID,
        accepted_at=datetime(2026, 9, 14, tzinfo=UTC),
        output=CVExtractionOutput(skills=[], experience=[], education=[]),
        candidate_profile=CandidateProfile(
            skills=[SkillEntity(entity="SQL", evidence=[evidence])]
        ),
        audit={},
    )


def _target(requirement: RoleRequirement) -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id="role-profile-1",
        version="1",
        status=RoleProfileStatus.PROVISIONAL,
        source_jd_profile_id="jd-1",
        source_jd_profile_version=1,
        rule_set_version="rules-v1",
        policy_version="policy-v1",
        requirements=[requirement],
    )


def _requirement() -> RoleRequirement:
    return RoleRequirement(
        id="requirement-sql",
        criterion_dimension=CriterionDimension.SKILL,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["Structured Query Language"],
        confidence_threshold=0.8,
        assessment_recommendation="practical_task",
        rubric_version="rubric-v1",
    )


def test_human_assisted_selection_deduplicates_refs_stably() -> None:
    selection = HumanAssistedEvidenceSelection(
        requirement_id="requirement-sql",
        selected_evidence_refs=["evidence-b", "evidence-a", "evidence-b"],
    )

    assert selection.selected_evidence_refs == ["evidence-b", "evidence-a"]


def test_human_assisted_context_rejects_empty_selection() -> None:
    with pytest.raises(ValidationError):
        HumanAssistedReanalysisContext(
            source_analysis_id="analysis-source",
            evidence_selections=[
                {"requirement_id": "requirement-sql", "selected_evidence_refs": []}
            ],
        )


def test_human_assisted_request_cannot_write_assessment_or_readiness() -> None:
    with pytest.raises(ValidationError):
        HumanAssistedReanalysisContext(
            source_analysis_id="analysis-source",
            evidence_selections=[
                {
                    "requirement_id": "requirement-sql",
                    "selected_evidence_refs": ["evidence-1"],
                    "assessment_status": "supported",
                }
            ],
        )


def test_selected_evidence_is_considered_before_engine_decides_status() -> None:
    profile = _profile()
    capability_profile = build_provisional_capability_profile(profile)
    evidence_ref = capability_profile.semantic_evidence[0].evidence_ref

    analysis = evaluate_target(
        capability_profile,
        _target(_requirement()),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
        assisted_evidence_by_requirement={"requirement-sql": (evidence_ref,)},
    )

    assert analysis.assessments[0].evidence_status.value in {
        "supported",
        "insufficient",
        "context_mismatch",
    }
    assert analysis.assessments[0].evidence_status.value != "not_found_in_evidence"
    assert analysis.assessments[0].matched_evidence_refs == [evidence_ref]
