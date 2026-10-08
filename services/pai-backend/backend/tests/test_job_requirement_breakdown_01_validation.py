from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.job_semantics_eval.contracts import (
    JobRequirementExtractionOutputV1,
    PredictedJobRequirementStatement,
)
from app.job_semantics_eval.source_adapter import build_source_blocks
from app.job_semantics_eval.validation import validate_extraction_output


def _statement(**overrides: object) -> dict[str, object]:
    return {
        "source_block_ids": ["jdblock:JOB_DESCRIPTION:0001"],
        "source_text": "Develop and maintain APIs.",
        "normalized_statement": "Develop and maintain APIs.",
        "statement_type": "RESPONSIBILITY",
        "capability_relevance": "CAPABILITY_BEARING",
        **overrides,
    }


def test_output_contract_is_strict_and_excludes_semantic_confidence_and_mapping() -> None:
    parsed = PredictedJobRequirementStatement.model_validate(_statement(), strict=True)
    assert parsed.capability_signal_text is None
    with pytest.raises(ValidationError):
        PredictedJobRequirementStatement.model_validate(
            _statement(semantic_confidence=0.9), strict=True
        )
    with pytest.raises(ValidationError):
        PredictedJobRequirementStatement.model_validate(
            _statement(canonical_capability_ref="finance.reporting"), strict=True
        )
    with pytest.raises(ValidationError):
        JobRequirementExtractionOutputV1.model_validate(
            {"statements": [], "unrecognized": True}, strict=True
        )


def test_validator_rejects_unknown_block_and_invented_source_span() -> None:
    source = {"job_description_html": "<p>Develop and maintain APIs.</p>"}
    blocks = build_source_blocks(source)
    with pytest.raises(ValueError, match="unknown source block"):
        validate_extraction_output(
            JobRequirementExtractionOutputV1.model_validate(
                {"statements": [_statement(source_block_ids=["unknown"])]}, strict=True
            ),
            blocks,
        )
    with pytest.raises(ValueError, match="not a contiguous visible-text span"):
        validate_extraction_output(
            JobRequirementExtractionOutputV1.model_validate(
                {"statements": [_statement(source_text="Invented API claim.")]}, strict=True
            ),
            blocks,
        )


def test_validator_derives_source_field_and_span_offsets_server_side() -> None:
    blocks = build_source_blocks(
        {
            "job_description_html": "<p>Prepare monthly financial reports.</p>",
            "job_requirements_html": "<p>Three years of reporting experience.</p>",
        }
    )
    output = JobRequirementExtractionOutputV1.model_validate(
        {
            "statements": [
                {
                    "source_block_ids": ["jdblock:JOB_REQUIREMENTS:0001"],
                    "source_text": "Three years of reporting experience.",
                    "normalized_statement": "Three years of reporting experience.",
                    "statement_type": "EXPERIENCE_REQUIREMENT",
                    "capability_relevance": "CAPABILITY_BEARING",
                    "capability_signal_text": "reporting experience",
                }
            ]
        },
        strict=True,
    )

    validated = validate_extraction_output(output, blocks)

    assert len(validated) == 1
    assert validated[0].source_field == "JOB_REQUIREMENTS"
    assert validated[0].block_order == 1
    assert validated[0].start_offset == 0
    assert validated[0].end_offset == len(validated[0].source_text)


def test_validator_rejects_noncontiguous_block_refs_and_normalization_rewrite() -> None:
    blocks = build_source_blocks(
        {
            "job_description_html": (
                "<p>Prepare reports.</p><p>Review controls.</p><p>Coordinate teams.</p>"
            )
        }
    )
    base = {
        "source_text": "Prepare reports.\nCoordinate teams.",
        "normalized_statement": "Prepare reports.\nCoordinate teams.",
        "statement_type": "RESPONSIBILITY",
        "capability_relevance": "CAPABILITY_BEARING",
    }
    with pytest.raises(ValueError, match="must be adjacent blocks"):
        validate_extraction_output(
            JobRequirementExtractionOutputV1.model_validate(
                {
                    "statements": [
                        {**base, "source_block_ids": [blocks[0].block_id, blocks[2].block_id]}
                    ]
                },
                strict=True,
            ),
            blocks,
        )

    with pytest.raises(ValueError, match="normalized_statement changes source content"):
        validate_extraction_output(
            JobRequirementExtractionOutputV1.model_validate(
                {
                    "statements": [
                        {
                            "source_block_ids": [blocks[0].block_id],
                            "source_text": "Prepare reports.",
                            "normalized_statement": "Prepare financial reports.",
                            "statement_type": "RESPONSIBILITY",
                            "capability_relevance": "CAPABILITY_BEARING",
                        }
                    ]
                },
                strict=True,
            ),
            blocks,
        )
