import asyncio

from app.instructional_design.experiment import ExperimentCondition
from app.instructional_design.experiment_cli import run_fixture_experiment
from app.instructional_design.fixtures import experiment_fixture_bundles


def test_experiment_fixture_families_cover_three_domains_two_states_and_two_performances() -> None:
    fixtures = experiment_fixture_bundles()

    assert len(fixtures) == 12
    assert {bundle.brief.capability.name for bundle in fixtures.values()} == {
        "model monitoring response",
        "python data processing",
        "technical communication",
    }
    assert all(
        bundle.brief.provenance.type.value == "research_fixture" for bundle in fixtures.values()
    )
    assert "fixture-model-monitoring-limited-application" in fixtures
    assert "fixture-technical-communication-substantial-analysis" in fixtures


def test_fixture_smoke_runner_emits_manifest_before_single_filtered_run() -> None:
    execution = asyncio.run(
        run_fixture_experiment(
            mode="smoke",
            fixture_id="fixture-model-monitoring-limited-application",
            condition=ExperimentCondition.STRUCTURED,
            runs=None,
        )
    )

    assert execution.manifest.fixture_ids == ["fixture-model-monitoring-limited-application"]
    assert execution.manifest.conditions == (ExperimentCondition.STRUCTURED,)
    assert execution.manifest.runs_per_fixture_per_condition == 1
    assert execution.manifest.estimated_model_call_count == 5
    assert len(execution.results) == 1
    assert execution.results[0].run.model_provider == "fixture-runner"
    assert len(execution.comparisons) == 1
    assert execution.comparisons[0].fixture_id == "fixture-model-monitoring-limited-application"
    assert execution.comparisons[0].structured_runs == execution.results
    assert execution.comparisons[0].one_shot_runs == []
