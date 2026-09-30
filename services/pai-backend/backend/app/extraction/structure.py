import re
import unicodedata

from app.extraction.schemas import DocumentSection, DocumentStructureOutput, SectionType

_HEADING_ALIASES: dict[str, SectionType] = {
    "EXPERIENCE": SectionType.EXPERIENCE,
    "WORK EXPERIENCE": SectionType.EXPERIENCE,
    "PROFESSIONAL EXPERIENCE": SectionType.EXPERIENCE,
    "EMPLOYMENT HISTORY": SectionType.EXPERIENCE,
    "EDUCATION": SectionType.EDUCATION,
    "ACADEMIC BACKGROUND": SectionType.EDUCATION,
    "SKILLS": SectionType.SKILLS,
    "TECHNICAL SKILLS": SectionType.SKILLS,
    "TECHNICAL PROFICIENCIES": SectionType.SKILLS,
    "CORE SKILLS": SectionType.SKILLS,
    "PROJECTS": SectionType.PROJECTS,
    "SELECTED PROJECTS": SectionType.PROJECTS,
    "PUBLICATIONS": SectionType.PUBLICATIONS,
    "RESEARCH": SectionType.PUBLICATIONS,
    "QUALIFICATIONS": SectionType.QUALIFICATIONS,
    "REQUIREMENTS": SectionType.QUALIFICATIONS,
    "REQUIREMENTS AND QUALIFICATIONS": SectionType.QUALIFICATIONS,
    "RESPONSIBILITIES": SectionType.RESPONSIBILITIES,
    "JOB RESPONSIBILITIES": SectionType.RESPONSIBILITIES,
}


def detect_document_structure(text: str, document_type: str = "unknown") -> DocumentStructureOutput:
    """Detect section boundaries from explicit headings in normalized text."""
    headings: list[tuple[int, SectionType, float]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        heading = _classify_heading(line)
        if heading is not None:
            section_type, confidence = heading
            headings.append((offset, section_type, confidence))
        offset += len(line)

    sections = [
        DocumentSection(
            section_type=section_type,
            start_offset=start_offset,
            end_offset=headings[index + 1][0] if index + 1 < len(headings) else len(text),
            confidence=confidence,
        )
        for index, (start_offset, section_type, confidence) in enumerate(headings)
        if (headings[index + 1][0] if index + 1 < len(headings) else len(text)) > start_offset
    ]
    return DocumentStructureOutput(document_type=document_type, sections=sections)


def _classify_heading(line: str) -> tuple[SectionType, float] | None:
    candidate = line.strip()
    if not candidate:
        return None
    normalized = _normalize_heading(candidate)
    section_type = _HEADING_ALIASES.get(normalized)
    if section_type is not None:
        return section_type, 0.95
    if _looks_like_unknown_heading(candidate):
        return SectionType.UNKNOWN, 0.5
    return None


def _normalize_heading(value: str) -> str:
    without_marks = "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", without_marks).strip()
    return normalized.upper()


def _looks_like_unknown_heading(value: str) -> bool:
    candidate = value.rstrip(":").strip()
    if len(candidate) > 80 or any(char in candidate for char in ".!?;"):
        return False
    letters = [char for char in candidate if char.isalpha()]
    return bool(letters) and candidate.upper() == candidate
