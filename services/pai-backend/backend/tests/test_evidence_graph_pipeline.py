from app.extraction.evidence import EvidenceContext, RelationClaim, RelationEntityType
from app.extraction.evidence_graph_pipeline import build_candidate_profile
from app.extraction.profile import RelationExtractionOutput


def _relation(source: str, context: EvidenceContext) -> RelationClaim:
    return RelationClaim(
        entity="PyTorch",
        entity_type=RelationEntityType.SKILL,
        context=context,
        usage="implemented model",
        confidence=0.9,
        source_excerpt=source,
    )


def test_small_document_uses_full_context_only() -> None:
    profile = build_candidate_profile(
        "small",
        RelationExtractionOutput(
            relations=[_relation("used PyTorch", EvidenceContext.USED_IN_PROJECT)]
        ),
        [RelationExtractionOutput(relations=[_relation("other", EvidenceContext.MENTIONED)])],
    )
    assert len(profile.skills) == 1
    assert [item.source_type for item in profile.skills[0].evidence] == ["full_document"]


def test_large_document_adds_section_grounding_without_flattening_context() -> None:
    profile = build_candidate_profile(
        "x" * 20_000,
        RelationExtractionOutput(
            relations=[_relation("used PyTorch", EvidenceContext.USED_IN_RESEARCH)]
        ),
        [
            RelationExtractionOutput(
                relations=[_relation("PyTorch project", EvidenceContext.USED_IN_PROJECT)]
            )
        ],
    )
    assert len(profile.skills) == 1
    assert {item.context for item in profile.skills[0].evidence} == {
        EvidenceContext.USED_IN_RESEARCH,
        EvidenceContext.USED_IN_PROJECT,
    }
