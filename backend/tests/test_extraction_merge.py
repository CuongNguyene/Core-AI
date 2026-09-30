import pytest

from app.extraction.chunking import TextChunk
from app.extraction.fixtures import FixtureDocument
from app.extraction.merge import locate_candidate, merge_chunk_outputs
from app.extraction.schemas import (
    ChunkExtractedClaim,
    CVChunkExtractionOutput,
    CVExtractionOutput,
    DocumentKind,
    EvidenceStatus,
    EvidenceType,
)


def test_locate_candidate_maps_exact_excerpt_to_document_relative_locator() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-basic",
        kind=DocumentKind.CV,
        content="Profile\nSkills: Python, FastAPI\nExperience: Built internal APIs.",
    )
    chunk = TextChunk(
        ordinal=1,
        start_offset=0,
        end_offset=len(document.content),
        text=document.content,
    )
    claim = ChunkExtractedClaim(
        value="Python",
        confidence=0.9,
        evidence_status=EvidenceStatus.SUPPORTED,
        source_excerpt="Python",
    )

    locator = locate_candidate(chunk, document, claim.source_excerpt or "")

    assert locator.document_id == "fixture-cv-basic"
    assert locator.section == "skills"
    assert locator.start_offset == document.content.index("Python")
    assert locator.end_offset == locator.start_offset + len("Python")


def test_merge_can_collect_forensics_without_changing_locator_behavior() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-basic",
        kind=DocumentKind.CV,
        content="Built  internal APIs",
    )
    chunks = [
        TextChunk(
            ordinal=1,
            start_offset=0,
            end_offset=len(document.content),
            text=document.content,
        )
    ]
    outputs = [
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="internal APIs",
                    confidence=0.8,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="Built internal APIs",
                )
            ],
            experience=[],
            education=[],
        )
    ]
    records: list[dict[str, object]] = []

    merged = merge_chunk_outputs(document, chunks, outputs, forensics_records=records)

    assert merged.skills[0].evidence_status is EvidenceStatus.SUPPORTED
    assert records[0]["raw_match_count"] == 0
    assert records[0]["diagnostic_matches"]["whitespace"]["matched"] is True


def test_merge_chunk_outputs_deduplicates_overlapping_evidence() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-basic",
        kind=DocumentKind.CV,
        content="abcdePythonfghij",
    )
    chunks = [
        TextChunk(ordinal=1, start_offset=0, end_offset=12, text=document.content[:12]),
        TextChunk(
            ordinal=2, start_offset=5, end_offset=len(document.content), text=document.content[5:]
        ),
    ]
    outputs = [
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="Python",
                    confidence=0.8,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="Python",
                )
            ],
            experience=[],
            education=[],
        ),
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="Python",
                    confidence=0.7,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="Python",
                )
            ],
            experience=[],
            education=[],
        ),
    ]

    merged = merge_chunk_outputs(document, chunks, outputs)

    assert isinstance(merged, CVExtractionOutput)
    assert len(merged.skills) == 1
    assert merged.skills[0].source_locator.start_offset == document.content.index("Python")


def test_merge_chunk_outputs_retains_non_overlapping_evidence() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-basic",
        kind=DocumentKind.CV,
        content="Skills: Python.\nExperience: Python.",
    )
    chunks = [
        TextChunk(ordinal=1, start_offset=0, end_offset=16, text=document.content[:16]),
        TextChunk(
            ordinal=2, start_offset=16, end_offset=len(document.content), text=document.content[16:]
        ),
    ]
    outputs = [
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="Python",
                    confidence=0.8,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="Python",
                )
            ],
            experience=[],
            education=[],
        ),
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="Python",
                    confidence=0.7,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="Python",
                )
            ],
            experience=[],
            education=[],
        ),
    ]

    merged = merge_chunk_outputs(document, chunks, outputs)

    assert len(merged.skills) == 1
    assert len(merged.skills[0].evidence) == 1


def test_merge_groups_distinct_evidence_types_without_losing_evidence() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-basic",
        kind=DocumentKind.CV,
        content="Skills: PyTorch.\nProject: Used PyTorch for image classification.",
    )
    chunks = [
        TextChunk(ordinal=1, start_offset=0, end_offset=16, text=document.content[:16]),
        TextChunk(
            ordinal=2, start_offset=16, end_offset=len(document.content), text=document.content[16:]
        ),
    ]
    outputs = [
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="PyTorch",
                    evidence_type=EvidenceType.EXPLICIT_SKILL,
                    confidence=0.8,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="PyTorch",
                )
            ],
            experience=[],
            education=[],
        ),
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="PyTorch",
                    evidence_type=EvidenceType.PROJECT_USAGE,
                    confidence=0.7,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="Used PyTorch",
                )
            ],
            experience=[],
            education=[],
        ),
    ]

    merged = merge_chunk_outputs(document, chunks, outputs)

    assert len(merged.skills) == 1
    assert merged.skills[0].evidence_type is EvidenceType.EXPLICIT_SKILL
    assert {item.evidence_type for item in merged.skills[0].evidence} == {
        EvidenceType.EXPLICIT_SKILL,
        EvidenceType.PROJECT_USAGE,
    }


