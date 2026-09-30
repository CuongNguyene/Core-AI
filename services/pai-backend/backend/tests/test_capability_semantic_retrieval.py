from datetime import UTC, datetime

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.capability_analysis.domain_packs.it_ai import IT_AI_PACK
from app.capability_analysis.retrieval import retrieve_evidence
from app.extraction.evidence import EvidenceContext, EvidenceItem
from app.extraction.locators import SourceLocator
from app.extraction.profile import CandidateProfile, EducationEntity, ProjectEntity, SkillEntity
from app.extraction.schemas import CVExtractionOutput, DocumentKind, ExtractionProfile, ReviewState
from app.matching.schemas import CriterionDimension, RequirementClassification, RoleRequirement


def evidence(context: EvidenceContext, excerpt: str, offset: int) -> EvidenceItem:
    return EvidenceItem(
        context=context,
        usage="implemented" if context is not EvidenceContext.MENTIONED else None,
        source_excerpt=excerpt,
        confidence=0.92,
        source_type="cv_section",
        source_locator=SourceLocator(
            document_id="cv-real-fixture",
            section="experience",
            start_offset=offset,
            end_offset=offset + len(excerpt),
        ),
    )


def accepted_profile(candidate: CandidateProfile) -> ExtractionProfile:
    return ExtractionProfile(
        id="32c61c13-3c40-47a9-9018-ed76f7fc0b3c",
        job_id="job-real-cv",
        document_id="cv-real-fixture",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        version=1,
        review_state=ReviewState.ACCEPTED,
        accepted_by=REVIEWER_ID,
        accepted_at=datetime(2026, 8, 10, tzinfo=UTC),
        output=CVExtractionOutput(skills=[], experience=[], education=[]),
        candidate_profile=candidate,
        audit={},
    )


def requirement(terms: list[str], *, dimension: CriterionDimension = CriterionDimension.SKILL) -> RoleRequirement:
    return RoleRequirement(
        id="req-1",
        criterion_dimension=dimension,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=terms,
        confidence_threshold=0.8,
        assessment_recommendation="practical_task",
        rubric_version="rubric-v1",
    )


def candidate_profile(profile: ExtractionProfile) -> CandidateProfile:
    assert profile.candidate_profile is not None
    return profile.candidate_profile


def test_python_retrieval_ranks_work_before_explicit_skill_mention() -> None:
    profile = accepted_profile(
        CandidateProfile(
            skills=[
                SkillEntity(entity="Python", evidence=[evidence(EvidenceContext.MENTIONED, "Python, PyTorch and TensorFlow", 10)]),
                SkillEntity(entity="Python", evidence=[evidence(EvidenceContext.USED_IN_EMPLOYMENT, "Developed robust Python automation scripts", 100)]),
            ]
        )
    )

    matches = retrieve_evidence(
        requirement(["Python"]),
        candidate_profile(profile),
        domain_pack=IT_AI_PACK,
    )

    assert [item.canonical_capability for item in matches] == ["python", "python"]
    assert matches[0].source_context == EvidenceContext.USED_IN_EMPLOYMENT
    assert matches[0].strength_rank > matches[1].strength_rank
    assert all(item.original_value == "Python" for item in matches)


def test_education_retrieval_uses_degree_and_field_without_inventing_completion() -> None:
    profile = accepted_profile(
        CandidateProfile(
            education=[
                EducationEntity(
                    institution="University A",
                    degree="BS",
                    field="Data Science",
                    evidence=[evidence(EvidenceContext.STUDIED, "BS in Data Science", 200)],
                ),
                EducationEntity(
                    institution="University B",
                    degree="MS",
                    field="Computer Science",
                    evidence=[evidence(EvidenceContext.STUDIED, "MS in Computer Science (in progress)", 240)],
                ),
            ]
        )
    )

    matches = retrieve_evidence(
        requirement(["Computer Science", "Data Science"], dimension=CriterionDimension.EDUCATION),
        candidate_profile(profile),
        domain_pack=IT_AI_PACK,
    )

    assert {item.canonical_capability for item in matches} == {"computer_science", "data_science"}
    assert any("BS in Data Science" in item.source_excerpt for item in matches)


def test_aliases_retrieve_apache_kafka_and_spark_as_project_evidence() -> None:
    profile = accepted_profile(
        CandidateProfile(
            projects=[
                ProjectEntity(name="Realtime sentiment project", evidence=[evidence(EvidenceContext.USED_IN_PROJECT, "Used Apache Kafka and Apache Spark", 300)]),
            ]
        )
    )

    matches = retrieve_evidence(
        requirement(["Kafka", "Spark"]),
        candidate_profile(profile),
        domain_pack=IT_AI_PACK,
    )

    assert {item.canonical_capability for item in matches} == {"kafka", "spark"}
    assert all(item.source_context is EvidenceContext.USED_IN_PROJECT for item in matches)
    assert all(item.eligible is True for item in matches)


def test_docker_mention_is_retrieved_but_not_usage_eligible() -> None:
    profile = accepted_profile(
        CandidateProfile(
            skills=[SkillEntity(entity="Docker", evidence=[evidence(EvidenceContext.MENTIONED, "Tools: Docker, Kubernetes", 400)])]
        )
    )

    matches = retrieve_evidence(
        requirement(["containerization", "Docker"]),
        candidate_profile(profile),
        domain_pack=IT_AI_PACK,
    )

    docker = next(item for item in matches if item.canonical_capability == "docker")
    assert docker.eligible is False
    assert "mention_requires_verification" in docker.eligibility_reason_codes


def test_production_requirement_retrieves_related_project_but_marks_context_mismatch() -> None:
    profile = accepted_profile(
        CandidateProfile(
            projects=[ProjectEntity(name="Realtime dashboard", evidence=[evidence(EvidenceContext.USED_IN_PROJECT, "Deployed a realtime dashboard", 500)])]
        )
    )
    req = requirement(["production deployment"])

    matches = retrieve_evidence(req, candidate_profile(profile), domain_pack=IT_AI_PACK)

    assert matches
    assert matches[0].eligible is False
    assert "production_context_required" in matches[0].eligibility_reason_codes


def test_model_evaluation_retrieval_is_partial_semantic_coverage_not_missing() -> None:
    profile = accepted_profile(
        CandidateProfile(
            projects=[
                ProjectEntity(
                    name="CNN project",
                    evidence=[evidence(EvidenceContext.USED_IN_PROJECT, "Developed and evaluated CNN models with evaluation metrics", 600)],
                )
            ]
        )
    )

    matches = retrieve_evidence(
        requirement(["model design", "model training", "model evaluation"]),
        candidate_profile(profile),
        domain_pack=IT_AI_PACK,
    )

    assert any(item.canonical_capability == "model_evaluation" for item in matches)
    assert all(item.source_context is EvidenceContext.USED_IN_PROJECT for item in matches)


def test_mlops_negative_control_does_not_use_docker_or_streaming_as_proxy() -> None:
    profile = accepted_profile(
        CandidateProfile(
            skills=[SkillEntity(entity="Docker", evidence=[evidence(EvidenceContext.MENTIONED, "Docker", 700)])],
            projects=[ProjectEntity(name="Streaming", evidence=[evidence(EvidenceContext.USED_IN_PROJECT, "Used Kafka and Spark", 720)])],
        )
    )

    matches = retrieve_evidence(
        requirement(["end-to-end MLOps", "CI/CD", "model drift monitoring"]),
        candidate_profile(profile),
        domain_pack=IT_AI_PACK,
    )

    assert matches == []
