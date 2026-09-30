from collections.abc import Collection

from .schemas import ContentGenerationRequest, ContentGenerationResult


def _ensure_unique(values: Collection[str], *, code: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(code)


def _ensure_contiguous_sequences(sequences: list[int], *, code: str) -> None:
    if sequences != list(range(1, len(sequences) + 1)):
        raise ValueError(code)


def validate_content_generation_request(request: ContentGenerationRequest) -> None:
    """Validate request references without resolving or loading source content."""

    _ensure_unique(request.objective_refs, code="duplicate_objective_reference")


def validate_content_generation_result(result: ContentGenerationResult) -> None:
    """Validate result structure and section ordering without generating content."""

    _ensure_contiguous_sequences(
        [section.order for section in result.sections],
        code="invalid_section_order",
    )
