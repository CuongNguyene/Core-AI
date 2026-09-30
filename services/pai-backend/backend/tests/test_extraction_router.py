from app.extraction.router import ExtractionMode, choose_extraction_mode


def test_documents_at_or_below_threshold_use_full_document_mode() -> None:
    assert choose_extraction_mode("x" * 12_000) is ExtractionMode.FULL_DOCUMENT


def test_documents_above_threshold_use_section_based_mode() -> None:
    assert choose_extraction_mode("x" * 12_001) is ExtractionMode.SECTION_BASED


def test_custom_threshold_is_respected() -> None:
    assert choose_extraction_mode("x" * 101, threshold=100) is ExtractionMode.SECTION_BASED
