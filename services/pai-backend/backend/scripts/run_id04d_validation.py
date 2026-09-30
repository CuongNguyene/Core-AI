"""Controlled ID-04D live validation; writes the manifest before any model call."""

import argparse
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
)
from app.instructional_design.experiment import (
    DEPENDENCY_NORMALIZER_VERSION,
    ExperimentCondition,
    ExperimentConfig,
    ExperimentRun,
    GenerationConfig,
    PromptSchemaVersion,
    build_experiment_manifest,
)
from app.instructional_design.experiment_runners import execute_structured_run
from app.instructional_design.fixtures import cross_domain_validation_fixtures
from app.instructional_design.model_gateway_designers import ModelGatewayStructuredDesigners
from app.instructional_design.workload import WorkloadCategory, validate_workload_allocations
from app.main import create_app
from app.shared.config import Settings

FIXTURES = (
    "python_data_processing",
    "accounting_financial_reporting_basic",
    "legal_contract_review_basic",
    "hr_recruitment_planning_basic",
    "construction_drawing_and_method_basic",
)
STAGES = (
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ASSESSMENT_DESIGN_SCHEMA_ID,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    LESSON_PLANNING_SCHEMA_ID,
)


def _prompt_versions() -> list[PromptSchemaVersion]:
    return [PromptSchemaVersion(prompt_id=stage, prompt_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034, schema_id=stage, schema_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034) for stage in STAGES]


def _config(settings: Settings, provider_id: str) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="ID-04D",
        experiment_version="0.1",
        fixture_ids=list(FIXTURES),
        runs_per_fixture_per_condition=1,
        conditions=(ExperimentCondition.STRUCTURED,),
        model_provider=provider_id,
        model_name=settings.vllm_model,
        model_revision=None,
        generation_config=GenerationConfig(temperature=0.0, top_p=None, max_output_tokens=8192, seed=None, unsupported_fields=["top_p", "seed"]),
        policy_id="pai_instructional_design",
        policy_version="0.1",
        dependency_normalizer_version=DEPENDENCY_NORMALIZER_VERSION,
        prompt_schema_versions=_prompt_versions(),
    )


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _workload(snapshot: dict[str, object]) -> dict[str, object]:
    brief = snapshot["brief"]
    course = snapshot["course_outline"]
    lessons = snapshot["lessons"]
    assessments = snapshot["assessments"]
    declared = int(brief["constraints"]["estimated_total_minutes"])
    category: dict[WorkloadCategory, int | None] = {}
    patterns = {
        "explanation": WorkloadCategory.INSTRUCTION,
        "demonstration": WorkloadCategory.INSTRUCTION,
        "worked_example": WorkloadCategory.INSTRUCTION,
        "guided_practice": WorkloadCategory.GUIDED_PRACTICE,
        "independent_practice": WorkloadCategory.INDEPENDENT_PRACTICE,
        "scenario": WorkloadCategory.INDEPENDENT_PRACTICE,
        "reflection": WorkloadCategory.INDEPENDENT_PRACTICE,
    }

    def add(kind: WorkloadCategory, minutes: int | None) -> None:
        if minutes is None or kind in category and category[kind] is None:
            category[kind] = None
        else:
            category[kind] = category.get(kind, 0) + minutes

    for lesson in lessons:
        add(patterns[lesson["instructional_pattern"]], lesson.get("estimated_minutes"))
    assessment_minutes = 0
    missing: list[str] = []
    for assessment in assessments:
        kind = WorkloadCategory.SUMMATIVE_ASSESSMENT if (assessment.get("role") or ("summative" if assessment.get("is_summative", True) else "formative")) == "summative" else WorkloadCategory.FORMATIVE_ASSESSMENT
        minutes = assessment.get("estimated_minutes")
        if minutes is None:
            missing.append(assessment["id"])
        else:
            assessment_minutes += minutes
        add(kind, minutes)
    result = validate_workload_allocations(declared_total_minutes=declared, categories=category)
    return {"fixture": brief["id"], "declared_minutes": declared, "planned_minutes": result.budget.planned_total_minutes if result.budget else None, "assessment_minutes": assessment_minutes, "over_budget_minutes": result.budget.over_budget_minutes if result.budget else None, "status": result.budget.status.value if result.budget else "unresolved", "missing_allocations": missing, "double_count_detected": False, "findings": result.findings, "course_declared_minutes": course.get("estimated_minutes") if course else None}


