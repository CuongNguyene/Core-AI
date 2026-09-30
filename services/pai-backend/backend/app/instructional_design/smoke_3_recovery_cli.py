"""Recover one missing ID-02C Smoke-3 structured artifact without rerunning the experiment."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from app.instructional_design.experiment import ExperimentConfig, ExperimentRun, ExperimentRunResult
from app.instructional_design.experiment_runners import execute_structured_run
from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.model_gateway_designers import ModelGatewayStructuredDesigners
from app.instructional_design.smoke_3_cli import build_smoke_3_config
from app.main import create_app
from app.model_gateway.contracts import ModelGateway
from app.shared.config import Settings


class RecoveryExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: dict[str, object]
    result: ExperimentRunResult


def build_recovery_run(
    config: ExperimentConfig, *, started_at: datetime | None = None
) -> ExperimentRun:
    """Build exactly the missing technical-communication structured run."""

    return ExperimentRun.from_config(
        run_id="instructional-design-id-02-smoke-3:technical_communication:structured_v0.3:recovery-1",
        config=config,
        fixture_id="technical_communication",
        condition=config.conditions[1],
        run_number=2,
        started_at=started_at or datetime.now(UTC),
    )


def _write_json(path: Path, value: BaseModel | dict[str, object]) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def recover(
    *,
    gateway: ModelGateway,
    model_provider: str,
    model_name: str,
    started_at: datetime | None = None,
) -> RecoveryExecution:
    config = build_smoke_3_config(
        model_provider=model_provider,
        model_name=model_name,
        model_revision=None,
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )
    run = build_recovery_run(config, started_at=started_at)
    bundle = research_fixture_bundles()["technical_communication"]
    result = await execute_structured_run(
        run=run,
        brief=bundle.brief,
        designers=ModelGatewayStructuredDesigners(
            gateway=gateway,
            requested_provider=model_provider,
            correlation_id=f"{run.run_id}:model",
            output_token_budget=config.generation_config.max_output_tokens,
            temperature=config.generation_config.temperature,
            stage_version="0.3",
        ),
    )
    return RecoveryExecution(
        manifest={
            **config.model_dump(mode="json"),
            "target_fixture_id": "technical_communication",
            "target_condition": "structured_v0.3",
            "planned_model_call_count": 5,
            "parent_experiment_id": "instructional-design-id-02-smoke-3",
            "written_before_model_calls": True,
        },
        result=result,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover the missing Smoke-3 structured artifact.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings(_env_file=args.env_file) if args.env_file else Settings()
    app = create_app(settings)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    provider_id = app.state.model_provider_id
    execution = asyncio.run(
        recover(
            gateway=cast(ModelGateway, app.state.model_gateway),
            model_provider=provider_id,
            model_name=settings.vllm_model,
        )
    )
    _write_json(output_dir / "recovery-results.json", execution)
    print(json.dumps(execution.model_dump(mode="json"), ensure_ascii=False))


if __name__ == "__main__":
    main()
