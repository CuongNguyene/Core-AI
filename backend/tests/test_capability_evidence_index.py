from datetime import UTC, datetime

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.capability_analysis.domain_packs.it_ai import IT_AI_PACK
from app.capability_analysis.evidence_index import build_evidence_index
from app.capability_analysis.retrieval import retrieve_evidence
from app.capability_analysis.rules import build_provisional_capability_profile, evaluate_target
from app.capability_analysis.schemas import TargetType, TargetUsageMode
from app.extraction.evidence import EvidenceContext, EvidenceItem
from app.extraction.locators import SourceLocator
from app.extraction.profile import CandidateProfile, SkillEntity
from app.extraction.schemas import (
    CVExtractionOutput,
    DocumentKind,
    EvidenceStatus,
    EvidenceType,
    ExtractedClaim,
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


def locator(offset: int) -> SourceLocator:
    return SourceLocator(
        document_id="cv-accepted",
        section="experience",
        start_offset=offset,
        end_offset=offset + 10,
    )


def raw_claim(value: str, evidence_type: EvidenceType, offset: int) -> ExtractedClaim:
    return ExtractedClaim(
        value=value,
        evidence_type=evidence_type,
        confidence=0.95,
        evidence_status=EvidenceStatus.SUPPORTED,
        source_locator=locator(offset),
        source_excerpt=f"{evidence_type.value}: {value}",
    )


def accepted_profile_with_stale_projection() -> ExtractionProfile:
    stale_mention = EvidenceItem(
        context=EvidenceContext.MENTIONED,
        usage=None,
        source_excerpt="stale flattened Python",
        confidence=0.8,
        source_type="legacy",
        source_locator=locator(90),
    )
    return ExtractionProfile(
        id="accepted-cv",
        job_id="job-cv",
        document_id="cv-accepted",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        version=1,
        review_state=ReviewState.ACCEPTED,
        accepted_by=REVIEWER_ID,
        accepted_at=datetime(2026, 8, 10, tzinfo=UTC),
        output=CVExtractionOutput(
            skills=[
                raw_claim("Python", EvidenceType.EXPLICIT_SKILL, 10),
                raw_claim("Python", EvidenceType.WORK_EXPERIENCE, 20),
                raw_claim("AWS Certified Developer", EvidenceType.CERTIFICATION, 30),
            ],
            experience=[],
            education=[],
        ),
        candidate_profile=CandidateProfile(
            skills=[SkillEntity(entity="Python", evidence=[stale_mention])]
        ),
        audit={},
    )


def python_requirement() -> RoleRequirement:
    return RoleRequirement(
        id="python",
        criterion_dimension=CriterionDimension.SKILL,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["Python"],
        confidence_threshold=0.8,
        assessment_recommendation="practical_task",
        rubric_version="rubric-v1",
    )


def target(requirement: RoleRequirement) -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id="role",
        version="1",
        status=RoleProfileStatus.PROVISIONAL,
        source_jd_profile_id="jd",
        source_jd_profile_version=1,
        rule_set_version="rules-v1",
        policy_version="policy-v1",
        requirements=[requirement],
    )


def test_raw_accepted_claims_override_stale_flattened_candidate_projection() -> None:
    index = build_evidence_index(accepted_profile_with_stale_projection())

    assert index.source == "accepted_cv_extraction_output"
    python = index.candidate_profile.skills[0]
    assert [(item.context, item.original_evidence_type) for item in python.evidence] == [
        (EvidenceContext.MENTIONED, "explicit_skill"),
        (EvidenceContext.USED_IN_EMPLOYMENT, "work_experience"),
    ]


def test_python_retrieval_preserves_original_type_and_ranks_work_before_mention() -> None:
    index = build_evidence_index(accepted_profile_with_stale_projection())

    candidates = retrieve_evidence(
        python_requirement(),
        index.candidate_profile,
        domain_pack=IT_AI_PACK,
    )

    assert [item.source_context for item in candidates] == [
        EvidenceContext.USED_IN_EMPLOYMENT,
        EvidenceContext.MENTIONED,
    ]
    assert [item.original_evidence_type for item in candidates] == [
        "work_experience",
        "explicit_skill",
    ]


def test_assessment_counts_retrieved_and_eligible_evidence_separately() -> None:
    profile = accepted_profile_with_stale_projection()
    current = build_provisional_capability_profile(profile)

    assessment = evaluate_target(
        current,
        target(python_requirement()),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert assessment.retrieved_candidate_count == 2
    assert assessment.eligible_candidate_count == 2
    assert assessment.evidence_strength is not None
    assert assessment.evidence_strength.value == "work"
    python = next(item for item in current.capabilities if item.capability_id == "python")
    assert {item.original_evidence_type for item in python.observations} == {
        "explicit_skill",
        "work_experience",
    }


def test_kafka_alias_keeps_project_usage_stronger_than_explicit_skill() -> None:
    profile = accepted_profile_with_stale_projection().model_copy(
        update={
            "output": CVExtractionOutput(
                skills=[
                    raw_claim("Kafka", EvidenceType.EXPLICIT_SKILL, 10),
                    raw_claim("Apache Kafka", EvidenceType.PROJECT_USAGE, 20),
                ],
                experience=[],
                education=[],
            )
        }
    )
    index = build_evidence_index(profile)
    kafka_requirement = python_requirement().model_copy(
        update={"id": "kafka", "evidence_terms": ["Kafka"]}
    )

    candidates = retrieve_evidence(
        kafka_requirement,
        index.candidate_profile,
        domain_pack=IT_AI_PACK,
    )

    assert [item.source_context for item in candidates] == [
        EvidenceContext.USED_IN_PROJECT,
        EvidenceContext.MENTIONED,
    ]
    assert [item.original_evidence_type for item in candidates] == [
        "project_usage",
        "explicit_skill",
    ]
    assert all(item.canonical_capability == "kafka" for item in candidates)
