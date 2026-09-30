from dataclasses import FrozenInstanceError

import pytest

from app.capability_analysis.evidence_index import EvidenceIndex
from app.capability_analysis.semantic_core.adapters import (
    adapt_evidence_index,
    adapt_role_requirement,
)
from app.capability_analysis.semantic_core.contracts import (
    EvidenceExpectation,
    EvidenceSemantics,
    EvidenceSourceKind,
    SemanticConstraintDimension,
    SemanticConstraintOperator,
    SemanticContext,
)
from app.extraction.evidence import EvidenceContext, EvidenceItem
from app.extraction.locators import SourceLocator
from app.extraction.profile import (
    CandidateProfile,
    CredentialEntity,
    EducationEntity,
    ExperienceEntity,
    ProjectEntity,
    SkillEntity,
)
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleRequirement,
)


def _locator(offset: int) -> SourceLocator:
    return SourceLocator(
        document_id="accepted-cv",
        section="experience",
        start_offset=offset,
        end_offset=offset + 10,
    )


def _evidence(
    context: EvidenceContext,
    offset: int,
    *,
    original_evidence_type: str,
    usage: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        context=context,
        usage=usage,
        source_excerpt=f"source observation at {offset}",
        confidence=0.91,
        source_type="accepted_cv_claim",
        source_locator=_locator(offset),
        original_evidence_type=original_evidence_type,
    )


def _requirement(dimension: CriterionDimension = CriterionDimension.SKILL) -> RoleRequirement:
    return RoleRequirement(
        id="requirement-1",
        criterion_dimension=dimension,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["generic capability"],
        confidence_threshold=0.8,
        assessment_recommendation="review source evidence",
        rubric_version="rubric-v1",
    )


def _adapt(profile: CandidateProfile) -> tuple[EvidenceSemantics, ...]:
    return adapt_evidence_index(EvidenceIndex(source="accepted_fixture", candidate_profile=profile))


def test_skill_requirement_does_not_infer_demonstrated_usage_expectation() -> None:
    requirement = adapt_role_requirement(_requirement())
    evidence = _adapt(
        CandidateProfile(
            skills=[
                SkillEntity(
                    entity="generic capability",
                    evidence=[
                        _evidence(
                            EvidenceContext.MENTIONED,
                            10,
                            original_evidence_type="explicit_skill",
                        )
                    ],
                )
            ]
        )
    )[0]

    assert requirement.evidence_expectation is EvidenceExpectation.UNKNOWN
    assert "evidence_expectation" in requirement.unresolved_fields
    assert evidence.context is SemanticContext.MENTIONED
    assert evidence.context.value != EvidenceExpectation.DEMONSTRATED_USAGE.value


@pytest.mark.parametrize(
    "dimension",
    [
        CriterionDimension.SKILL,
        CriterionDimension.EXPERIENCE,
        CriterionDimension.QUALIFICATION,
    ],
)
def test_non_structural_requirement_dimensions_leave_expectation_unresolved(
    dimension: CriterionDimension,
) -> None:
    requirement = adapt_role_requirement(_requirement(dimension))

    assert requirement.evidence_expectation is EvidenceExpectation.UNKNOWN
    assert "evidence_expectation" in requirement.unresolved_fields


@pytest.mark.parametrize(
    ("dimension", "expected"),
    [
        (CriterionDimension.EDUCATION, EvidenceExpectation.EDUCATION),
        (CriterionDimension.CREDENTIAL, EvidenceExpectation.CREDENTIAL),
    ],
)
def test_structural_requirement_dimensions_keep_direct_expectation(
    dimension: CriterionDimension,
    expected: EvidenceExpectation,
) -> None:
    requirement = adapt_role_requirement(_requirement(dimension))

    assert requirement.evidence_expectation is expected
    assert "evidence_expectation" not in requirement.unresolved_fields


def test_requirement_adapter_preserves_source_chain_and_opaque_constraints() -> None:
    source_locator = _locator(70)
    requirement = _requirement().model_copy(
        update={
            "source_requirement_ref": "jd-requirement-7",
            "source_locator": source_locator,
            "provenance": {"evidence_terms": "jd_extraction"},
            "evidence_constraints": ["must operate under the stated source condition"],
        }
    )

    semantics = adapt_role_requirement(requirement)

    assert semantics.source_requirement_ref == "jd-requirement-7"
    assert semantics.source_locator is not None
    assert (
        semantics.source_locator.document_id,
        semantics.source_locator.section,
        semantics.source_locator.start_offset,
        semantics.source_locator.end_offset,
    ) == ("accepted-cv", "experience", 70, 80)
    assert semantics.provenance == (("evidence_terms", "jd_extraction"),)
    assert len(semantics.constraints) == 1
    constraint = semantics.constraints[0]
    assert constraint.dimension is SemanticConstraintDimension.UNRESOLVED
    assert constraint.operator is SemanticConstraintOperator.DECLARED
    assert constraint.values == ("must operate under the stated source condition",)
    assert constraint.source_field == "evidence_constraints"
    assert constraint.source_reference == "jd-requirement-7"