def test_merge_classifies_activity_in_experience_bucket_as_work_evidence() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-legal",
        kind=DocumentKind.CV,
        content="Experience: Drafted and reviewed commercial contracts for company clients.",
    )
    chunk = TextChunk(
        ordinal=1,
        start_offset=0,
        end_offset=len(document.content),
        text=document.content,
    )
    output = CVChunkExtractionOutput(
        skills=[],
        experience=[
            ChunkExtractedClaim(
                value="Drafted and reviewed commercial contracts",
                evidence_type=EvidenceType.EXPLICIT_SKILL,
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt="Drafted and reviewed commercial contracts for company clients",
            )
        ],
        education=[],
    )

    merged = merge_chunk_outputs(document, [chunk], [output])

    assert merged.experience[0].evidence_type is EvidenceType.WORK_EXPERIENCE
    assert merged.experience[0].evidence[0].evidence_type is EvidenceType.WORK_EXPERIENCE


def test_merge_preserves_project_usage_context_in_experience_bucket() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-project",
        kind=DocumentKind.CV,
        content="Project: Built a data platform for the client.",
    )
    chunk = TextChunk(
        ordinal=1,
        start_offset=0,
        end_offset=len(document.content),
        text=document.content,
    )
    output = CVChunkExtractionOutput(
        skills=[],
        experience=[
            ChunkExtractedClaim(
                value="Built a data platform",
                evidence_type=EvidenceType.PROJECT_USAGE,
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt="Built a data platform for the client",
            )
        ],
        education=[],
    )

    merged = merge_chunk_outputs(document, [chunk], [output])

    assert merged.experience[0].evidence_type is EvidenceType.PROJECT_USAGE


def test_merge_keeps_education_and_certification_contexts_distinct() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-education",
        kind=DocumentKind.CV,
        content="Education: Bachelor of Data Science. AWS Certified Developer.",
    )
    chunk = TextChunk(
        ordinal=1,
        start_offset=0,
        end_offset=len(document.content),
        text=document.content,
    )
    output = CVChunkExtractionOutput(
        skills=[],
        experience=[],
        education=[
            ChunkExtractedClaim(
                value="Bachelor of Data Science",
                evidence_type=EvidenceType.EXPLICIT_SKILL,
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt="Bachelor of Data Science",
            ),
            ChunkExtractedClaim(
                value="AWS Certified Developer",
                evidence_type=EvidenceType.CERTIFICATION,
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt="AWS Certified Developer",
            ),
        ],
    )

    merged = merge_chunk_outputs(document, [chunk], [output])

    assert [item.evidence_type for item in merged.education] == [
        EvidenceType.EDUCATION,
        EvidenceType.CERTIFICATION,
    ]


def test_merge_keeps_stronger_duplicate_evidence_for_same_type() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-basic",
        kind=DocumentKind.CV,
        content="Skills: Python.\nProject: Python APIs.",
    )
    chunks = [
        TextChunk(ordinal=1, start_offset=0, end_offset=15, text=document.content[:15]),
        TextChunk(
            ordinal=2, start_offset=15, end_offset=len(document.content), text=document.content[15:]
        ),
    ]
    outputs = [
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="Python",
                    evidence_type=EvidenceType.EXPLICIT_SKILL,
                    confidence=0.5,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="Python",
                )
            ],
            experience=[],
            education=[],
        ),
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="Python",
                    evidence_type=EvidenceType.EXPLICIT_SKILL,
                    confidence=0.95,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="Python APIs",
                )
            ],
            experience=[],
            education=[],
        ),
    ]

    merged = merge_chunk_outputs(document, chunks, outputs)

    assert len(merged.skills) == 1
    assert merged.skills[0].confidence == 0.95
    assert merged.skills[0].source_excerpt == "Python APIs"


