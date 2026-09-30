from app.extraction.chunking import split_sections
from app.extraction.router import ExtractionMode, choose_extraction_mode
from app.extraction.schemas import SectionType
from app.extraction.structure import detect_document_structure


def test_small_cv_uses_full_document_mode() -> None:
    assert choose_extraction_mode("x" * 5_000) is ExtractionMode.FULL_DOCUMENT


def test_large_cv_uses_section_based_mode() -> None:
    assert choose_extraction_mode("x" * 20_000) is ExtractionMode.SECTION_BASED


def test_cross_section_entity_stays_in_its_declared_section() -> None:
    text = "EDUCATION\nBS Computer Science\n\nSKILLS\nPython\n"

    structure = detect_document_structure(text, document_type="cv")
    chunks = split_sections(text, structure.sections, max_chars=2000, overlap_chars=150)

    education_chunks = [chunk for chunk in chunks if chunk.section_type is SectionType.EDUCATION]
    skill_chunks = [chunk for chunk in chunks if chunk.section_type is SectionType.SKILLS]
    assert education_chunks and skill_chunks
    assert all("Python" not in chunk.text for chunk in education_chunks)
    assert any("Python" in chunk.text for chunk in skill_chunks)
