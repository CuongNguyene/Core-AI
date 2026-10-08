from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.job_semantics_eval.provider import provider_input
from app.job_semantics_eval.source_adapter import JobSourceBlock, build_source_blocks


def test_source_blocks_follow_frozen_html_text_view_and_deterministic_local_order() -> None:
    source = {
        "source_application_ref": "must-not-be-forwarded",
        "job_posting_url": "https://example.invalid/job/1",
        "job_description_html": (
            "<h2>Trách nhiệm</h2><ul><li>Phát triển <strong>REST API</strong> &amp;"
            " kiểm thử.</li><li>Phối hợp nhóm</li></ul>"
        ),
        "job_requirements_html": "<p>English&nbsp;business communication.</p>",
    }

    blocks = build_source_blocks(source)

    assert blocks == (
        JobSourceBlock(
            block_id="jdblock:JOB_DESCRIPTION:0001",
            source_field="JOB_DESCRIPTION",
            source_order=1,
            text="Trách nhiệm",
        ),
        JobSourceBlock(
            block_id="jdblock:JOB_DESCRIPTION:0002",
            source_field="JOB_DESCRIPTION",
            source_order=2,
            text="Phát triển REST API & kiểm thử.",
        ),
        JobSourceBlock(
            block_id="jdblock:JOB_DESCRIPTION:0003",
            source_field="JOB_DESCRIPTION",
            source_order=3,
            text="Phối hợp nhóm",
        ),
        JobSourceBlock(
            block_id="jdblock:JOB_REQUIREMENTS:0001",
            source_field="JOB_REQUIREMENTS",
            source_order=1,
            text="English business communication.",
        ),
    )


@pytest.mark.parametrize("source", [None, {}, {"job_description_html": None}])
def test_null_or_omitted_source_produces_no_blocks(source: object) -> None:
    assert build_source_blocks(source) == ()


@pytest.mark.parametrize("value", [None, "", " \t\n  ", "<p> &nbsp; </p>"])
def test_null_empty_or_whitespace_html_produces_no_blocks(value: object) -> None:
    assert build_source_blocks({"job_description_html": value}) == ()


def test_source_adapter_rejects_unknown_source_fields() -> None:
    with pytest.raises(ValueError, match="unknown target_job_source field"):
        build_source_blocks({"job_description_html": "<p>Task</p>", "salary": "secret"})


def test_source_adapter_rejects_non_string_html() -> None:
    with pytest.raises(ValueError, match="must be a string or null"):
        build_source_blocks({"job_description_html": ["not", "html"]})


def test_adapter_matches_all_frozen_corpus_visible_text_and_provider_projection() -> None:
    backend = Path(__file__).parents[1]
    dataset = (
        backend / "evals/job_semantics/requirement_breakdown_eval_00/dataset.synthetic.v1.jsonl"
    )
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    assert len(cases) == 40
    for case in cases:
        source = case.get("target_job_source")
        blocks = build_source_blocks(source)
        expected_fields = {
            "JOB_DESCRIPTION": "job_description_html",
            "JOB_REQUIREMENTS": "job_requirements_html",
        }
        for field, html_key in expected_fields.items():
            html_value = (source or {}).get(html_key) if isinstance(source, dict) else None
            expected_view = "\n".join(block.text for block in blocks if block.source_field == field)
            if html_value is not None:
                from evals.job_semantics.requirement_breakdown_eval_00.validate_and_freeze import (
                    html_text_view,
                )

                assert expected_view == html_text_view(html_value)
        projected = provider_input(blocks).model_dump(mode="json")
        assert set(projected) == {"source_blocks"}
        assert all(
            set(row) == {"block_id", "source_field", "text"} for row in projected["source_blocks"]
        )