def test_project_observation_remains_distinct_from_employment_observation() -> None:
    observations = _adapt(
        CandidateProfile(
            projects=[
                ProjectEntity(
                    name="customer onboarding",
                    evidence=[
                        _evidence(
                            EvidenceContext.USED_IN_PROJECT,
                            10,
                            original_evidence_type="project_usage",
                        )
                    ],
                )
            ],
            employment_history=[
                ExperienceEntity(
                    name="customer onboarding",
                    evidence=[
                        _evidence(
                            EvidenceContext.USED_IN_EMPLOYMENT,
                            30,
                            original_evidence_type="work_experience",
                        )
                    ],
                )
            ],
        )
    )

    assert [(item.source_kind, item.context) for item in observations] == [
        (EvidenceSourceKind.EMPLOYMENT, SemanticContext.USED_IN_EMPLOYMENT),
        (EvidenceSourceKind.PROJECT, SemanticContext.USED_IN_PROJECT),
    ]


def test_education_observation_does_not_become_work_observation() -> None:
    observations = _adapt(
        CandidateProfile(
            education=[
                EducationEntity(
                    institution="Example University",
                    degree="Bachelor",
                    field="Accounting",
                    evidence=[
                        _evidence(
                            EvidenceContext.STUDIED,
                            10,
                            original_evidence_type="education",
                        )
                    ],
                )
            ],
            employment_history=[
                ExperienceEntity(
                    name="Accounting",
                    evidence=[
                        _evidence(
                            EvidenceContext.USED_IN_EMPLOYMENT,
                            30,
                            original_evidence_type="work_experience",
                        )
                    ],
                )
            ],
        )
    )

    education = next(item for item in observations if item.source_kind is EvidenceSourceKind.EDUCATION)
    employment = next(item for item in observations if item.source_kind is EvidenceSourceKind.EMPLOYMENT)
    assert education.context is SemanticContext.STUDIED
    assert employment.context is SemanticContext.USED_IN_EMPLOYMENT
    assert education.source_kind is not employment.source_kind


def test_credential_observation_does_not_become_practice_observation() -> None:
    observations = _adapt(
        CandidateProfile(
            credentials=[
                CredentialEntity(
                    name="Professional credential",
                    evidence=[
                        _evidence(
                            EvidenceContext.CREDENTIALED,
                            10,
                            original_evidence_type="certification",
                        )
                    ],
                )
            ],
            skills=[
                SkillEntity(
                    entity="Professional practice",
                    evidence=[
                        _evidence(
                            EvidenceContext.USED_IN_EMPLOYMENT,
                            30,
                            original_evidence_type="work_experience",
                        )
                    ],
                )
            ],
        )
    )

    credential = next(item for item in observations if item.source_kind is EvidenceSourceKind.CREDENTIAL)
    practice = next(item for item in observations if item.source_kind is EvidenceSourceKind.SKILL)
    assert credential.context is SemanticContext.CREDENTIALED
    assert practice.context is SemanticContext.USED_IN_EMPLOYMENT


def test_multiple_observations_for_one_concept_remain_distinct() -> None:
    observations = _adapt(
        CandidateProfile(
            skills=[
                SkillEntity(
                    entity="generic capability",
                    evidence=[
                        _evidence(
                            EvidenceContext.MENTIONED,
                            10,
                            original_evidence_type="explicit_skill",
                        ),
                        _evidence(
                            EvidenceContext.USED_IN_PROJECT,
                            30,
                            original_evidence_type="project_usage",
                            usage="contributed",
                        ),
                    ],
                )
            ]
        )
    )

    assert len(observations) == 2
    assert observations[0].concepts == observations[1].concepts == ("generic capability",)
    assert observations[0].evidence_ref != observations[1].evidence_ref
    assert [item.original_evidence_type for item in observations] == [
        "explicit_skill",
        "project_usage",
    ]
    assert observations[1].participation == "contributed"
    assert observations[1].source_locator is not None
    assert observations[1].confidence == 0.91


def test_absent_usage_remains_unknown_instead_of_inferred_participation() -> None:
    observation = _adapt(
        CandidateProfile(
            skills=[
                SkillEntity(
                    entity="generic capability",
                    evidence=[
                        _evidence(
                            EvidenceContext.USED_IN_EMPLOYMENT,
                            10,
                            original_evidence_type="work_experience",
                        )
                    ],
                )
            ]
        )
    )[0]

    assert observation.participation is None
    assert "participation" in observation.unresolved_fields


def test_locator_less_evidence_is_not_projected_as_matchable_semantics() -> None:
    evidence_without_locator = EvidenceItem(
        context=EvidenceContext.USED_IN_EMPLOYMENT,
        usage=None,
        source_excerpt="unlocatable source observation",
        confidence=0.91,
        source_type="legacy_graph",
        source_locator=None,
        original_evidence_type="work_experience",
    )

    observations = _adapt(
        CandidateProfile(
            skills=[
                SkillEntity(entity="generic capability", evidence=[evidence_without_locator])
            ]
        )
    )

    assert observations == ()


def test_missing_evidence_produces_no_observation_and_never_an_absence_claim() -> None:
    observations = _adapt(CandidateProfile(skills=[SkillEntity(entity="unobserved")]))

    assert observations == ()


def test_semantic_contracts_are_immutable() -> None:
    requirement = adapt_role_requirement(_requirement(CriterionDimension.EDUCATION))
    evidence = _adapt(
        CandidateProfile(
            skills=[
                SkillEntity(
                    entity="generic capability",
                    evidence=[
                        _evidence(
                            EvidenceContext.MENTIONED,
                            10,
                            original_evidence_type="explicit_skill",
                        )
                    ],
                )
            ]
        )
    )[0]

    assert requirement.evidence_expectation is EvidenceExpectation.EDUCATION
    with pytest.raises(FrozenInstanceError):
        requirement.concepts = ("changed",)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        evidence.context = SemanticContext.UNKNOWN  # type: ignore[misc]
