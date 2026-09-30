from app.extraction.evidence import (
    EvidenceContext,
    RelationClaim,
    RelationEntityType,
)
from app.extraction.graph_merge import merge_relation_evidence
from app.extraction.profile import RelationExtractionOutput


def test_graph_merge_preserves_distinct_contexts_for_one_skill() -> None:
    output = merge_relation_evidence(
        RelationExtractionOutput(
            relations=[
                RelationClaim(
                    entity="pytorch",
                    entity_type=RelationEntityType.SKILL,
                    context=EvidenceContext.MENTIONED,
                    confidence=0.5,
                    source_excerpt="PyTorch",
                ),
                RelationClaim(
                    entity="PyTorch framework",
                    entity_type=RelationEntityType.SKILL,
                    context=EvidenceContext.USED_IN_RESEARCH,
                    usage="implemented_model",
                    confidence=0.95,
                    source_excerpt="Implemented model using PyTorch",
                ),
            ]
        )
    )

    assert len(output.skills) == 1
    assert {item.context for item in output.skills[0].evidence} == {
        EvidenceContext.MENTIONED,
        EvidenceContext.USED_IN_RESEARCH,
    }


def test_graph_merge_keeps_projects_and_research_out_of_employment_history() -> None:
    output = merge_relation_evidence(
        RelationExtractionOutput(
            relations=[
                RelationClaim(
                    entity="ViReCAX",
                    entity_type=RelationEntityType.RESEARCH,
                    context=EvidenceContext.USED_IN_RESEARCH,
                    confidence=0.9,
                    source_excerpt="Research project ViReCAX",
                ),
                RelationClaim(
                    entity="Hotel sentiment project",
                    entity_type=RelationEntityType.PROJECT,
                    context=EvidenceContext.USED_IN_PROJECT,
                    confidence=0.85,
                    source_excerpt="Developed a hotel sentiment project",
                ),
            ]
        )
    )

    assert len(output.research_work) == 1
    assert len(output.projects) == 1
    assert output.employment_history == []
