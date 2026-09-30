"""Offline replay harness for EXT-03A.10 deterministic evidence gating."""

import argparse
import json
from pathlib import Path
from typing import Any

from app.extraction.capability_evidence_gate import (
    apply_capability_evidence_gate,
    build_gate_set,
    calculate_replay_metrics,
    gate_set_artifact,
)
from app.extraction.capability_taxonomy import (
    TAXONOMY_ID,
    TAXONOMY_VERSION,
    TaxonomySelectedCapability,
    TaxonomySelection,
)
from app.extraction.two_stage_capability_schema import ExperimentalCvFacts

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RESULTS = BACKEND_ROOT / "test" / "results"
SOURCE_C = RESULTS / "ext-03a8-selection-semantics"
SOURCE_36 = RESULTS / "ext-03a9-flash-model-comparison-run3"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _expectations() -> dict[str, dict[str, Any]]:
    payload = _read(SOURCE_C / "expectations.json")
    return {item["fixture_id"]: item for item in payload["fixtures"]}


def _selection(record: dict[str, Any], selected_field: str) -> TaxonomySelection | None:
    selected = record.get(selected_field)
    if not selected or "supporting_statement_ids" not in record:
        return None
    return TaxonomySelection(
        taxonomy_id=TAXONOMY_ID,
        taxonomy_version=TAXONOMY_VERSION,
        capabilities=[
            TaxonomySelectedCapability(
                capability_id=capability_id,
                supporting_statement_ids=refs,
            )
            for capability_id, refs in record["supporting_statement_ids"].items()
            if capability_id in selected
        ],
    )


def _records(source_dir: Path, *, model: str) -> list[dict[str, Any]]:
    if model == "gemini-3.6-flash":
        return [
            {"fixture_id": item["fixture_id"], "record": item}
            for item in _read(source_dir / "gemini-3.6-flash.json")
        ]
    records: list[dict[str, Any]] = []
    for path in sorted((source_dir / "per-cv").glob("*.json")):
        payload = _read(path)
        records.append({"fixture_id": payload["fixture_id"], "record": payload})
    return records


def _write(output: Path, name: str, payload: Any) -> None:
    (output / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def run(output_dir: Path, facts_dir: Path | None) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("OUTPUT_DIR_MUST_BE_EMPTY_NO_RESAMPLING")
    output_dir.mkdir(parents=True, exist_ok=True)
    gate_set = build_gate_set()
    expectations = _expectations()
    manifest = {
        "experiment_id": "EXT-03A.10",
        "taxonomy_id": TAXONOMY_ID,
        "taxonomy_version": TAXONOMY_VERSION,
        "gate_id": gate_set.gate_id,
        "gate_version": gate_set.version,
        "expectation_source": "ext-03a8-selection-semantics/expectations.json",
        "historical_sources": [
            "ext-03a8-selection-semantics",
            "ext-03a9-flash-model-comparison-run3/gemini-3.6-flash.json",
        ],
        "provider_calls": 0,
        "facts_source": str(facts_dir) if facts_dir else None,
    }
    _write(output_dir, "manifest.json", manifest)
    _write(output_dir, "gate-set.json", gate_set_artifact(gate_set))

    source_status: dict[str, Any] = {}
    if facts_dir is None:
        source_status["formulation-c"] = {
            "status": "NOT_REPLAYABLE",
            "reason": "historical C artifact has no supporting_statement_ids",
        }
        source_status["gemini-3.6-flash"] = {
            "status": "NOT_REPLAYABLE",
            "reason": "Stage-1 factual statements are not persisted in historical artifacts",
        }
        _write(output_dir, "replay-status.json", source_status)
        _write(output_dir, "aggregate.json", {"status": "BLOCKED", "provider_calls": 0})
        _write(
            output_dir,
            "evaluation.md",
            "# EXT-03A.10\n\nHistorical replay is blocked: evidence refs or Stage-1 factual text are unavailable. No provider calls were made.\n",
        )
        return {"status": "BLOCKED", "provider_calls": 0, "sources": source_status}

    facts_by_fixture: dict[str, ExperimentalCvFacts] = {}
    for fixture_id, expected in expectations.items():
        path = facts_dir / f"{fixture_id}.json"
        if not path.is_file():
            raise RuntimeError(f"MISSING_FACTS_ARTIFACT:{fixture_id}")
        facts = ExperimentalCvFacts.model_validate_json(path.read_text(encoding="utf-8"))
        if facts.document_id == "":
            raise RuntimeError(f"INVALID_FACTS_ARTIFACT:{fixture_id}")
        facts_by_fixture[fixture_id] = facts
        if expected["sha256"] == "":
            raise RuntimeError(f"INVALID_EXPECTATION:{fixture_id}")

    outputs: dict[str, list[dict[str, Any]]] = {}
    for source_name, source_dir, selected_field in (
        ("formulation-c", SOURCE_C, "selected_capability_ids"),
        ("gemini-3.6-flash", SOURCE_36, "selected_capability_ids"),
    ):
        rows: list[dict[str, Any]] = []
        for entry in _records(source_dir, model=source_name):
            record = entry["record"]
            selection = _selection(record, selected_field)
            if selection is None:
                continue
            gated = apply_capability_evidence_gate(selection, facts_by_fixture[entry["fixture_id"]], gate_set)
            expected_ids = expectations[entry["fixture_id"]]["expected_supported_capability_ids"]
            row = {
                "fixture_id": entry["fixture_id"],
                "before_ids": [item.capability_id for item in selection.capabilities],
                "after_ids": gated.accepted_capabilities,
                "metrics": calculate_replay_metrics(
                    before_ids=[item.capability_id for item in selection.capabilities],
                    after_ids=gated.accepted_capabilities,
                    expected_ids=expected_ids,
                ),
                "decisions": [
                    {
                        "capability_id": item.capability_id,
                        "accepted": item.accepted,
                        "reason_code": item.reason_code,
                        "accepted_statement_ids": item.accepted_statement_ids,
                        "rejected_statement_ids": item.rejected_statement_ids,
                    }
                    for item in gated.decisions
                ],
            }
            rows.append(row)
        outputs[source_name] = rows
        _write(output_dir, f"replay-{source_name}.json", rows)
        source_status[source_name] = {"status": "AVAILABLE", "records": len(rows)}

    _write(output_dir, "replay-status.json", source_status)
    _write(output_dir, "aggregate.json", {"status": "COMPLETE", "provider_calls": 0})
    _write(output_dir, "evaluation.md", "# EXT-03A.10\n\nOffline replay completed.\n")
    return {"status": "COMPLETE", "provider_calls": 0, "sources": source_status}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--facts-dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.facts_dir), indent=2))


if __name__ == "__main__":
    main()
