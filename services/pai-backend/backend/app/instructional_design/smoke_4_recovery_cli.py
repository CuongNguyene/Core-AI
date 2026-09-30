"""Recover only the failed ID-02D Smoke-4 structured artifact."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from app.instructional_design.contracts import INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031
from app.instructional_design.experiment import (
    ExperimentConfig,
    ExperimentManifest,
    ExperimentRun,
    ExperimentRunResult,
    GenerationConfig,
    aggregate_experiment_results,
    build_experiment_comparisons,
    validate_manifest_for_execution,
)
from app.instructional_design.experiment_runners import execute_structured_run
from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.model_gateway_designers import ModelGatewayStructuredDesigners
from app.instructional_design.smoke_4_cli import (
    Smoke4Execution,
    Smoke4ValidationReport,
    validate_smoke_4,
)
from app.main import create_app
from app.model_gateway.contracts import ModelGateway
from app.shared.config import Settings

TARGET_FIXTURE_ID = "technical_communication"
TARGET_CONDITION = "structured_v0.3.1"


class Smoke4RecoveryExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    parent_manifest: ExperimentManifest
    result: ExperimentRunResult


def _config_from_manifest(manifest: ExperimentManifest) -> ExperimentConfig:
    dependency_normalizer_version = validate_manifest_for_execution(manifest)
    return ExperimentConfig(
        experiment_id=manifest.experiment_id,
        experiment_version=manifest.experiment_version,
        fixture_ids=list(manifest.fixture_ids),
        runs_per_fixture_per_condition=manifest.runs_per_fixture_per_condition,
        conditions=(manifest.conditions[0],),
        model_provider=manifest.model_provider,
        model_name=manifest.model_name,
        model_revision=manifest.model_revision,
        generation_config=GenerationConfig.model_validate(
            manifest.generation_config.model_dump(mode="json")
        ),
        policy_id=manifest.policy_id,
        policy_version=manifest.policy_version,
        dependency_normalizer_version=dependency_normalizer_version,
        prompt_schema_versions=list(manifest.prompt_schema_versions),
    )


async def recover_smoke_4(
    *,
    gateway: ModelGateway,
    parent_manifest: ExperimentManifest,
    started_at: datetime | None = None,
) -> Smoke4RecoveryExecution:
    config = _config_from_manifest(parent_manifest)
    if TARGET_FIXTURE_ID not in config.fixture_ids:
        raise ValueError("recovery target is not in the parent manifest")
    if config.conditions[0].value != TARGET_CONDITION:
        raise ValueError("recovery target condition does not match the parent manifest")
    run = ExperimentRun.from_config(
        run_id=f"{config.experiment_id}:{TARGET_FIXTURE_ID}:{TARGET_CONDITION}:1",
        config=config,
        fixture_id=TARGET_FIXTURE_ID,
        condition=config.conditions[0],
        run_number=1,
        started_at=started_at or datetime.now(UTC),
    )
    result = await execute_structured_run(
        run=run,
        brief=research_fixture_bundles()[TARGET_FIXTURE_ID].brief,
        designers=ModelGatewayStructuredDesigners(
            gateway=gateway,
            requested_provider=config.model_provider,
            correlation_id=f"{run.run_id}:recovery-1:model",
            output_token_budget=config.generation_config.max_output_tokens,
            temperature=config.generation_config.temperature,
            stage_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
        ),
    )
    return Smoke4RecoveryExecution(parent_manifest=parent_manifest, result=result)


def merge_recovery(
    *, parent_results: Path, recovery_results: Path, output: Path
) -> tuple[Smoke4Execution, Smoke4ValidationReport]:
    parent = Smoke4Execution.model_validate_json(parent_results.read_text(encoding="utf-8"))
    recovery = Smoke4RecoveryExecution.model_validate_json(
        recovery_results.read_text(encoding="utf-8")
    )
    replaced = [
        recovery.result
        if (item.run.fixture_id, item.run.condition.value)
        == (TARGET_FIXTURE_ID, TARGET_CONDITION)
        else item
        for item in parent.results
    ]
    if not any(
        (item.run.fixture_id, item.run.condition.value)
        == (TARGET_FIXTURE_ID, TARGET_CONDITION)
        for item in parent.results
    ):
        raise ValueError("recovery target does not match a parent result")
    execution = Smoke4Execution(
        manifest=parent.manifest,
        results=replaced,
        comparisons=build_experiment_comparisons(replaced),
        aggregation=aggregate_experiment_results(replaced),
    )
    validation = validate_smoke_4(execution)
    output.write_text(
        json.dumps(execution.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return execution, validation


def _write_json(path: Path, value: BaseModel | dict[str, object]) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover only the failed Smoke-4 artifact.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--parent-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    parent_dir: Path = args.parent_dir
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    parent_manifest = ExperimentManifest.model_validate_json(
        (parent_dir / "manifest.json").read_text(encoding="utf-8")
    )
    _write_json(
        output_dir / "recovery-manifest.json",
        {
            "parent_manifest": parent_manifest.model_dump(mode="json"),
            "target_fixture_id": TARGET_FIXTURE_ID,
            "target_condition": TARGET_CONDITION,
            "planned_model_call_count": 5,
            "recovery_attempt": 1,
            "written_before_model_calls": True,
        },
    )
    settings = Settings(_env_file=args.env_file) if args.env_file else Settings()
    app = create_app(settings)
    recovery = asyncio.run(
        recover_smoke_4(
            gateway=cast(ModelGateway, app.state.model_gateway),
            parent_manifest=parent_manifest,
        )
    )
    _write_json(output_dir / "recovery-results.json", recovery)
    execution, validation = merge_recovery(
        parent_results=parent_dir / "results.json",
        recovery_results=output_dir / "recovery-results.json",
        output=output_dir / "results-recovered.json",
    )
    _write_json(output_dir / "validation-report.json", validation)
    print(json.dumps({"validation": validation.model_dump(mode="json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
