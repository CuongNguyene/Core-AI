from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.extraction.schemas import DocumentSection, SectionType


class ExtractionChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ordinal: int = Field(ge=1)
    section_type: SectionType = SectionType.UNKNOWN
    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)

    @classmethod
    def from_slice(
        cls,
        *,
        ordinal: int,
        section_type: SectionType,
        content: str,
        start_offset: int,
        end_offset: int,
    ) -> "ExtractionChunk":
        return cls(
            ordinal=ordinal,
            section_type=section_type,
            text=content[start_offset:end_offset],
            start_offset=start_offset,
            end_offset=end_offset,
        )


# Compatibility name for callers that still use the full-document splitter.
TextChunk = ExtractionChunk


def split_document(
    content: str, max_chars: int = 2000, overlap_chars: int = 150
) -> list[ExtractionChunk]:
    """Split a document without structure metadata for full-document mode."""
    _validate_chunk_settings(max_chars, overlap_chars)
    return _split_range(
        content,
        section_type=SectionType.UNKNOWN,
        section_start=0,
        section_end=len(content),
        max_chars=max_chars,
        overlap_chars=overlap_chars,
        ordinal_start=1,
    )


def split_sections(
    content: str,
    sections: Sequence[DocumentSection],
    max_chars: int = 2000,
    overlap_chars: int = 150,
) -> list[ExtractionChunk]:
    """Split each document section independently without crossing boundaries."""
    _validate_chunk_settings(max_chars, overlap_chars)
    _validate_sections(content, sections)

    chunks: list[ExtractionChunk] = []
    next_ordinal = 1
    for section in sections:
        section_chunks = _split_range(
            content,
            section_type=section.section_type,
            section_start=section.start_offset,
            section_end=section.end_offset,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
            ordinal_start=next_ordinal,
        )
        chunks.extend(section_chunks)
        next_ordinal += len(section_chunks)
    return chunks


def _split_range(
    content: str,
    *,
    section_type: SectionType,
    section_start: int,
    section_end: int,
    max_chars: int,
    overlap_chars: int,
    ordinal_start: int,
) -> list[ExtractionChunk]:
    chunks: list[ExtractionChunk] = []
    start = section_start
    ordinal = ordinal_start

    while start < section_end:
        limit = min(start + max_chars, section_end)
        end = limit

        if limit < section_end:
            paragraph_boundary = content.rfind("\n\n", start, limit)
            preferred_start = start + overlap_chars
            if paragraph_boundary >= preferred_start:
                end = paragraph_boundary + 2
            else:
                newline_boundary = content.rfind("\n", start, limit)
                if newline_boundary >= preferred_start:
                    end = newline_boundary + 1

        if end <= start:
            end = limit

        chunks.append(
            ExtractionChunk.from_slice(
                ordinal=ordinal,
                section_type=section_type,
                content=content,
                start_offset=start,
                end_offset=end,
            )
        )
        ordinal += 1

        if end >= section_end:
            break

        next_start = max(section_start, end - overlap_chars)
        if next_start <= start:
            next_start = start + 1
        start = next_start

    return chunks


def _validate_chunk_settings(max_chars: int, overlap_chars: int) -> None:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars <= 0:
        raise ValueError("overlap_chars must be positive")
    if max_chars <= overlap_chars:
        raise ValueError("max_chars must be greater than overlap_chars")


def _validate_sections(content: str, sections: Sequence[DocumentSection]) -> None:
    previous_end = 0
    for section in sections:
        if section.start_offset < previous_end:
            raise ValueError("sections must be sorted and non-overlapping")
        if section.end_offset > len(content):
            raise ValueError("section offset exceeds document length")
        previous_end = section.end_offset
