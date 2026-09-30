import pytest
from pydantic import ValidationError

from app.extraction.evidence import EvidenceContext, EvidenceItem


def test_evidence_item_captures_context_usage_and_source() -> None:
    evidence = EvidenceItem(
        context=EvidenceContext.USED_IN_RESEARCH,
        usage="implemented_model",
        source_excerpt="Implemented PhoBERT model using PyTorch",
        confidence=0.95,
        source_type="cv_section",
    )

    assert evidence.context is EvidenceContext.USED_IN_RESEARCH
    assert evidence.usage == "implemented_model"


def test_evidence_item_rejects_missing_source_or_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(
            context=EvidenceContext.MENTIONED,
            source_excerpt="",
            confidence=1.1,
            source_type="cv_section",
        )
