"""Fixture-only CLI for ID-02 orchestration smoke checks; it never calls a provider."""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_VERSION,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
)
from app.instructional_design.experiment import (
    DEPENDENCY_NORMALIZER_VERSION,
    ExperimentAggregation,
    ExperimentComparison,
    ExperimentCondition,
    ExperimentConfig,
    ExperimentManifest,
    ExperimentRun,
    ExperimentRunResult,
    GenerationConfig,
    PromptSchemaVersion,
    aggregate_experiment_results,
    build_experiment_comparisons,
    build_experiment_manifest,
)
from app.instructional_design.experiment_runners import (
    FixtureOneShotInstructionalDesignGenerator,
    FixtureStructuredDesigners,
    execute_one_shot_run,
    execute_structured_run,
)
from app.instructional_design.fixtures import experiment_fixture_bundles


class FixtureExperimentExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    manifest: ExperimentManifest
    results: list[ExperimentRunResult]
    comparisons: list[ExperimentComparison]
    aggregation: ExperimentAggregation


def _prompt_schema_versions() -> list[PromptSchemaVersion]:
    structured_ids = (
        OBJECTIVE_DESIGN_SCHEMA_ID,
        ASSESSMENT_DESIGN_SCHEMA_ID,
        PREREQUISITE_PROPOSAL_SCHEMA_ID,
        COURSE_PLANNING_SCHEMA_ID,
        LESSON_PLANNING_SCHEMA_ID,
    )
    return [
        *[
            PromptSchemaVersion(
                prompt_id=contract_id,
                prompt_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION,
                schema_id=contract_id,
                schema_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION,
            )
            for contract_id in structured_ids
        ],
        PromptSchemaVersion(
            prompt_id=ONE_SHOT_BASELINE_SCHEMA_ID,
            prompt_version=ONE_SHOT_BASELINE_SCHEMA_VERSION,
            schema_id=ONE_SHOT_BASELINE_SCHEMA_ID,
            schema_version=ONE_SHOT_BASELINE_SCHEMA_VERSION,
        ),
    ]


async def run_fixture_experiment(
    *,
    mode: str,
    fixture_id: str | None,
    condition: ExperimentCondition | None,
    runs: int | None,
) -> FixtureExperimentExecution:
    """Execute fixture-only smoke/full mechanics, never an external model experiment."""

    if mode not in {"smoke", "full"}:
        raise ValueError("mode must be smoke or full")
    fixtures = experiment_fixture_bundles()
    if fixture_id is not None and fixture_id not in fixtures:
        raise ValueError("fixture_id is not registered")
    selected_fixture_ids = [fixture_id] if fixture_id else sorted(fixtures)
    selected_conditions = (
        (condition,)
        if condition
        else (ExperimentCondition.ONE_SHOT, ExperimentCondition.STRUCTURED)
    )
    selected_runs = runs if runs is not None else (1 if mode == "smoke" else 3)
    if selected_runs <= 0:
        raise ValueError("runs must be greater than zero")
    config = ExperimentConfig(
        experiment_id="instructional-design-id-02-fixture",
        experiment_version="0.1",
        fixture_ids=selected_fixture_ids,
        runs_per_fixture_per_condition=selected_runs,
        conditions=selected_conditions,
        model_provider="fixture-runner",
        model_name="fixture-design-artifacts",
        model_revision="none",
        generation_config=GenerationConfig(
            temperature=None,
            top_p=None,
            max_output_tokens=None,
            seed=None,
            unsupported_fields=["temperature", "top_p", "max_output_tokens", "seed"],
        ),
        policy_id="pai_instructional_design",
        policy_version="0.1",
        dependency_normalizer_version=DEPENDENCY_NORMALIZER_VERSION,
        prompt_schema_versions=_prompt_schema_versions(),
    )
    manifest = build_experiment_manifest(config)
    results: list[ExperimentRunResult] = []
    for selected_id in selected_fixture_ids:
        bundle = fixtures[selected_id]
        for selected_condition in selected_conditions:
            for run_number in range(1, selected_runs + 1):
                run = ExperimentRun.from_config(
                    run_id=f"{config.experiment_id}:{selected_id}:{selected_condition.value}:{run_number}",
                    config=config,
                    fixture_id=selected_id,
                    condition=selected_condition,
                    run_number=run_number,
                    started_at=datetime.now(UTC),
                )
                if selected_condition is ExperimentCondition.ONE_SHOT:
                    result = await execute_one_shot_run(
                        run=run,
                        brief=bundle.brief,
                        generator=FixtureOneShotInstructionalDesignGenerator(bundle),
                    )
                else:
                    result = await execute_structured_run(
                        run=run,
                        brief=bundle.brief,
                        designers=FixtureStructuredDesigners(bundle),
                    )
                results.append(result)
    return FixtureExperimentExecution(
        manifest=manifest,
        results=results,
        comparisons=build_experiment_comparisons(results),
        aggregation=aggregate_experiment_results(results),
    )


def _parse_condition(value: str | None) -> ExperimentCondition | None:
    return ExperimentCondition(value) if value is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an ID-02 fixture-only research experiment.")
    parser.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--fixture")
    parser.add_argument("--condition", choices=tuple(item.value for item in ExperimentCondition))
    parser.add_argument("--runs", type=int)
    args = parser.parse_args()
    execution = asyncio.run(
        run_fixture_experiment(
            mode=args.mode,
            fixture_id=args.fixture,
            condition=_parse_condition(args.condition),
            runs=args.runs,
        )
    )
    print(json.dumps({"manifest": execution.manifest.model_dump(mode="json")}, ensure_ascii=False))
    print(json.dumps(execution.model_dump(mode="json"), ensure_ascii=False))


if __name__ == "__main__":
    main()
