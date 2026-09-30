from app.extraction.evidence import EvidenceContext
from app.extraction.profile_builder import build_candidate_profile
from app.extraction.schemas import EvidenceStatus, EvidenceType, ExtractedClaim, SourceLocator


def claim(value: str | None, evidence_type: EvidenceType) -> ExtractedClaim:
    return ExtractedClaim(
        value=value,
        evidence_type=evidence_type,
        confidence=0.9,
        evidence_status=EvidenceStatus.SUPPORTED if value else EvidenceStatus.UNKNOWN,
        source_locator=(
            SourceLocator(
                document_id="cv-1",
                section="experience",
                start_offset=0,
                end_offset=10,
            )
            if value
            else None
        ),
        source_excerpt=value,
    )


def test_builder_maps_evidence_type_to_context_and_preserves_original_type() -> None:
    profile = build_candidate_profile(
        skills=[claim("Pandas", EvidenceType.WORK_EXPERIENCE)], experience=[], education=[]
    )

    evidence = profile.skills[0].evidence[0]
    assert evidence.context is EvidenceContext.USED_IN_EMPLOYMENT
    assert evidence.original_evidence_type == EvidenceType.WORK_EXPERIENCE.value


def test_builder_routes_project_and_publication_claims_out_of_employment() -> None:
    profile = build_candidate_profile(
        skills=[],
        experience=[
            claim("Image Captioning", EvidenceType.PROJECT_USAGE),
            claim("Neural Computing and Applications paper", EvidenceType.PUBLICATION),
        ],
        education=[],
    )

    assert [item.name for item in profile.projects] == ["Image Captioning"]
    assert [item.title for item in profile.publications] == [
        "Neural Computing and Applications paper"
    ]
    assert profile.employment_history == []


def test_builder_keeps_project_usage_from_skills_as_project_context_skill_evidence() -> None:
    profile = build_candidate_profile(
        skills=[claim("Apache Kafka", EvidenceType.PROJECT_USAGE)], experience=[], education=[]
    )

    assert [item.entity for item in profile.skills] == ["Apache Kafka"]
    evidence = profile.skills[0].evidence[0]
    assert evidence.context is EvidenceContext.USED_IN_PROJECT
    assert evidence.original_evidence_type == EvidenceType.PROJECT_USAGE.value


def test_builder_keeps_work_experience_bucket_as_employment_and_unknown_activity_as_activity() -> None:
    profile = build_candidate_profile(
        skills=[],
        experience=[
            claim("Bioinformatics Data Analyst", EvidenceType.WORK_EXPERIENCE),
            claim("Built internal APIs with FastAPI", EvidenceType.UNKNOWN),
        ],
        education=[],
    )

    assert [item.name for item in profile.employment_history] == ["Bioinformatics Data Analyst"]
    assert [item.statement for item in profile.activities] == ["Built internal APIs with FastAPI"]


def test_builder_merges_same_skill_across_contexts_and_drops_unknown_placeholders() -> None:
    profile = build_candidate_profile(
        skills=[
            claim("Python", EvidenceType.EXPLICIT_SKILL),
            claim("Python", EvidenceType.WORK_EXPERIENCE),
            claim(None, EvidenceType.UNKNOWN),
        ],
        experience=[],
        education=[],
    )

    assert len(profile.skills) == 1
    assert {item.context for item in profile.skills[0].evidence} == {
        EvidenceContext.MENTIONED,
        EvidenceContext.USED_IN_EMPLOYMENT,
    }


def test_builder_routes_certification_to_credentials() -> None:
    profile = build_candidate_profile(
        skills=[claim("AWS Certified Developer", EvidenceType.CERTIFICATION)],
        experience=[],
        education=[],
    )

    assert profile.credentials[0].name == "AWS Certified Developer"
    assert profile.credentials[0].evidence[0].context is EvidenceContext.CREDENTIALED
