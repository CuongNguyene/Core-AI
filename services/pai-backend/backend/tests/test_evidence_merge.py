from app.extraction.entity_normalization import normalize_entity
from app.extraction.evidence import (
    EvidenceContext,
    EvidenceEntity,
    EvidenceExtractionOutput,
    EvidenceItem,
)
from app.extraction.merge import merge_evidence_outputs


def _item(context: EvidenceContext, confidence: float, excerpt: str) -> EvidenceItem:
    return EvidenceItem(
        context=context,
        source_excerpt=excerpt,
        confidence=confidence,
        source_type="section",
    )


def test_merge_canonicalizes_aliases_and_preserves_contexts() -> None:
    merged = merge_evidence_outputs(
        [
            EvidenceExtractionOutput(
                entities=[
                    EvidenceEntity(
                        name="torch",
                        entity_type="technology",
                        evidence=[_item(EvidenceContext.MENTIONED, 0.8, "torch")],
                    )
                ]
            ),
            EvidenceExtractionOutput(
                entities=[
                    EvidenceEntity(
                        name="PyTorch framework",
                        entity_type="technology",
                        evidence=[
                            _item(
                                EvidenceContext.USED_IN_RESEARCH,
                                0.95,
                                "Implemented model using PyTorch framework",
                            )
                        ],
                    )
                ]
            ),
        ]
    )
    assert len(merged.entities) == 1
    assert merged.entities[0].canonical_value == "PyTorch"
    assert {item.context for item in merged.entities[0].evidence} == {
        EvidenceContext.MENTIONED,
        EvidenceContext.USED_IN_RESEARCH,
    }


def test_merge_keeps_stronger_duplicate_evidence() -> None:
    merged = merge_evidence_outputs(
        [
            EvidenceExtractionOutput(
                entities=[
                    EvidenceEntity(
                        name="PyTorch",
                        entity_type="technology",
                        evidence=[_item(EvidenceContext.USED_IN_PROJECT, 0.6, "used PyTorch")],
                    )
                ]
            ),
            EvidenceExtractionOutput(
                entities=[
                    EvidenceEntity(
                        name="PyTorch",
                        entity_type="technology",
                        evidence=[_item(EvidenceContext.USED_IN_PROJECT, 0.9, "used PyTorch")],
                    )
                ]
            ),
        ]
    )
    assert merged.entities[0].evidence[0].confidence == 0.9


def test_entity_normalization_retains_original_value() -> None:
    normalized = normalize_entity("torch")
    assert normalized.original_value == "torch"
    assert normalized.canonical_value == "PyTorch"
