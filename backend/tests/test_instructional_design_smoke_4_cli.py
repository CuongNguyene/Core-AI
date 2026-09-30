from datetime import UTC, datetime

from app.instructional_design.experiment import (
    ExperimentCondition,
    ExperimentRun,
    ExperimentRunResult,
    ExperimentRunStatus,
    StageFailure,
    aggregate_experiment_results,
    build_experiment_manifest,
)
from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.schemas import (
    DesignFinding,
    DesignFindingSeverity,
)
from app.instructional_design.smoke_4_cli import (
    SMOKE_4_FIXTURE_IDS,
    Smoke4Execution,
    build_smoke_4_config,
    validate_smoke_4,
)


def test_smoke_4_is_three_structured_v031_runs_and_fifteen_calls() -> None:
    config = build_smoke_4_config(
        model_provider="vilao",
        model_name="claude-sonnet-5",
        model_revision=None,
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )

    assert config.fixture_ids == list(SMOKE_4_FIXTURE_IDS)
    assert config.conditions == (ExperimentCondition.STRUCTURED_V031,)
    assert config.runs_per_fixture_per_condition == 1
    assert config.prompt_schema_versions
    assert {item.prompt_version for item in config.prompt_schema_versions} == {"0.3.1"}

    assert build_experiment_manifest(config).estimated_model_call_count == 15


def test_smoke_4_validation_passes_for_fixture_snapshots() -> None:
    config = build_smoke_4_config(
        model_provider="fixture",
        model_name="fixture-model",
        model_revision="fixture",
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )
    fixtures = research_fixture_bundles()
    manifest = build_experiment_manifest(config)
    results = [
        ExperimentRunResult(
            run=ExperimentRun.from_config(
                run_id=f"smoke4:{fixture_id}",
                config=config,
                fixture_id=fixture_id,
                condition=config.conditions[0],
                run_number=1,
                started_at=datetime(2026, 8, 13, tzinfo=UTC),
            ),
            status=ExperimentRunStatus.COMPLETED,
            snapshot=fixtures[fixture_id].snapshot,
            completed_at=datetime(2026, 8, 13, tzinfo=UTC),
        )
        for fixture_id in SMOKE_4_FIXTURE_IDS
    ]
    execution = Smoke4Execution(
        manifest=manifest,
        results=results,
        comparisons=[],
        aggregation=aggregate_experiment_results(results),
    )

    report = validate_smoke_4(execution)

    assert report.decision == "ID-02D VALIDATED"
    assert report.completed_runs == 3
    assert all(item.result == "PASS" for item in report.checks)


def test_smoke_4_runtime_failure_is_blocked_and_not_misreported_as_contract_failure() -> None:
    config = build_smoke_4_config(
        model_provider="fixture",
        model_name="fixture-model",
        model_revision="fixture",
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )
    manifest = build_experiment_manifest(config)
    failed_run = ExperimentRun.from_config(
        run_id="smoke4:technical_communication",
        config=config,
        fixture_id="technical_communication",
        condition=config.conditions[0],
        run_number=1,
        started_at=datetime(2026, 8, 13, tzinfo=UTC),
    )
    result = ExperimentRunResult(
        run=failed_run,
        status=ExperimentRunStatus.FAILED,
        partial_artifacts=None,
        stage_failure=StageFailure(
            stage="AssessmentDesigner",
            failure_class="StructuredOutputFailedError",
            validation_error="Structured output failed: invalid_model_json",
            retry_count=0,
        ),
    )
    execution = Smoke4Execution(
        manifest=manifest,
        results=[result],
        comparisons=[],
        aggregation=aggregate_experiment_results([result]),
    )

    report = validate_smoke_4(execution)

    assert report.decision == "ID-02D BLOCKED"
    assert report.runtime_failures[0].category == "MODEL_RELIABILITY"
    assert report.checks[1].result == "NOT_OBSERVED"


def test_smoke_4_quality_gate_error_requires_needs_iteration() -> None:
    config = build_smoke_4_config(
        model_provider="fixture",
        model_name="fixture-model",
        model_revision="fixture",
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )
    fixture = research_fixture_bundles()[SMOKE_4_FIXTURE_IDS[0]]
    quality_report = fixture.snapshot.quality_report.model_copy(
        update={
            "passed": False,
            "findings": [
                DesignFinding(
                    code="assessment_dependency_not_covered",
                    severity=DesignFindingSeverity.ERROR,
                    entity_type="assessment",
                    entity_id="assessment-1",
                    message="Dependency is not covered.",
                )
            ],
        }
    )
    snapshot = fixture.snapshot.model_copy(update={"quality_report": quality_report})
    result = ExperimentRunResult(
        run=ExperimentRun.from_config(
            run_id="smoke4:model_monitoring",
            config=config,
            fixture_id=SMOKE_4_FIXTURE_IDS[0],
            condition=config.conditions[0],
            run_number=1,
            started_at=datetime(2026, 8, 13, tzinfo=UTC),
        ),
        status=ExperimentRunStatus.COMPLETED,
        snapshot=snapshot,
        completed_at=datetime(2026, 8, 13, tzinfo=UTC),
    )
    execution = Smoke4Execution(
        manifest=build_experiment_manifest(config),
        results=[result],
        comparisons=[],
        aggregation=aggregate_experiment_results([result]),
    )

    assert validate_smoke_4(execution).decision == "ID-02D NEEDS ITERATION"
