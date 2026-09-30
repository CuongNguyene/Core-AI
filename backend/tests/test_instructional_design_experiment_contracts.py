import json
from datetime import UTC, datetime

import pytest

from app.instructional_design.experiment import (
    EditEffort,
    ExperimentCondition,
    ExperimentConfig,
    ExperimentRun,
    ExperimentRunResult,
    ExperimentRunStatus,
    GenerationConfig,
    HumanEvaluation,
    HumanEvaluationScores,
    PromptSchemaVersion,
    aggregate_experiment_results,
    build_blinded_review_payload,
    build_experiment_comparisons,
    build_experiment_manifest,
    validate_manifest_for_execution,
)
from app.instructional_design.fixtures import research_fixture_bundles


def config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="id-02",
        experiment_version="0.1",
        fixture_ids=["fixture-model-monitoring-limited-application"],
        runs_per_fixture_per_condition=3,
        model_provider="fixture-provider",
        model_name="fixture-model",
        model_revision="fixture-revision",
        generation_config=GenerationConfig(
            temperature=0.2,
            top_p=None,
            max_output_tokens=4096,
            seed=42,
            unsupported_fields=["top_p"],
        ),
        policy_id="pai_instructional_design",
        policy_version="0.1",
        dependency_normalizer_version="id02d.2@0.1",
        prompt_schema_versions=[
            PromptSchemaVersion(
                prompt_id="instructional_design_one_shot_baseline",
                prompt_version="0.1",
                schema_id="instructional_design_one_shot_baseline",
                schema_version="0.1",
            )
        ],
    )


def run(condition: ExperimentCondition, run_number: int) -> ExperimentRun:
    return ExperimentRun.from_config(
        run_id=f"run-{condition.value}-{run_number}",
        config=config(),
        fixture_id="fixture-model-monitoring-limited-application",
        condition=condition,
        run_number=run_number,
        started_at=datetime(2026, 8, 12, tzinfo=UTC),
    )


def test_conditions_preserve_the_same_controlled_fixture_model_config_and_policy() -> None:
    baseline = run(ExperimentCondition.ONE_SHOT, 1)
    structured = run(ExperimentCondition.STRUCTURED, 1)

    assert baseline.fixture_id == structured.fixture_id
    assert baseline.generation_config == structured.generation_config
    assert baseline.policy_id == structured.policy_id
    assert baseline.policy_version == structured.policy_version
    assert baseline.run_id != structured.run_id


def test_manifest_records_expected_model_call_count_and_provenance() -> None:
    manifest = build_experiment_manifest(config())

    assert manifest.fixture_count == 1
    assert manifest.estimated_model_call_count == 18
    assert manifest.runs_per_fixture_per_condition == 3
    assert manifest.policy_version == "0.1"
    assert manifest.dependency_normalizer_version == "id02d.2@0.1"
    assert manifest.prompt_schema_versions[0].prompt_version == "0.1"


def test_manifest_preflight_rejects_missing_dependency_normalizer_version_before_execution() -> None:
    invalid = config().model_copy(update={"dependency_normalizer_version": ""})

    with pytest.raises(ValueError, match="dependency_normalizer_version"):
        build_experiment_manifest(invalid)


def test_manifest_preflight_rejects_missing_prompt_schema_provenance() -> None:
    invalid = config().model_copy(update={"prompt_schema_versions": []})

    with pytest.raises(ValueError, match="prompt_schema_versions"):
        build_experiment_manifest(invalid)


def test_historical_manifest_is_readable_but_cannot_start_execution_without_version() -> None:
    historical = build_experiment_manifest(config()).model_copy(
        update={"dependency_normalizer_version": None}
    )

    with pytest.raises(ValueError, match="dependency_normalizer_version"):
        validate_manifest_for_execution(historical)


def test_manifest_counts_stage_calls_for_three_fixture_comparative_smoke() -> None:
    manifest = build_experiment_manifest(
        config().model_copy(
            update={
                "fixture_ids": ["model-monitoring", "python-data", "technical-communication"],
                "runs_per_fixture_per_condition": 1,
            }
        )
    )

    assert manifest.estimated_model_call_count == 18


