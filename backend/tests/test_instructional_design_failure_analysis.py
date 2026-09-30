import json

import pytest


def test_failure_analysis_requires_exact_source_finding_and_preserves_result_payload() -> None:
    from app.instructional_design.failure_analysis import (
        FailureAnalysisReport,
        FindingRootCause,
        RootCauseAnnotation,
        validate_annotations_against_results,
    )

    source_results = {
        "results": [
            {
                "run": {"run_id": "run-python-structured", "condition": "structured"},
                "snapshot": {
                    "quality_report": {
                        "findings": [
                            {
                                "code": "orphan_lesson",
                                "entity_type": "lesson",
                                "entity_id": "les-001-a",
                                "field": "objective_ids",
                            }
                        ]
                    }
                },
            }
        ]
    }
    report = FailureAnalysisReport(
        experiment_id="instructional-design-id-02-smoke-2",
        source_results_artifact="results.json",
        annotations=[
            RootCauseAnnotation(
                run_id="run-python-structured",
                finding_index=0,
                finding_code="orphan_lesson",
                entity_type="lesson",
                entity_id="les-001-a",
                field="objective_ids",
                root_cause=FindingRootCause.UNDER_GENERATION,
                producer_stage="LessonPlanner",
                validator_correct=True,
                rationale="The lesson omitted a required objective reference.",
            )
        ],
    )

    validate_annotations_against_results(report, source_results)

    assert "orphan_lesson" in json.dumps(source_results)


def test_failure_analysis_rejects_an_annotation_without_an_exact_source_finding() -> None:
    from app.instructional_design.failure_analysis import (
        FailureAnalysisReport,
        FindingRootCause,
        RootCauseAnnotation,
        validate_annotations_against_results,
    )

    report = FailureAnalysisReport(
        experiment_id="instructional-design-id-02-smoke-2",
        source_results_artifact="results.json",
        annotations=[
            RootCauseAnnotation(
                run_id="run-python-structured",
                finding_index=0,
                finding_code="orphan_lesson",
                entity_type="lesson",
                entity_id="not-a-real-lesson",
                field="objective_ids",
                root_cause=FindingRootCause.UNDER_GENERATION,
                producer_stage="LessonPlanner",
                validator_correct=True,
                rationale="Deliberately mismatched source reference.",
            )
        ],
    )

    with pytest.raises(ValueError, match="does not match a source finding"):
        validate_annotations_against_results(report, {"results": []})
