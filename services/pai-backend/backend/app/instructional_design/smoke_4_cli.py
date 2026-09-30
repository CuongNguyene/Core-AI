"""Controlled real-model ID-02D Smoke-4 contract validation."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
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
from app.instructional_design.experiment_runners import execute_structured_run
from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.model_gateway_designers import ModelGatewayStructuredDesigners
from app.main import create_app
from app.model_gateway.contracts import ModelGateway
from app.shared.config import Settings

SMOKE_4_FIXTURE_IDS = (
    "model_monitoring",
    "python_data_processing",
    "technical_communication",
)
SMOKE_4_EXPERIMENT_ID = "instructional-design-id-02d-smoke-4"
SMOKE_4_EXPERIMENT_VERSION = "0.1"
SMOKE_4_OUTPUT_TOKENS = 8192
SMOKE_4_TEMPERATURE = 0.0


class Smoke4Execution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    manifest: ExperimentManifest
    results: list[ExperimentRunResult]
    comparisons: list[ExperimentComparison]
    aggregation: ExperimentAggregation


class Smoke4Check(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(min_length=1)
    result: Literal["PASS", "FAIL", "NOT_OBSERVED"]
    details: list[str] = Field(default_factory=list)


class Smoke4RuntimeFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: str
    fixture_id: str
    stage: str
    failure_class: str
    category: Literal[
        "PROMPT_SEMANTICS",
        "SCHEMA_SEMANTICS",
        "ORCHESTRATION",
        "VALIDATOR_BUG",
        "MODEL_RELIABILITY",
    ]
    details: str | None = None


class Smoke4ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: str
    condition: str
    expected_runs: int
    completed_runs: int
    failed_runs: int
    checks: list[Smoke4Check]
    runtime_failures: list[Smoke4RuntimeFailure]
    quality_gate_pass: bool
    quality_gate_findings_by_code: dict[str, int]
    quality_gate_findings_by_severity: dict[str, int]
    decision: Literal["ID-02D VALIDATED", "ID-02D NEEDS ITERATION", "ID-02D BLOCKED"]


def _prompt_schema_versions() -> list[PromptSchemaVersion]:
    return [
        PromptSchemaVersion(
            prompt_id=contract_id,
            prompt_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
            schema_id=contract_id,
            schema_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
        )
        for contract_id in (
            OBJECTIVE_DESIGN_SCHEMA_ID,
            ASSESSMENT_DESIGN_SCHEMA_ID,
            PREREQUISITE_PROPOSAL_SCHEMA_ID,
            COURSE_PLANNING_SCHEMA_ID,
            LESSON_PLANNING_SCHEMA_ID,
        )
    ]


def build_smoke_4_config(
    *,
    model_provider: str,
    model_name: str,
    model_revision: str | None,
    policy_id: str,
    policy_version: str,
) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id=SMOKE_4_EXPERIMENT_ID,
        experiment_version=SMOKE_4_EXPERIMENT_VERSION,
        fixture_ids=list(SMOKE_4_FIXTURE_IDS),
        runs_per_fixture_per_condition=1,
        conditions=(ExperimentCondition.STRUCTURED_V031,),
        model_provider=model_provider,
        model_name=model_name,
        model_revision=model_revision,
        generation_config=GenerationConfig(
            temperature=SMOKE_4_TEMPERATURE,
            top_p=None,
            max_output_tokens=SMOKE_4_OUTPUT_TOKENS,
            seed=None,
            unsupported_fields=["top_p", "seed"],
        ),
        policy_id=policy_id,
        policy_version=policy_version,
        dependency_normalizer_version=DEPENDENCY_NORMALIZER_VERSION,
        prompt_schema_versions=_prompt_schema_versions(),
    )


async def run_smoke_4(
    *,
    gateway: ModelGateway,
    model_provider: str,
    model_name: str,
    model_revision: str | None,
    policy_id: str,
    policy_version: str,
    generation_started_at: datetime | None = None,
) -> Smoke4Execution:
    config = build_smoke_4_config(
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
    for fixture_id in SMOKE_4_FIXTURE_IDS:
        bundle = fixtures[fixture_id]
        condition = ExperimentCondition.STRUCTURED_V031
        run = ExperimentRun.from_config(
            run_id=f"{config.experiment_id}:{fixture_id}:{condition.value}:1",
            config=config,
            fixture_id=fixture_id,
            condition=condition,
            run_number=1,
            started_at=started_at,
        )
        results.append(
            await execute_structured_run(
                run=run,
                brief=bundle.brief,
                designers=ModelGatewayStructuredDesigners(
                    gateway=gateway,
                    requested_provider=model_provider,
                    correlation_id=f"{run.run_id}:model",
                    output_token_budget=config.generation_config.max_output_tokens,
                    temperature=config.generation_config.temperature,
                    stage_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
                ),
            )
        )
    return Smoke4Execution(
        manifest=manifest,
        results=results,
        comparisons=build_experiment_comparisons(results),
        aggregation=aggregate_experiment_results(results),
    )


def _check(name: str, failures: list[str], *, observed_runs: int) -> Smoke4Check:
    if not observed_runs:
        return Smoke4Check(name=name, result="NOT_OBSERVED", details=failures)
    return Smoke4Check(name=name, result="FAIL" if failures else "PASS", details=failures)


def validate_smoke_4(execution: Smoke4Execution) -> Smoke4ValidationReport:
    """Replay contract checks over immutable results; never repair an artifact."""

    completed = [item for item in execution.results if item.snapshot is not None]
    failed = [item for item in execution.results if item.snapshot is None]
    artifact_id_failures: list[str] = []
    formative_failures: list[str] = []
    graph_failures: list[str] = []
    prerequisite_failures: list[str] = []
    scope_failures: list[str] = []
    runtime_failures: list[Smoke4RuntimeFailure] = []
    finding_by_code: dict[str, int] = {}
    finding_by_severity: dict[str, int] = {}
    for result in execution.results:
        if result.snapshot is None:
            reason = result.stage_failure.validation_error if result.stage_failure else "run failed"
            stage_failure = result.stage_failure
            runtime_failures.append(
                Smoke4RuntimeFailure(
                    run_id=result.run.run_id,
                    fixture_id=result.run.fixture_id,
                    stage=stage_failure.stage if stage_failure else "unknown",
                    failure_class=stage_failure.failure_class if stage_failure else "unknown",
                    category="MODEL_RELIABILITY",
                    details=reason,
                )
            )
            continue
        snapshot = result.snapshot
        if snapshot.course_outline is None:
            graph_failures.append(f"{result.run.fixture_id}: missing course outline")
            continue
        artifact_ids = (
            {item.id for item in snapshot.objectives}
            | {item.id for item in snapshot.assessments}
            | {item.id for item in snapshot.prerequisites}
            | {item.id for item in snapshot.course_outline.modules}
            | {item.id for item in snapshot.lessons}
        )
        for assessment in snapshot.assessments:
            values = [item.capability for item in assessment.required_capabilities]
            values.extend(assessment.required_capability_refs)
            if set(values) & artifact_ids:
                artifact_id_failures.append(assessment.id)
        assessment_by_id = {item.id: item for item in snapshot.assessments}
        module_by_id = {item.id: item for item in snapshot.course_outline.modules}
        objective_ids = set(snapshot.course_outline.objective_ids)
        for lesson in snapshot.lessons:
            module = module_by_id.get(lesson.module_id)
            if module is None:
                graph_failures.append(f"{lesson.id}: missing module")
            if not set(lesson.objective_ids).issubset(objective_ids):
                graph_failures.append(f"{lesson.id}: objective outside course")
            if module is not None and not set(lesson.objective_ids).issubset(module.objective_ids):
                graph_failures.append(f"{lesson.id}: objective outside module")
            for assessment_id in lesson.formative_assessment_ids:
                referenced_assessment = assessment_by_id.get(assessment_id)
                if (
                    referenced_assessment is None
                    or referenced_assessment.effective_role.value != "formative"
                ):
                    formative_failures.append(f"{lesson.id}: {assessment_id}")
        for prerequisite in snapshot.prerequisites:
            if prerequisite.basis.value == "model_proposed" and prerequisite.status.value != "candidate":
                prerequisite_failures.append(prerequisite.id)
        module_minutes = sum(item.estimated_minutes or 0 for item in snapshot.course_outline.modules)
        course_minutes = snapshot.course_outline.estimated_minutes
        if course_minutes is not None and module_minutes > course_minutes:
            warnings = snapshot.course_outline.planning_warnings
            if not any(item.type.value == "scope_time_conflict" for item in warnings):
                scope_failures.append(snapshot.course_outline.id)
        for finding in snapshot.quality_report.findings:
            finding_by_code[finding.code] = finding_by_code.get(finding.code, 0) + 1
            severity = finding.severity.value
            finding_by_severity[severity] = finding_by_severity.get(severity, 0) + 1
    quality_gate_pass = all(
        result.snapshot is not None and result.snapshot.quality_report.passed
        for result in execution.results
    )
    checks = [
        _check(
            "model_execution",
            [item.details or item.failure_class for item in runtime_failures],
            observed_runs=1,
        ),
        _check("capability_refs", artifact_id_failures, observed_runs=len(completed)),
        _check(
            "formative_summative_separation",
            formative_failures,
            observed_runs=len(completed),
        ),
        _check("lesson_objective_graph", graph_failures, observed_runs=len(completed)),
        _check("prerequisite_governance", prerequisite_failures, observed_runs=len(completed)),
        _check("scope_time_warning", scope_failures, observed_runs=len(completed)),
    ]
    decision: Literal["ID-02D VALIDATED", "ID-02D NEEDS ITERATION", "ID-02D BLOCKED"]
    if runtime_failures:
        decision = "ID-02D BLOCKED"
    elif any(item.result == "FAIL" for item in checks) or any(
        severity in {"error", "blocking"} for severity in finding_by_severity
    ):
        decision = "ID-02D NEEDS ITERATION"
    else:
        decision = "ID-02D VALIDATED"
    return Smoke4ValidationReport(
        experiment_id=execution.manifest.experiment_id,
        condition=ExperimentCondition.STRUCTURED_V031.value,
        expected_runs=len(SMOKE_4_FIXTURE_IDS),
        completed_runs=len(completed),
        failed_runs=len(failed),
        checks=checks,
        runtime_failures=runtime_failures,
        quality_gate_pass=quality_gate_pass,
        quality_gate_findings_by_code=finding_by_code,
        quality_gate_findings_by_severity=finding_by_severity,
        decision=decision,
    )


def _write_json(path: Path, value: BaseModel) -> None:
    path.write_text(
        json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ID-02D Smoke-4 contract validation.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("test/results/instructional-design-smoke-4"),
    )
    args = parser.parse_args()
    settings = Settings(_env_file=args.env_file) if args.env_file else Settings()
    app = create_app(settings)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    provider_id = app.state.model_provider_id
    config = build_smoke_4_config(
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
        run_smoke_4(
            gateway=cast(ModelGateway, app.state.model_gateway),
            model_provider=provider_id,
            model_name=settings.vllm_model,
            model_revision=None,
            policy_id="pai_instructional_design",
            policy_version="0.1",
        )
    )
    _write_json(output_dir / "results.json", execution)
    validation = validate_smoke_4(execution)
    _write_json(output_dir / "validation-report.json", validation)
    print(json.dumps(validation.model_dump(mode="json"), ensure_ascii=False))


if __name__ == "__main__":
    main()
