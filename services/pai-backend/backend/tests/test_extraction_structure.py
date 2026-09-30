import pytest
from pydantic import ValidationError

from app.extraction.schemas import (
    DocumentSection,
    DocumentStructureOutput,
    SectionType,
)
from app.extraction.structure import detect_document_structure


def test_detect_document_structure_maps_cv_headings_to_non_overlapping_offsets() -> None:
    text = (
        "PROFILE\nAI engineer\n\n"
        "EXPERIENCE\nSoftware Engineer\nBuilt APIs.\n\n"
        "EDUCATION\nBachelor Computer Science\n"
    )

    result = detect_document_structure(text, document_type="cv")

    assert result.document_type == "cv"
    assert [section.section_type for section in result.sections] == [
        SectionType.UNKNOWN,
        SectionType.EXPERIENCE,
        SectionType.EDUCATION,
    ]
    assert result.sections[1].start_offset == text.index("EXPERIENCE")
    assert result.sections[1].end_offset == text.index("EDUCATION")
    assert result.sections[2].end_offset == len(text)
    assert all(
        0 <= section.start_offset < section.end_offset <= len(text) for section in result.sections
    )


def test_detect_document_structure_supports_jd_headings() -> None:
    text = "RESPONSIBILITIES\nBuild models.\n\nQUALIFICATIONS\nPython experience."

    result = detect_document_structure(text, document_type="jd")

    assert [section.section_type for section in result.sections] == [
        SectionType.RESPONSIBILITIES,
        SectionType.QUALIFICATIONS,
    ]


def test_document_section_rejects_invalid_offsets_and_confidence() -> None:
    with pytest.raises(ValidationError):
        DocumentSection(
            section_type=SectionType.SKILLS,
            start_offset=10,
            end_offset=10,
            confidence=1.1,
        )


def test_document_structure_output_requires_sections() -> None:
    result = DocumentStructureOutput(document_type="unknown", sections=[])

    assert result.sections == []