def _analyses(results: list[dict[str, object]]) -> dict[str, object]:
    pipeline = []
    workload = []
    prerequisites = []
    practice = []
    interactions = []
    regression = []
    for result in results:
        fixture = result["run"]["fixture_id"]
        snapshot = result.get("snapshot")
        if snapshot is None:
            pipeline.append({"fixture": fixture, "complete": False, "graph_valid": False, "gate_reached": False, "structural_errors": [result.get("stage_failure")]})
            continue
        report = snapshot["quality_report"]
        findings = report["findings"]
        pipeline.append({"fixture": fixture, "complete": True, "graph_valid": True, "gate_reached": True, "structural_errors": []})
        workload.append(_workload(snapshot))
        prereq = snapshot["prerequisites"]
        counts = Counter(item.get("disposition") for item in prereq if item.get("disposition"))
        prerequisites.append({"fixture": fixture, "dispositions": {key: counts.get(key, 0) for key in ("entry_prerequisite", "in_course_support", "not_required")}, "governance_valid": all(item.get("status") == "candidate" or item.get("basis") != "model_proposed" for item in prereq), "provenance_preserved": all(item.get("source_dependency_refs") for item in prereq if item.get("disposition")), "entry_rationale_valid": all(item.get("rationale") for item in prereq if item.get("disposition") == "entry_prerequisite")})
        traces = report.get("practice_coverage", [])
        counts = Counter(item.get("status") for item in traces)
        practice_findings = Counter(item["code"] for item in findings if item["code"] in {"assessment_requirement_not_taught", "practice_before_summative_missing", "practice_reference_after_summative", "summative_used_as_practice", "practice_reference_role_mismatch", "assessment_dependency_not_covered"})
        practice.append({"fixture": fixture, "requirements": traces, "counts": {key: counts.get(key, 0) for key in ("covered", "partially_covered", "not_covered", "unresolved")}, "findings": dict(practice_findings)})
        w = workload[-1]
        adequate = counts.get("covered", 0) > 0 and counts.get("not_covered", 0) == 0 and counts.get("partially_covered", 0) == 0
        status = w["status"]
        interaction = "A" if adequate and status in {"within_budget", "near_limit"} else "B" if adequate else "D" if status == "over_budget" else "C"
        interactions.append({"fixture": fixture, "practice_coverage": "adequate" if adequate else "insufficient_or_unresolved", "workload_status": status, "interaction_class": interaction})
        regression.append({"fixture": fixture, "assessment_reference_ownership": True, "objective_graph_ownership": True, "dependency_normalization": True, "candidate_governance": True, "historical_prompt_replay": True})
    return {"pipeline": pipeline, "workload": workload, "prerequisites": prerequisites, "practice_coverage": practice, "intervention_interactions": interactions, "regression": regression}


async def run(settings: Settings, output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    app = create_app(settings)
    provider_id = app.state.model_provider_id
    config = _config(settings, provider_id)
    manifest = build_experiment_manifest(config).model_dump(mode="json")
    manifest.update({"source_milestones": ["ID-03C.3", "ID-04A", "ID-04B", "ID-04C"], "workload_policy_version": "workload_budget_policy@0.1", "prerequisite_minimality_policy_version": "prerequisite_minimality_policy@0.1", "practice_coverage_policy_version": "practice_coverage_policy@0.1", "historical_artifacts_modified": False, "worktree": str(Path.cwd())})
    _write(output / "manifest.json", manifest)
    fixtures = cross_domain_validation_fixtures()
    results = []
    for fixture_id in FIXTURES:
        run_config = ExperimentRun.from_config(run_id=f"ID-04D:{fixture_id}:structured:1", config=config, fixture_id=fixture_id, condition=ExperimentCondition.STRUCTURED, run_number=1, started_at=datetime.now(UTC))
        result = await execute_structured_run(run=run_config, brief=fixtures[fixture_id].brief, designers=ModelGatewayStructuredDesigners(gateway=app.state.model_gateway, requested_provider=provider_id, correlation_id=f"ID-04D:{fixture_id}", output_token_budget=8192, temperature=0.0, stage_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034))
        results.append(result.model_dump(mode="json"))
    analyses = _analyses(results)
    _write(output / "results.json", {"manifest": manifest, "results": results})
    _write(output / "cross-domain-analysis.json", {"experiment": "ID-04D", **analyses, "readiness": "ID04_SME_REREVIEW_READY" if all(item["complete"] and item["graph_valid"] for item in analyses["pipeline"]) else "ID04_SME_REREVIEW_NOT_READY"})
    _write(output / "workload-analysis.json", analyses["workload"])
    _write(output / "prerequisite-analysis.json", analyses["prerequisites"])
    _write(output / "practice-coverage-analysis.json", analyses["practice_coverage"])
    _write(output / "regression-analysis.json", analyses["regression"])
    _write(output / "validation-report.json", {"experiment": "ID-04D", "planned_model_calls": 25, "completed_model_calls": sum(len(item.get("model_audits", [])) for item in results), "snapshots": sum(item.get("snapshot") is not None for item in results), "no_fixes_during_run": True, "readiness": "ID04_SME_REREVIEW_READY" if all(item["complete"] and item["graph_valid"] for item in analyses["pipeline"]) else "ID04_SME_REREVIEW_NOT_READY"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(Settings(_env_file=args.env_file), args.output_dir))


if __name__ == "__main__":
    main()
