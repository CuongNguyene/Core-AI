from __future__ import annotations

from app.job_semantics_eval.contracts import ValidatedRequirementStatement
from app.job_semantics_eval.metrics import evaluate_dataset


def _pred(
    *,
    field: str,
    text: str,
    order: int,
    start: int,
    kind: str = "RESPONSIBILITY",
    relevance: str = "CAPABILITY_BEARING",
) -> ValidatedRequirementStatement:
    block_id = f"jdblock:{field}:{order:04d}"
    return ValidatedRequirementStatement(
        source_block_ids=(block_id,),
        source_field=field,
        block_order=order,
        start_offset=start,
        end_offset=start + len(text),
        source_text=text,
        normalized_statement=text,
        statement_type=kind,
        capability_relevance=relevance,
        output_index=start,
    )


def test_matcher_uses_source_field_and_occurrence_order_for_duplicate_spans() -> None:
    text = "Prepare monthly reports."
    cases = [
        {
            "case_id": "case-1",
            "domain": "FINANCE_ACCOUNTING",
            "language_profile": "VIETNAMESE",
            "difficulty": "EASY",
            "boundary_tags": ["html_list_boundary"],
            "target_job_source": {
                "job_description_html": f"<p>{text}</p>",
                "job_requirements_html": f"<p>{text}</p>",
            },
            "expected_statements": [
                {
                    "source_field": "JOB_DESCRIPTION",
                    "source_text": text,
                    "source_order": 1,
                    "statement_type": "RESPONSIBILITY",
                    "capability_relevance": "CAPABILITY_BEARING",
                },
                {
                    "source_field": "JOB_REQUIREMENTS",
                    "source_text": text,
                    "source_order": 1,
                    "statement_type": "EXPERIENCE_REQUIREMENT",
                    "capability_relevance": "CAPABILITY_BEARING",
                },
            ],
        }
    ]

    metrics = evaluate_dataset(
        cases,
        {
            "case-1": (
                _pred(
                    field="JOB_REQUIREMENTS",
                    text=text,
                    order=1,
                    start=0,
                    kind="EXPERIENCE_REQUIREMENT",
                ),
                _pred(field="JOB_DESCRIPTION", text=text, order=1, start=0),
            )
        },
    )

    assert metrics["decomposition"]["statement_precision"] == 1.0
    assert metrics["decomposition"]["statement_recall"] == 1.0
    assert metrics["decomposition"]["case_exact_decomposition_rate"] == 1.0
    assert metrics["statement_type"]["accuracy"] == 1.0
    assert metrics["source_fidelity"]["source_field_provenance_accuracy"] == 1.0
    assert metrics["slices"]["boundary_tag"]["html_list_boundary"]["case_count"] == 1


def test_metrics_separate_over_split_under_split_and_provider_errors() -> None:
    cases = [
        {
            "case_id": "over",
            "domain": "SOFTWARE_ENGINEERING",
            "language_profile": "ENGLISH",
            "difficulty": "HARD",
            "boundary_tags": ["coordinated_clause_split"],
            "target_job_source": {"job_description_html": "<p>Design and implement APIs.</p>"},
            "expected_statements": [
                {
                    "source_field": "JOB_DESCRIPTION",
                    "source_text": "Design and implement APIs.",
                    "source_order": 1,
                    "statement_type": "RESPONSIBILITY",
                    "capability_relevance": "CAPABILITY_BEARING",
                }
            ],
        },
        {
            "case_id": "under",
            "domain": "PROJECT_MANAGEMENT",
            "language_profile": "MIXED",
            "difficulty": "MEDIUM",
            "boundary_tags": ["mixed_requirement_clause"],
            "target_job_source": {
                "job_description_html": "<p>Plan project milestones. Track dependencies.</p>"
            },
            "expected_statements": [
                {
                    "source_field": "JOB_DESCRIPTION",
                    "source_text": "Plan project milestones.",
                    "source_order": 1,
                    "statement_type": "RESPONSIBILITY",
                    "capability_relevance": "CAPABILITY_BEARING",
                },
                {
                    "source_field": "JOB_DESCRIPTION",
                    "source_text": "Track dependencies.",
                    "source_order": 2,
                    "statement_type": "RESPONSIBILITY",
                    "capability_relevance": "CAPABILITY_BEARING",
                },
            ],
        },
        {
            "case_id": "error",
            "domain": "DATA_ANALYTICS",
            "language_profile": "VIETNAMESE",
            "difficulty": "EASY",
            "boundary_tags": ["generic_keyword_overlap"],
            "expected_statements": [],
        },
    ]

    metrics = evaluate_dataset(
        cases,
        {
            "over": (
                _pred(field="JOB_DESCRIPTION", text="Design", order=1, start=0),
                _pred(field="JOB_DESCRIPTION", text="implement APIs", order=1, start=11),
            ),
            "under": (
                _pred(
                    field="JOB_DESCRIPTION",
                    text="Plan project milestones. Track dependencies.",
                    order=1,
                    start=0,
                ),
            ),
        },
        execution_errors={"error": "provider_timeout"},
    )

    assert metrics["execution"]["attempted_cases"] == 3
    assert metrics["execution"]["completed_cases"] == 2
    assert metrics["execution"]["provider_errors"] == 1
    assert metrics["decomposition"]["over_split_statement_count"] == 2
    assert metrics["decomposition"]["under_split_gold_statement_count"] == 2
    assert metrics["slices"]["domain"]["DATA_ANALYTICS"]["case_count"] == 1
    assert metrics["slices"]["domain"]["DATA_ANALYTICS"]["evaluated_case_count"] == 0


def test_evaluation_rejects_predictions_for_unattempted_case_ids() -> None:
    try:
        evaluate_dataset([{"case_id": "only", "expected_statements": []}], {"other": ()})
    except ValueError as error:
        assert "unknown prediction case" in str(error)
    else:
        raise AssertionError("unknown prediction case ID must fail closed")


def test_source_order_comparison_is_scoped_to_each_case() -> None:
    cases = []
    predictions = {}
    for case_id, first, second in (("a", "Alpha.", "Beta."), ("b", "Gamma.", "Delta.")):
        cases.append(
            {
                "case_id": case_id,
                "target_job_source": {"job_description_html": f"<p>{first}</p><p>{second}</p>"},
                "expected_statements": [
                    {
                        "source_field": "JOB_DESCRIPTION",
                        "source_text": first,
                        "source_order": 1,
                        "statement_type": "RESPONSIBILITY",
                        "capability_relevance": "CAPABILITY_BEARING",
                    },
                    {
                        "source_field": "JOB_DESCRIPTION",
                        "source_text": second,
                        "source_order": 2,
                        "statement_type": "RESPONSIBILITY",
                        "capability_relevance": "CAPABILITY_BEARING",
                    },
                ],
            }
        )
        predictions[case_id] = (
            _pred(field="JOB_DESCRIPTION", text=first, order=1, start=0),
            _pred(field="JOB_DESCRIPTION", text=second, order=2, start=len(first) + 1),
        )

    metrics = evaluate_dataset(cases, predictions)
    assert metrics["source_order_accuracy"] == 1.0
    assert metrics["source_order_comparison_count"] == 2
