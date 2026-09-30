import json

from app.extraction.chunking import TextChunk
from app.extraction.fixtures import FixtureDocument
from app.extraction.merge import merge_chunk_outputs
from app.extraction.schemas import (
    ChunkExtractedClaim,
    CVChunkExtractionOutput,
    DocumentKind,
    EvidenceStatus,
)


def test_unresolved_claim_is_preserved_as_insufficient_when_excerpt_is_not_present() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-basic",
        kind=DocumentKind.CV,
        content="Python",
    )
    output = CVChunkExtractionOutput(
        skills=[
            ChunkExtractedClaim(
                value="Production Python deployment",
                confidence=0.5,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt="Production Python deployment",
            )
        ],
        experience=[],
        education=[],
    )

    merged = merge_chunk_outputs(
        document,
        [
            TextChunk(
                ordinal=1,
                start_offset=0,
                end_offset=len(document.content),
                text=document.content,
            )
        ],
        [output],
    )

    assert merged.skills[0].evidence_status is EvidenceStatus.INSUFFICIENT
    assert merged.skills[0].unresolved_reason == "locator_unresolved"


def test_audit_metadata_does_not_contain_raw_document_or_prompt() -> None:
    audit = {
        "provider": "mock",
        "model": "fixture-model",
        "prompt_template_id": "cv_section_extraction",
        "outcome": "succeeded",
    }
    raw_document = "Skills: Python"
    raw_prompt = "Return every claim"

    serialized = json.dumps(audit)

    assert raw_document not in serialized
    assert raw_prompt not in serialized
