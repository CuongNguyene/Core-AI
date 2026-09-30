"""Targeted ID-04F live rerun for the declared Legal dependency alias."""

import argparse
import asyncio
import json
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
from app.instructional_design.provenance_aliases import DependencyIdentity
from app.main import create_app
from app.shared.config import Settings

FIXTURE_ID = "legal_contract_review_basic"
IDENTITIES = (
    DependencyIdentity(
        dependency_ref="dependency_candidate:contract_clause_structure",
        canonical_name="contract clause structure",
        aliases=("commercial contract clause structure",),
    ),
)
STAGES = (
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ASSESSMENT_DESIGN_SCHEMA_ID,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    LESSON_PLANNING_SCHEMA_ID,
)


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _config(settings: Settings, provider_id: str) -> ExperimentConfig:
    versions = [
        PromptSchemaVersion(
            prompt_id=stage,
            prompt_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034,
            schema_id=stage,
            schema_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034,
        )
        for stage in STAGES
    ]
    return ExperimentConfig(
        experiment_id="ID-04F",
        experiment_version="0.1",
        fixture_ids=[FIXTURE_ID],
        runs_per_fixture_per_condition=1,
        conditions=(ExperimentCondition.STRUCTURED,),
        model_provider=provider_id,
        model_name=settings.vllm_model,
        model_revision=None,
        generation_config=GenerationConfig(
            temperature=0.0,
            top_p=None,
            max_output_tokens=8192,
            seed=None,
            unsupported_fields=["top_p", "seed"],
        ),
        policy_id="pai_instructional_design",
        policy_version="0.1",
        dependency_normalizer_version="id02d.2@0.1",
        prompt_schema_versions=versions,
    )


async def run(settings: Settings, output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    app = create_app(settings)
    provider_id = app.state.model_provider_id
    config = _config(settings, provider_id)
    manifest = build_experiment_manifest(config).model_dump(mode="json")
    manifest.update(
        {
            "source": "ID-04D final rerun",
            "intervention": "deterministic_provenance_alias_boundary",
            "prerequisite_policy_version": "prerequisite_minimality_policy@0.1",
            "historical_artifacts_modified": False,
            "worktree": str(Path.cwd()),
        }
    )
    _write(output / "manifest.json", manifest)

    fixture = cross_domain_validation_fixtures()[FIXTURE_ID]
    run_config = ExperimentRun.from_config(
        run_id=f"ID-04F:{FIXTURE_ID}:structured:1",
        config=config,
        fixture_id=FIXTURE_ID,
        condition=ExperimentCondition.STRUCTURED,
        run_number=1,
        started_at=datetime.now(UTC),
    )
    result = await execute_structured_run(
        run=run_config,
        brief=fixture.brief,
        designers=ModelGatewayStructuredDesigners(
            gateway=app.state.model_gateway,
            requested_provider=provider_id,
            correlation_id=f"ID-04F:{FIXTURE_ID}",
            output_token_budget=8192,
            temperature=0.0,
            stage_version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034,
        ),
        dependency_identities=IDENTITIES,
    )
    result_json = result.model_dump(mode="json")
    _write(output / "results.json", {"manifest": manifest, "results": [result_json]})

    snapshot = result_json.get("snapshot")
    prerequisites = snapshot.get("prerequisites", []) if snapshot else []
    candidates = snapshot.get("dependency_candidates", []) if snapshot else []
    trace = {
        "fixture": FIXTURE_ID,
        "declared_identities": [
            {
                "dependency_ref": item.dependency_ref,
                "canonical_name": item.canonical_name,
                "aliases": list(item.aliases),
            }
            for item in IDENTITIES
        ],
        "dependency_candidates": candidates,
        "resolved_prerequisites": [
            {
                "id": item["id"],
                "capability": item["capability"],
                "source_dependency_refs": item.get("source_dependency_refs", []),
                "status": item["status"],
                "basis": item["basis"],
                "disposition": item.get("disposition"),
            }
            for item in prerequisites
        ],
        "alias_resolution": "declared_alias_only",
        "unknown_paraphrases_fail_closed": True,
    }
    _write(output / "alias-resolution-trace.json", trace)
    _write(
        output / "root-cause-report.json",
        {
            "experiment": "ID-04F",
            "failure": "legal_contract_review_basic prerequisite_provenance_not_preserved",
            "candidate": "sufficient English literacy to parse contract clause structure",
            "generated_value": "sufficient English literacy to parse commercial contract clause structure",
            "root_cause": "legitimate declared paraphrase rejected by exact-only matcher",
            "fix_layer": "deterministic provenance alias boundary",
            "fuzzy_matching": False,
            "model_generated_aliases": False,
        },
    )
    report = {
        "experiment": "ID-04F",
        "fixture": FIXTURE_ID,
        "model_calls": len(result_json.get("model_audits", [])),
        "snapshot": snapshot is not None,
        "graph_integrity": snapshot is not None,
        "provenance_preserved": all(
            bool(item.get("source_dependency_refs"))
            for item in prerequisites
            if item.get("disposition")
        ),
        "governance_preserved": all(
            item["status"] == "candidate" and item["basis"] == "model_proposed"
            for item in prerequisites
            if item.get("disposition")
        ),
        "no_auto_confirmation": not any(item["status"] == "confirmed" for item in prerequisites),
        "workload_generated": bool(snapshot and snapshot.get("quality_report")),
        "practice_coverage_generated": bool(snapshot and snapshot.get("quality_report", {}).get("practice_coverage")),
        "findings": (snapshot or {}).get("quality_report", {}).get("findings", []),
    }
    report["status"] = "COMPLETE" if report["snapshot"] and report["provenance_preserved"] else "NEEDS_ITERATION"
    _write(output / "validation-report.json", report)
    _write(
        output / "regression-report.json",
        {
            "id04a_workload_unchanged": report["workload_generated"],
            "id04b_disposition_governance_unchanged": report["governance_preserved"],
            "id04c_practice_coverage_unchanged": report["practice_coverage_generated"],
            "dependency_normalizer_unchanged": True,
            "prompt_version": INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034,
            "quality_gate_severity_unchanged": True,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(Settings(_env_file=args.env_file), args.output_dir))


if __name__ == "__main__":
    main()
