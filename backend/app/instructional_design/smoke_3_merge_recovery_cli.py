"""Merge one recovered Smoke-3 result without mutating the original artifact."""

import argparse
import json
from pathlib import Path

from app.instructional_design.experiment import (
    ExperimentManifest,
    ExperimentRunResult,
    aggregate_experiment_results,
    build_experiment_comparisons,
)
from app.instructional_design.smoke_3_cli import Smoke3Execution


def merge_recovery(
    *, parent_results: Path, recovery_results: Path, output: Path
) -> Smoke3Execution:
    parent = json.loads(parent_results.read_text(encoding="utf-8"))
    recovery = json.loads(recovery_results.read_text(encoding="utf-8"))
    existing = [
        ExperimentRunResult.model_validate_json(json.dumps(item)) for item in parent["results"]
    ]
    recovered = ExperimentRunResult.model_validate_json(json.dumps(recovery["result"]))
    key = (recovered.run.fixture_id, recovered.run.condition.value)
    replaced = [
        recovered
        if (item.run.fixture_id, item.run.condition.value) == key
        else item
        for item in existing
    ]
    if not any((item.run.fixture_id, item.run.condition.value) == key for item in existing):
        raise ValueError("recovery target does not match a parent result")
    execution = Smoke3Execution(
        manifest=ExperimentManifest.model_validate_json(json.dumps(parent["manifest"])),
        results=replaced,
        comparisons=build_experiment_comparisons(replaced),
        aggregation=aggregate_experiment_results(replaced),
    )
    output.write_text(
        json.dumps(execution.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return execution


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge the recovered Smoke-3 result.")
    parser.add_argument("--parent-results", type=Path, required=True)
    parser.add_argument("--recovery-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execution = merge_recovery(
        parent_results=args.parent_results,
        recovery_results=args.recovery_results,
        output=args.output,
    )
    print(json.dumps({"result_count": len(execution.results)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
