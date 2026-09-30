from app.extraction.evidence import (
    EvidenceContext,
    EvidenceEntity,
    EvidenceExtractionOutput,
    EvidenceItem,
)
from app.extraction.merge import merge_evidence_outputs


def _entity(name: str, context: EvidenceContext, excerpt: str) -> EvidenceEntity:
    return EvidenceEntity(
        name=name,
        entity_type="technology",
        evidence=[
            EvidenceItem(
                context=context,
                source_excerpt=excerpt,
                confidence=0.9,
                source_type="section",
            )
        ],
    )


def test_skill_list_mentions_are_not_upgraded() -> None:
    result = merge_evidence_outputs(
        [
            EvidenceExtractionOutput(
                entities=[_entity("Python", EvidenceContext.MENTIONED, "Python")]
            )
        ]
    )
    assert result.entities[0].evidence[0].context is EvidenceContext.MENTIONED


def test_research_implementation_preserves_research_context() -> None:
    result = merge_evidence_outputs(
        [
            EvidenceExtractionOutput(
                entities=[
                    _entity(
                        "PyTorch",
                        EvidenceContext.USED_IN_RESEARCH,
                        "Implemented PhoBERT model using PyTorch",
                    )
                ]
            )
        ]
    )
    assert result.entities[0].evidence[0].context is EvidenceContext.USED_IN_RESEARCH


def test_explicit_production_deployment_is_retained() -> None:
    result = merge_evidence_outputs(
        [
            EvidenceExtractionOutput(
                entities=[
                    _entity(
                        "PyTorch",
                        EvidenceContext.USED_IN_PRODUCTION,
                        "Built production inference API serving millions users",
                    )
                ]
            )
        ]
    )
    assert result.entities[0].evidence[0].context is EvidenceContext.USED_IN_PRODUCTION


def test_project_entity_is_not_employment_history() -> None:
    result = merge_evidence_outputs(
        [
            EvidenceExtractionOutput(
                entities=[
                    _entity("ViReCAX project", EvidenceContext.USED_IN_PROJECT, "ViReCAX project")
                ]
            )
        ]
    )
    assert result.entities[0].entity_type == "technology"
    assert result.entities[0].name == "ViReCAX project"
