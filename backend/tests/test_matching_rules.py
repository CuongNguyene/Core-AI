from datetime import UTC, datetime

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.extraction.schemas import (
    CVExtractionOutput,
    DocumentKind,
    EvidenceStatus,
    ExtractedClaim,
    ExtractionProfile,
    ReviewState,
    SourceLocator,
)
from app.matching.rules import evaluate_requirements
from app.matching.schemas import (
    CriterionDimension,
    CriterionStatus,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)


def accepted_cv(*claims: ExtractedClaim) -> ExtractionProfile:
    return ExtractionProfile(
        id="cv-profile-1",
        job_id="cv-job-1",
        document_id="fixture-cv-basic",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        version=1,
        review_state=ReviewState.ACCEPTED,
        accepted_by=REVIEWER_ID,
        accepted_at=datetime.now(UTC),
        output=CVExtractionOutput(skills=list(claims), experience=[], education=[]),
        audit={},
    )


def claim(value: str, confidence: float = 0.9, offset: int = 16) -> ExtractedClaim:
    return ExtractedClaim(
        value=value,
        confidence=confidence,
        evidence_status=EvidenceStatus.SUPPORTED,
        source_locator=SourceLocator(
            document_id="fixture-cv-basic",
            section="skills",
            start_offset=offset,
            end_offset=offset + len(value),
        ),
        source_excerpt=value,
    )


def active_role(*requirements: RoleRequirement) -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id="role-ai-engineer",
        version="1.0",
        status=RoleProfileStatus.ACTIVE,
        source_jd_profile_id="jd-profile-1",
        source_jd_profile_version=1,
        rule_set_version="1.0",
        policy_version="matching-v1",
        requirements=list(requirements),
    )


def requirement(
    requirement_id: str,
    classification: RequirementClassification,
    *,
    confidence_threshold: float = 0.8,
    conflicting_terms: list[str] | None = None,
) -> RoleRequirement:
    return RoleRequirement(
        id=requirement_id,
        criterion_dimension=CriterionDimension.SKILL,
        classification=classification,
        evidence_terms=["Python"],
        conflicting_terms=conflicting_terms or [],
        confidence_threshold=confidence_threshold,
        assessment_recommendation="practical_task",
        rubric_version="1.0",
    )


def test_rule_engine_allocates_evidence_once_to_highest_priority_requirement() -> None:
    evaluation = evaluate_requirements(
        accepted_cv(claim("Python")),
        active_role(
            requirement("legal-python", RequirementClassification.LEGAL_MANDATORY),
            requirement("optional-python", RequirementClassification.OPTIONAL),
        ),
    )

    assert [result.status for result in evaluation.criterion_results] == [
        CriterionStatus.MATCHED,
        CriterionStatus.INSUFFICIENT,
    ]
    assert len(evaluation.allocations) == 1
    assert evaluation.criterion_results[1].reused_evidence_ids == [
        evaluation.allocations[0].evidence_id
    ]


def test_low_confidence_evidence_is_partial_not_missing_competency() -> None:
    evaluation = evaluate_requirements(
        accepted_cv(claim("Python", confidence=0.5)),
        active_role(requirement("critical-python", RequirementClassification.ROLE_CRITICAL)),
    )

    result = evaluation.criterion_results[0]
    assert result.status is CriterionStatus.PARTIAL
    assert result.human_review_required is True
    assert result.source_evidence[0].confidence == 0.5


def test_missing_legal_requirement_is_insufficient_with_assessment_recommendation() -> None:
    evaluation = evaluate_requirements(
        accepted_cv(claim("FastAPI")),
        active_role(requirement("legal-python", RequirementClassification.LEGAL_MANDATORY)),
    )

    result = evaluation.criterion_results[0]
    assert result.status is CriterionStatus.INSUFFICIENT
    assert result.mandatory_status == "unresolved"
    assert result.recommended_next_assessment == "practical_task"
    assert result.human_review_required is True
    assert evaluation.preliminary_skill_gaps[0].requirement_id == "legal-python"
    assert evaluation.preliminary_skill_gaps[0].status is CriterionStatus.INSUFFICIENT
    assert evaluation.preliminary_skill_gaps[0].human_review_required is True


def test_conflicting_evidence_requires_human_review() -> None:
    evaluation = evaluate_requirements(
        accepted_cv(claim("Python"), claim("No Python", offset=30)),
        active_role(
            requirement(
                "critical-python",
                RequirementClassification.ROLE_CRITICAL,
                conflicting_terms=["No Python"],
            )
        ),
    )

    result = evaluation.criterion_results[0]
    assert result.status is CriterionStatus.CONFLICTING
    assert result.human_review_required is True
    assert len(result.source_evidence) == 2


def test_contextual_responsibility_is_preserved_but_not_scored_as_capability_gap() -> None:
    responsibility = RoleRequirement(
        id="monthly-reports",
        criterion_dimension=None,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["prepare monthly financial reports"],
        modality="responsibility",
        confidence_threshold=0.8,
        assessment_recommendation="review",
        rubric_version="1.0",
    )

    evaluation = evaluate_requirements(accepted_cv(claim("Python")), active_role(responsibility))

    assert evaluation.criterion_results == []
    assert evaluation.preliminary_skill_gaps == []


def test_unspecified_scope_context_is_preserved_but_not_scored_as_capability_gap() -> None:
    exclusion = RoleRequirement(
        id="warehouse-out-of-scope",
        criterion_dimension=None,
        classification=RequirementClassification.UNCLASSIFIED,
        evidence_terms=["warehouse knowledge is not required"],
        modality="unspecified",
        confidence_threshold=0.8,
        assessment_recommendation="context_only",
        rubric_version="1.0",
    )

    evaluation = evaluate_requirements(accepted_cv(claim("Python")), active_role(exclusion))

    assert evaluation.criterion_results == []
    assert evaluation.preliminary_skill_gaps == []
