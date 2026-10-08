"""Fail-closed validation of model statements against server-authored source blocks."""

from __future__ import annotations

from collections.abc import Sequence

from app.job_semantics_eval.contracts import (
    JobRequirementExtractionOutputV1,
    ValidatedRequirementStatement,
)
from app.job_semantics_eval.source_adapter import JobSourceBlock

_TERMINAL_PUNCTUATION = ".!?;:"


class InvalidProviderProvenance(ValueError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.raw_statement_count = 0


def _normalized_fidelity_key(value: str) -> str:
    stripped = value.strip()
    while stripped and stripped[-1] in _TERMINAL_PUNCTUATION:
        stripped = stripped[:-1]
    return stripped


def _all_occurrences(text: str, span: str) -> tuple[int, ...]:
    offsets: list[int] = []
    start = 0
    while True:
        offset = text.find(span, start)
        if offset < 0:
            return tuple(offsets)
        offsets.append(offset)
        start = offset + 1


def validate_extraction_output(
    output: JobRequirementExtractionOutputV1,
    source_blocks: Sequence[JobSourceBlock],
) -> tuple[ValidatedRequirementStatement, ...]:
    """Validate all provider provenance; never repair an invalid model span."""
    blocks_by_id = {block.block_id: block for block in source_blocks}
    if len(blocks_by_id) != len(source_blocks):
        raise InvalidProviderProvenance(
            "invalid_output_duplicate_server_block", "server block IDs are not unique"
        )

    ordered_blocks = tuple(source_blocks)
    field_offsets: dict[str, dict[str, int]] = {}
    cursor_by_field: dict[str, int] = {}
    for field in ("JOB_DESCRIPTION", "JOB_REQUIREMENTS"):
        cursor = 0
        field_offsets[field] = {}
        for block in ordered_blocks:
            if block.source_field == field:
                field_offsets[field][block.block_id] = cursor
                cursor += len(block.text) + 1
        cursor_by_field[field] = cursor

    validated: list[ValidatedRequirementStatement] = []
    for output_index, statement in enumerate(output.statements):
        block_ids = tuple(statement.source_block_ids)
        if len(set(block_ids)) != len(block_ids):
            raise InvalidProviderProvenance(
                "invalid_output_block_reference", "duplicate source block reference"
            )
        unknown = [block_id for block_id in block_ids if block_id not in blocks_by_id]
        if unknown:
            raise InvalidProviderProvenance(
                "invalid_output_unknown_block", "unknown source block reference"
            )
        selected = tuple(blocks_by_id[block_id] for block_id in block_ids)
        fields = {block.source_field for block in selected}
        if len(fields) != 1:
            raise InvalidProviderProvenance("invalid_output_source_field", "mixed source fields")
        field = selected[0].source_field
        if any(
            current.source_order != previous.source_order + 1
            for previous, current in zip(selected, selected[1:], strict=False)
        ):
            raise InvalidProviderProvenance(
                "invalid_output_block_order", "source_block_ids must be adjacent blocks only"
            )

        selected_view = "\n".join(block.text for block in selected)
        occurrences = _all_occurrences(selected_view, statement.source_text)
        if not occurrences:
            raise InvalidProviderProvenance(
                "invalid_output_invented_span",
                "source_text is not a contiguous visible-text span of cited blocks",
            )
        local_offset = occurrences[0]
        first_block_order = selected[0].source_order
        absolute_offset = field_offsets[field][selected[0].block_id] + local_offset

        if _normalized_fidelity_key(statement.normalized_statement) != _normalized_fidelity_key(
            statement.source_text
        ):
            raise InvalidProviderProvenance(
                "invalid_output_normalization", "normalized_statement changes source content"
            )
        signal = statement.capability_signal_text
        if signal is not None and (not signal.strip() or signal not in statement.source_text):
            raise InvalidProviderProvenance(
                "invalid_output_signal_span", "capability signal is not an exact source span"
            )
        if not 0 <= absolute_offset < cursor_by_field[field]:
            raise InvalidProviderProvenance(
                "invalid_output_offset", "source offset is outside field"
            )

        validated.append(
            ValidatedRequirementStatement(
                source_block_ids=block_ids,
                source_field=field,  # type: ignore[arg-type]
                block_order=first_block_order,
                start_offset=absolute_offset,
                end_offset=absolute_offset + len(statement.source_text),
                source_text=statement.source_text,
                normalized_statement=statement.normalized_statement,
                statement_type=statement.statement_type,
                capability_relevance=statement.capability_relevance,
                capability_signal_text=signal,
                output_index=output_index,
            )
        )
    return tuple(validated)
