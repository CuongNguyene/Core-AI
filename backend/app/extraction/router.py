from enum import Enum


class CvExtractionPipeline(Enum):
    LEGACY_V2 = "legacy_v2"
    TWO_STAGE = "two_stage"


class JdExtractionMode(Enum):
    LEGACY_FULL = "legacy_full"
    REQUIREMENT_V2 = "requirement_v2"


class ExtractionMode(Enum):
    FULL_DOCUMENT = "full_document"
    SECTION_BASED = "section_based"


class ExtractionInputMode(Enum):
    NATIVE_PDF = "native_pdf"
    WHOLE_PARSED_TEXT = "whole_parsed_text"
    CHUNKED_TEXT = "chunked_text"


def choose_extraction_mode(text: str, threshold: int = 12_000) -> ExtractionMode:
    """Choose extraction strategy from normalized document length."""
    if len(text) <= threshold:
        return ExtractionMode.FULL_DOCUMENT
    return ExtractionMode.SECTION_BASED
