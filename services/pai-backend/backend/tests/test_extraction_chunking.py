import pytest

from app.extraction.chunking import ExtractionChunk, TextChunk, split_document, split_sections
from app.extraction.schemas import DocumentSection, SectionType


def test_split_document_prefers_newline_before_hard_cut() -> None:
    content = "a" * 1990 + "\n" + "b" * 300

    chunks = split_document(content, max_chars=2000, overlap_chars=150)

    assert chunks == [
        TextChunk(ordinal=1, start_offset=0, end_offset=1991, text=content[:1991]),
        TextChunk(ordinal=2, start_offset=1841, end_offset=2291, text=content[1841:]),
    ]


def test_split_document_uses_requested_overlap_and_short_final_chunk() -> None:
    content = "intro\n" + ("x" * 2200)

    chunks = split_document(content, max_chars=2000, overlap_chars=150)

    assert len(chunks) == 2
    assert chunks[1].start_offset == chunks[0].end_offset - 150
    assert chunks[1].end_offset == len(content)
    assert len(chunks[1].text) < 2000


def test_split_sections_never_crosses_section_boundaries() -> None:
    content = "EXPERIENCE\n" + ("a" * 80) + "\nEDUCATION\n" + ("b" * 80)
    education_start = content.index("EDUCATION")
    sections = [
        DocumentSection(
            section_type=SectionType.EXPERIENCE,
            start_offset=0,
            end_offset=education_start,
            confidence=0.95,
        ),
        DocumentSection(
            section_type=SectionType.EDUCATION,
            start_offset=education_start,
            end_offset=len(content),
            confidence=0.95,
        ),
    ]

    chunks = split_sections(content, sections, max_chars=50, overlap_chars=10)

    assert all(isinstance(chunk, ExtractionChunk) for chunk in chunks)
    assert {chunk.section_type for chunk in chunks} == {
        SectionType.EXPERIENCE,
        SectionType.EDUCATION,
    }
    for chunk in chunks:
        section = next(
            section for section in sections if section.section_type is chunk.section_type
        )
        assert section.start_offset <= chunk.start_offset < chunk.end_offset <= section.end_offset
        assert chunk.text == content[chunk.start_offset : chunk.end_offset]


def test_split_sections_keeps_overlap_inside_each_section() -> None:
    content = "SKILLS\n" + ("x" * 180)
    section = DocumentSection(
        section_type=SectionType.SKILLS,
        start_offset=0,
        end_offset=len(content),
        confidence=0.95,
    )

    chunks = split_sections(content, [section], max_chars=100, overlap_chars=20)

    assert len(chunks) == 3
    assert chunks[1].start_offset == chunks[0].end_offset - 20
    assert all(chunk.section_type is SectionType.SKILLS for chunk in chunks)


@pytest.mark.parametrize(
    ("max_chars", "overlap_chars"),
    [
        (0, 150),
        (2000, 0),
        (150, 150),
        (100, 150),
    ],
)
def test_split_document_rejects_invalid_chunk_settings(max_chars: int, overlap_chars: int) -> None:
    with pytest.raises(ValueError):
        split_document("abc", max_chars=max_chars, overlap_chars=overlap_chars)
