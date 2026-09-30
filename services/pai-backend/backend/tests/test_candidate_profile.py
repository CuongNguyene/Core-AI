from app.extraction.evidence import EvidenceContext, EvidenceItem, RelationClaim, RelationEntityType
from app.extraction.profile import (
    CandidateProfile,
    EducationEntity,
    RelationExtractionOutput,
    ResearchEntity,
    SkillEntity,
)


def test_candidate_profile_keeps_skill_and_research_context_separate() -> None:
    evidence = EvidenceItem(
        context=EvidenceContext.USED_IN_RESEARCH,
        usage="implemented_model",
        source_excerpt="Implemented PhoBERT model using PyTorch",
        confidence=0.95,
        source_type="cv_section",
    )
    profile = CandidateProfile(
        skills=[SkillEntity(entity="PyTorch", evidence=[evidence])],
        research_work=[ResearchEntity(name="Vietnamese sentiment analysis", evidence=[evidence])],
        education=[EducationEntity(institution="UIT", degree="BS Computer Science")],
    )

    assert profile.skills[0].entity == "PyTorch"
    assert profile.skills[0].evidence[0].context is EvidenceContext.USED_IN_RESEARCH
    assert profile.research_work[0].name == "Vietnamese sentiment analysis"
    assert profile.education[0].institution == "UIT"


def test_relation_extraction_keeps_context_instead_of_flattening_skill() -> None:
    output = RelationExtractionOutput(
        relations=[
            RelationClaim(
                entity="PyTorch",
                entity_type=RelationEntityType.SKILL,
                context=EvidenceContext.USED_IN_RESEARCH,
                usage="implemented_model",
                confidence=0.95,
                source_excerpt="Implemented PhoBERT model using PyTorch",
            )
        ]
    )

    assert output.relations[0].context is EvidenceContext.USED_IN_RESEARCH
