"""Normalization and fail-closed validation for the requirement-oriented JD contract."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.extraction.schemas import (
    JDRequirementExtractionOutputV2,
    JDRequirementExtractionOutputV2Pdf,
    JDRequirementExtractionOutputV2Text,
    JDRequirementExtractionV2,
    NativePdfLocator,
    ProviderPdfLocator,
    SourceLocator,
)


@dataclass(frozen=True)
class ResolvedSpan:
    start_offset: int
    end_offset: int


def resolve_exact_source_excerpt(
    document_text: str, source_excerpt: str, *, require_unique: bool = True
) -> ResolvedSpan:
    """Resolve one unique excerpt in the authoritative parsed document.

    Providers commonly collapse line breaks or non-breaking spaces while quoting
    DOCX text. Those formatting differences do not change the source evidence,
    so accept one whitespace-normalized match and persist the exact source span.
    """

    if not source_excerpt:
        raise ValueError("source_excerpt_not_found")
    first = document_text.find(source_excerpt)
    if first >= 0:
        second = document_text.find(source_excerpt, first + len(source_excerpt))
        if second >= 0 and require_unique:
            raise ValueError("ambiguous_source_excerpt")
        return ResolvedSpan(first, first + len(source_excerpt))

    normalized_document, original_spans = _normalize_whitespace(document_text)
    normalized_excerpt, _ = _normalize_whitespace(source_excerpt)
    if not normalized_excerpt:
        raise ValueError("source_excerpt_not_found")
    first = normalized_document.find(normalized_excerpt)
    if first < 0:
        raise ValueError("source_excerpt_not_found")
    second = normalized_document.find(normalized_excerpt, first + len(normalized_excerpt))
    if second >= 0 and require_unique:
        raise ValueError("ambiguous_source_excerpt")
    start_offset = original_spans[first][0]
    end_offset = original_spans[first + len(normalized_excerpt) - 1][1]
    return ResolvedSpan(start_offset, end_offset)


def _normalize_whitespace(value: str) -> tuple[str, list[tuple[int, int]]]:
    """Collapse whitespace while retaining offsets into the original text."""

    normalized: list[str] = []
    original_spans: list[tuple[int, int]] = []
    index = 0
    while index < len(value):
        if value[index].isspace():
            start = index
            while index < len(value) and value[index].isspace():
                index += 1
            if normalized:
                normalized.append(" ")
                original_spans.append((start, index))
            continue
        normalized.append(value[index])
        original_spans.append((index, index + 1))
        index += 1

    while normalized and normalized[-1] == " ":
        normalized.pop()
        original_spans.pop()
    return "".join(normalized), original_spans


def bind_jd_requirement_source_document(
    output: JDRequirementExtractionOutputV2
    | JDRequirementExtractionOutputV2Pdf
    | JDRequirementExtractionOutputV2Text,
    *,
    document_id: str,
    parsed_text: str,
    is_pdf: bool = False,
    page_texts: Sequence[str] | None = None,
) -> JDRequirementExtractionOutputV2:
    """Bind every supported JD V2 locator to the backend-owned document identity.

    The provider selects the source span, but its echoed document identity is not
    authoritative. This helper changes only that identity before grounding is
    checked against the supplied backend document text.
    """

    requirements: list[JDRequirementExtractionV2] = []
    for requirement in output.requirements:
        locator = requirement.source_locator
        excerpt = requirement.source_excerpt
        if requirement.evidence_status.value == "supported" and locator is not None and excerpt:
            if isinstance(locator, (NativePdfLocator, ProviderPdfLocator)):
                if not is_pdf:
                    raise ValueError("text_requires_span_locator")
                if page_texts is None or locator.page_number > len(page_texts):
                    raise ValueError("native_pdf_invalid_page")
                page_text = page_texts[locator.page_number - 1]
                try:
                    resolved = resolve_exact_source_excerpt(
                        page_text, excerpt, require_unique=False
                    )
                except ValueError as exc:
                    raise ValueError("source_excerpt_page_mismatch") from exc
                normalized_locator: SourceLocator | NativePdfLocator = NativePdfLocator(
                    document_id=document_id,
                    page_number=locator.page_number,
                    section=locator.section,
                )
                source_excerpt = page_text[resolved.start_offset : resolved.end_offset]
            else:
                if is_pdf:
                    raise ValueError("pdf_requires_page_locator")
                resolved = resolve_exact_source_excerpt(parsed_text, excerpt)
                normalized_locator = SourceLocator(
                    document_id=document_id,
                    section=locator.section or "document",
                    start_offset=resolved.start_offset,
                    end_offset=resolved.end_offset,
                )
                source_excerpt = parsed_text[resolved.start_offset : resolved.end_offset]
            requirement = requirement.model_copy(
                update={"source_locator": normalized_locator, "source_excerpt": source_excerpt}
            )
        requirements.append(JDRequirementExtractionV2.model_validate(requirement, strict=False))
    return JDRequirementExtractionOutputV2(requirements=requirements)


def validate_requirement_v2_output(
    output: JDRequirementExtractionOutputV2,
    expected_document_id: str,
    document_text: str,
    *,
    page_texts: Sequence[str] | None = None,
) -> None:
    """Validate stable requirement identity and exact document provenance."""

    seen: set[str] = set()
    for requirement in output.requirements:
        if requirement.evidence_status.value != "supported":
            continue
        requirement_id = requirement.requirement_id
        if not requirement_id or not requirement_id.strip():
            raise ValueError("missing_requirement_id")
        if requirement_id in seen:
            raise ValueError("duplicate_requirement_id")
        seen.add(requirement_id)
        locator = requirement.source_locator
        if locator is None:
            raise ValueError("missing_source_locator")
        if locator.document_id != expected_document_id:
            raise ValueError("invalid_source_locator_document")
        excerpt = requirement.source_excerpt
        if not excerpt:
            raise ValueError("missing_source_excerpt")
        if isinstance(locator, NativePdfLocator):
            if page_texts is None or locator.page_number > len(page_texts):
                raise ValueError("native_pdf_invalid_page")
            if excerpt not in page_texts[locator.page_number - 1]:
                raise ValueError("source_excerpt_page_mismatch")
        elif isinstance(locator, ProviderPdfLocator):
            raise ValueError("unbound_pdf_locator")
        else:
            if (
                locator.start_offset is None
                or locator.end_offset is None
                or locator.end_offset > len(document_text)
            ):
                raise ValueError("source_locator_out_of_bounds")
            if document_text[locator.start_offset : locator.end_offset] != excerpt:
                raise ValueError("source_excerpt_mismatch")