def test_human_evaluation_is_condition_blind_and_records_edit_effort() -> None:
    bundle = next(iter(research_fixture_bundles().values()))
    completed = ExperimentRunResult(
        run=run(ExperimentCondition.ONE_SHOT, 1),
        status=ExperimentRunStatus.COMPLETED,
        snapshot=bundle.snapshot,
        completed_at=datetime(2026, 8, 12, tzinfo=UTC),
    )
    review = HumanEvaluation(
        run_id=completed.run.run_id,
        reviewer_id="reviewer-1",
        reviewed_at=datetime(2026, 8, 12, tzinfo=UTC),
        scores=HumanEvaluationScores(
            objective_measurability=4,
            objective_assessment_alignment=4,
            cognitive_alignment=4,
            evidence_validity=3,
            prerequisite_quality=3,
            sequence_coherence=4,
            instruction_assessment_alignment=4,
            under_teaching=2,
            over_teaching=1,
            overall_edit_effort=2,
        ),
        edit_effort=EditEffort.MINOR,
        objectives_changed=1,
        notes="Minor wording correction.",
    )

    blinded = build_blinded_review_payload(completed, review_id="review-001")

    blinded_data = blinded.model_dump(mode="json")
    assert blinded.review_id == "review-001"
    assert "condition" not in blinded_data
    assert "run_id" not in blinded_data
    assert "prompt_schema_versions" not in blinded_data
    assert "generation_provenance" not in json.dumps(blinded_data)
    assert "quality_report" not in json.dumps(blinded_data)
    assert review.run_id == completed.run.run_id
    assert review.edit_effort is EditEffort.MINOR
    assert review.source == "human"


def test_aggregation_exposes_descriptive_metrics_without_composite_or_winner() -> None:
    bundle = next(iter(research_fixture_bundles().values()))
    results = [
        ExperimentRunResult(
            run=run(ExperimentCondition.ONE_SHOT, 1),
            status=ExperimentRunStatus.COMPLETED,
            snapshot=bundle.snapshot,
            completed_at=datetime(2026, 8, 12, tzinfo=UTC),
        ),
        ExperimentRunResult(
            run=run(ExperimentCondition.STRUCTURED, 1),
            status=ExperimentRunStatus.COMPLETED,
            snapshot=bundle.snapshot,
            completed_at=datetime(2026, 8, 12, tzinfo=UTC),
        ),
    ]

    summary = aggregate_experiment_results(results)
    serialized = summary.model_dump(mode="json")

    assert summary.by_condition[ExperimentCondition.ONE_SHOT].run_count == 1
    assert summary.by_condition[ExperimentCondition.STRUCTURED].quality_gate_pass_rate == 1.0
    assert "composite_score" not in serialized
    assert "winner" not in serialized


def test_comparison_groups_only_equivalent_fixture_runs_without_a_verdict() -> None:
    bundle = next(iter(research_fixture_bundles().values()))
    results = [
        ExperimentRunResult(
            run=run(ExperimentCondition.ONE_SHOT, 1),
            status=ExperimentRunStatus.COMPLETED,
            snapshot=bundle.snapshot,
            completed_at=datetime(2026, 8, 12, tzinfo=UTC),
        ),
        ExperimentRunResult(
            run=run(ExperimentCondition.STRUCTURED, 1),
            status=ExperimentRunStatus.COMPLETED,
            snapshot=bundle.snapshot,
            completed_at=datetime(2026, 8, 12, tzinfo=UTC),
        ),
    ]

    comparison = build_experiment_comparisons(results)[0]

    assert comparison.fixture_id == "fixture-model-monitoring-limited-application"
    assert [item.run.condition for item in comparison.one_shot_runs] == [
        ExperimentCondition.ONE_SHOT
    ]
    assert [item.run.condition for item in comparison.structured_runs] == [
        ExperimentCondition.STRUCTURED
    ]
    assert "winner" not in comparison.model_dump(mode="json")
