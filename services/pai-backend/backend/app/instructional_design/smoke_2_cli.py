"""Real-model, research-only ID-02 Smoke-2 entry point."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

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
    execute_one_shot_run,
    execute_structured_run,
)
from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.model_gateway_designers import (
    ModelGatewayOneShotInstructionalDesignGenerator,
    ModelGatewayStructuredDesigners,
)
from app.main import create_app
from app.model_gateway.contracts import ModelGateway
from app.shared.config import Settings

SMOKE_2_FIXTURE_IDS = (
    "model_monitoring",
    "python_data_processing",
    "technical_communication",
)
SMOKE_2_EXPERIMENT_ID = "instructional-design-id-02-smoke-2"
SMOKE_2_EXPERIMENT_VERSION = "0.1"
SMOKE_2_OUTPUT_TOKENS = 8192
SMOKE_2_TEMPERATURE = 0.0


class Smoke2Execution(BaseModel):
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
                prompt_id=prompt_id,
                prompt_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION,
                schema_id=prompt_id,
                schema_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION,
            )
            for prompt_id in structured_ids
        ],
        PromptSchemaVersion(
            prompt_id=ONE_SHOT_BASELINE_SCHEMA_ID,
            prompt_version=ONE_SHOT_BASELINE_SCHEMA_VERSION,
            schema_id=ONE_SHOT_BASELINE_SCHEMA_ID,
            schema_version=ONE_SHOT_BASELINE_SCHEMA_VERSION,
        ),
    ]


def build_smoke_2_config(
    *,
    model_provider: str,
    model_name: str,
    model_revision: str | None,
    policy_id: str,
    policy_version: str,
) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id=SMOKE_2_EXPERIMENT_ID,
        experiment_version=SMOKE_2_EXPERIMENT_VERSION,
        fixture_ids=list(SMOKE_2_FIXTURE_IDS),
        runs_per_fixture_per_condition=1,
        model_provider=model_provider,
        model_name=model_name,
        model_revision=model_revision,
        generation_config=GenerationConfig(
            temperature=SMOKE_2_TEMPERATURE,
            top_p=None,
            max_output_tokens=SMOKE_2_OUTPUT_TOKENS,
            seed=None,
            unsupported_fields=["top_p", "seed"],
        ),
        policy_id=policy_id,
        policy_version=policy_version,
        dependency_normalizer_version=DEPENDENCY_NORMALIZER_VERSION,
        prompt_schema_versions=_prompt_schema_versions(),
    )


async def run_smoke_2(
    *,
    gateway: ModelGateway,
    model_provider: str,
    model_name: str,
    model_revision: str | None,
    policy_id: str,
    policy_version: str,
    generation_started_at: datetime | None = None,
) -> Smoke2Execution:
    """Run exactly three public research briefs under both conditions once."""

    config = build_smoke_2_config(
        model_provider=model_provider,
        model_name=model_name,
        model_revision=model_revision,
        policy_id=policy_id,
        policy_version=policy_version,
    )
    manifest = build_experiment_manifest(config)
    fixtures = research_fixture_bundles()
    started_at = generation_started_at or datetime.now(UTC)
    results: list[ExperimentRunResult] = []
    for fixture_id in SMOKE_2_FIXTURE_IDS:
        bundle = fixtures[fixture_id]
        for condition in config.conditions:
            run = ExperimentRun.from_config(
                run_id=f"{config.experiment_id}:{fixture_id}:{condition.value}:1",
                config=config,
                fixture_id=fixture_id,
                condition=condition,
                run_number=1,
                started_at=started_at,
            )
            correlation_id = f"{run.run_id}:model"
            if condition is ExperimentCondition.ONE_SHOT:
                result = await execute_one_shot_run(
                    run=run,
                    brief=bundle.brief,
                    generator=ModelGatewayOneShotInstructionalDesignGenerator(
                        gateway=gateway,
                        requested_provider=model_provider,
                        correlation_id=correlation_id,
                        output_token_budget=config.generation_config.max_output_tokens,
                        temperature=config.generation_config.temperature,
                    ),
                )
            else:
                result = await execute_structured_run(
                    run=run,
                    brief=bundle.brief,
                    designers=ModelGatewayStructuredDesigners(
                        gateway=gateway,
                        requested_provider=model_provider,
                        correlation_id=correlation_id,
                        output_token_budget=config.generation_config.max_output_tokens,
                        temperature=config.generation_config.temperature,
                    ),
                )
            results.append(result)
    return Smoke2Execution(
        manifest=manifest,
        results=results,
        comparisons=build_experiment_comparisons(results),
        aggregation=aggregate_experiment_results(results),
    )


def _write_json(path: Path, value: BaseModel | dict[str, object]) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the real-model ID-02 Smoke-2 experiment.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("test/results/instructional-design-smoke-2"),
    )
    args = parser.parse_args()

    settings = Settings(_env_file=args.env_file) if args.env_file else Settings()
    app = create_app(settings)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    provider_id = app.state.model_provider_id
    config = build_smoke_2_config(
        model_provider=provider_id,
        model_name=settings.vllm_model,
        model_revision=None,
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )
    manifest = build_experiment_manifest(config)
    _write_json(output_dir / "manifest.json", manifest)
    print(json.dumps({"manifest": manifest.model_dump(mode="json")}, ensure_ascii=False))

    execution = asyncio.run(
        run_smoke_2(
            gateway=cast(ModelGateway, app.state.model_gateway),
            model_provider=provider_id,
            model_name=settings.vllm_model,
            model_revision=None,
            policy_id="pai_instructional_design",
            policy_version="0.1",
        )
    )
    _write_json(output_dir / "results.json", execution)
    print(json.dumps(execution.model_dump(mode="json"), ensure_ascii=False))


if __name__ == "__main__":
    main()