def test_merge_normalizes_aliases_but_preserves_original_evidence() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-basic",
        kind=DocumentKind.CV,
        content="Skills: pytorch.\nProject: torch.",
    )
    chunks = [
        TextChunk(ordinal=1, start_offset=0, end_offset=16, text=document.content[:16]),
        TextChunk(
            ordinal=2, start_offset=16, end_offset=len(document.content), text=document.content[16:]
        ),
    ]
    outputs = [
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="pytorch",
                    evidence_type=EvidenceType.EXPLICIT_SKILL,
                    confidence=0.8,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="pytorch",
                )
            ],
            experience=[],
            education=[],
        ),
        CVChunkExtractionOutput(
            skills=[
                ChunkExtractedClaim(
                    value="torch",
                    evidence_type=EvidenceType.PROJECT_USAGE,
                    confidence=0.7,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_excerpt="torch",
                )
            ],
            experience=[],
            education=[],
        ),
    ]

    merged = merge_chunk_outputs(document, chunks, outputs)

    assert len(merged.skills) == 1
    assert merged.skills[0].value == "pytorch"
    assert {item.source_excerpt for item in merged.skills[0].evidence} == {"pytorch", "torch"}


def test_merge_resolves_whitespace_variant_and_stores_canonical_excerpt() -> None:
    document = FixtureDocument(
        document_id="doc-1", kind=DocumentKind.CV, content="Skills: Python\nand FastAPI"
    )
    chunk = TextChunk(
        ordinal=1,
        start_offset=0,
        end_offset=len(document.content),
        text=document.content,
    )
    output = CVChunkExtractionOutput(
        skills=[
            ChunkExtractedClaim(
                value="Python and FastAPI",
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt="Python and FastAPI",
            )
        ],
        experience=[],
        education=[],
    )

    merged = merge_chunk_outputs(document, [chunk], [output])

    assert merged.skills[0].source_excerpt == "Python\nand FastAPI"
    assert merged.skills[0].source_locator is not None


def test_locate_candidate_normalizes_nbsp_unicode_and_line_endings_to_original_offsets() -> None:
    document = FixtureDocument(
        document_id="doc-normalized",
        kind=DocumentKind.CV,
        content="Skills:\u00a0Café\r\nPython",
    )
    chunk = TextChunk(
        ordinal=1,
        start_offset=0,
        end_offset=len(document.content),
        text=document.content,
    )

    locator = locate_candidate(chunk, document, "Cafe\u0301  Python")

    start = document.content.index("Café")
    assert locator.start_offset == start
    assert document.content[locator.start_offset : locator.end_offset] == "Café\r\nPython"


def test_merge_rejects_punctuation_difference_outside_conservative_normalization() -> None:
    document = FixtureDocument(
        document_id="doc-2", kind=DocumentKind.CV, content="Skills: Python, FastAPI"
    )
    chunk = TextChunk(
        ordinal=1,
        start_offset=0,
        end_offset=len(document.content),
        text=document.content,
    )
    output = CVChunkExtractionOutput(
        skills=[
            ChunkExtractedClaim(
                value="Python FastAPI",
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt="Python FastAPI",
            )
        ],
        experience=[],
        education=[],
    )

    merged = merge_chunk_outputs(document, [chunk], [output])

    assert merged.skills[0].evidence_status is EvidenceStatus.INSUFFICIENT
    assert merged.skills[0].unresolved_reason == "locator_unresolved"


def test_merge_keeps_unresolved_locator_as_insufficient_claim() -> None:
    document = FixtureDocument(
        document_id="doc-unresolved",
        kind=DocumentKind.CV,
        content="Skills: Python",
    )
    chunk = TextChunk(
        ordinal=1,
        start_offset=0,
        end_offset=len(document.content),
        text=document.content,
    )
    output = CVChunkExtractionOutput(
        skills=[
            ChunkExtractedClaim(
                value="Production Python deployment",
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt="Production Python deployment",
            )
        ],
        experience=[],
        education=[],
    )

    merged = merge_chunk_outputs(document, [chunk], [output])

    assert len(merged.skills) == 1
    assert merged.skills[0].value is None
    assert merged.skills[0].evidence_status is EvidenceStatus.INSUFFICIENT
    assert merged.skills[0].source_locator is None
    assert merged.skills[0].source_excerpt is None
    assert merged.skills[0].unresolved_reason == "locator_unresolved"


@pytest.mark.parametrize(
    "excerpt",
    ["Java", "Python"],
)
def test_merge_chunk_outputs_fails_closed_for_missing_or_ambiguous_excerpt(excerpt: str) -> None:
    document = FixtureDocument(
        document_id="fixture-cv-basic",
        kind=DocumentKind.CV,
        content="Skills: Python and Python.",
    )
    chunk = TextChunk(
        ordinal=1,
        start_offset=0,
        end_offset=len(document.content),
        text=document.content,
    )
    output = CVChunkExtractionOutput(
        skills=[
            ChunkExtractedClaim(
                value="Python",
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_excerpt=excerpt,
            )
        ],
        experience=[],
        education=[],
    )

    merged = merge_chunk_outputs(document, [chunk], [output])

    assert merged.skills[0].evidence_status is EvidenceStatus.INSUFFICIENT
    assert merged.skills[0].unresolved_reason == "locator_unresolved"
