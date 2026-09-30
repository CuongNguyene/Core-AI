import pytest
from pydantic import ValidationError

from app.extraction.fixtures import FixtureDocumentSource
from app.extraction.schemas import (
    ChunkExtractedClaim,
    CVChunkExtractionOutput,
    CVExtractionOutput,
    DocumentKind,
    EvidenceStatus,
    ExtractedClaim,
    ExtractionProfile,
    ReviewState,
    SourceLocator,
)


def test_supported_claim_requires_complete_source_evidence() -> None:
    with pytest.raises(ValidationError):
        ExtractedClaim(
            value="Python",
            confidence=0.9,
            evidence_status=EvidenceStatus.SUPPORTED,
        )


def test_unknown_claim_has_no_invented_value_or_source() -> None:
    claim = ExtractedClaim(
        value=None,
        confidence=0.0,
        evidence_status=EvidenceStatus.UNKNOWN,
    )

    assert claim.value is None
    assert claim.source_locator is None
    assert claim.source_excerpt is None


def test_supported_chunk_claim_requires_value_confidence_and_excerpt_only() -> None:
    claim = ChunkExtractedClaim(
        value="Python",
        confidence=0.9,
        evidence_status=EvidenceStatus.SUPPORTED,
        source_excerpt="Python",
    )

    assert claim.value == "Python"
    assert claim.source_excerpt == "Python"
    assert not hasattr(claim, "source_locator")


def test_source_excerpt_is_bounded_to_limit_sensitive_evidence_exposure() -> None:
    with pytest.raises(ValidationError):
        ExtractedClaim(
            value="Python",
            confidence=0.9,
            evidence_status=EvidenceStatus.SUPPORTED,
            source_locator=SourceLocator(
                document_id="fixture-cv-basic",
                section="skills",
                start_offset=0,
                end_offset=6,
            ),
            source_excerpt="x" * 501,
        )


def test_chunk_source_excerpt_is_bounded_to_limit_sensitive_evidence_exposure() -> None:
    with pytest.raises(ValidationError):
        ChunkExtractedClaim(
            value="Python",
            confidence=0.9,
            evidence_status=EvidenceStatus.SUPPORTED,
            source_excerpt="x" * 501,
        )


def test_fixture_document_source_returns_known_cv_with_stable_locator() -> None:
    source = FixtureDocumentSource.default()

    document = source.get("fixture-cv-basic", DocumentKind.CV)
    locator = source.locate(document, "Python")

    assert document.kind is DocumentKind.CV
    assert locator.document_id == "fixture-cv-basic"
    assert locator.start_offset < locator.end_offset
    assert document.content[locator.start_offset : locator.end_offset] == "Python"


def test_source_locator_rejects_invalid_character_range() -> None:
    with pytest.raises(ValidationError):
        SourceLocator(
            document_id="fixture-cv-basic",
            section="skills",
            start_offset=10,
            end_offset=10,
        )


def test_accepted_profile_requires_reviewer_and_timestamp() -> None:
    with pytest.raises(ValidationError):
        ExtractionProfile(
            id="profile-1",
            job_id="job-1",
            document_id="fixture-cv-basic",
            document_kind=DocumentKind.CV,
            owner_actor_id="candidate-1",
            version=1,
            review_state=ReviewState.ACCEPTED,
            output=CVExtractionOutput(skills=[], experience=[], education=[]),
            audit={},
        )


def test_chunk_output_schema_accepts_supported_candidates_without_locators() -> None:
    output = CVChunkExtractionOutput(
        skills=[
            ChunkExtractedClaim(
                value="Python",
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt="Python",
            )
        ],
        experience=[],
        education=[],
    )

    assert output.skills[0].source_excerpt == "Python"
