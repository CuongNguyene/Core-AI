"""Offline Recovery-01 reporting for the immutable failed Luna baseline run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.job_semantics_eval import runner_openai_luna

FAILED_RUN_ID = "20261008T095324Z-luna-2ba7a268"
FAILED_RUN_ARTIFACT_SHA256 = {
    "results.jsonl": "sha256:d44baabdaf0f87f43b3d8ee269e4dedddfa5ea4e242b1524e5349ab5abc0af13",
    "run-manifest.json": "sha256:6b83f916941f535991e825543f8a68462dc9ae1232e247946b9b6ced787088b0",
}


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write_recovery_report(
    source_run_dir: Path,
    recovery_root: Path,
    *,
    expected_source_hashes: dict[str, str],
    expected_case_count: int,
) -> Path:
    """Verify source bytes, then write recomputable reports outside the failed run."""
    source_run_dir = source_run_dir.resolve()
    recovery_root = recovery_root.resolve()
    if not source_run_dir.is_dir():
        raise ValueError("failed run directory does not exist")
    if recovery_root == source_run_dir or source_run_dir in recovery_root.parents:
        raise ValueError("recovery artifacts must not be written inside the source run")
    if set(expected_source_hashes) != {"results.jsonl", "run-manifest.json"}:
        raise ValueError("recovery requires pinned hashes for results and run manifest")

    source_hashes: dict[str, str] = {}
    for filename, expected_hash in expected_source_hashes.items():
        artifact = source_run_dir / filename
        if not artifact.is_file():
            raise ValueError(f"immutable failed-run artifact missing: {filename}")
        actual_hash = _sha(artifact.read_bytes())
        if actual_hash != expected_hash:
            raise ValueError(f"immutable failed-run hash mismatch: {filename}")
        source_hashes[filename] = actual_hash

    result_records = [
        json.loads(line)
        for line in (source_run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(result_records) != expected_case_count:
        raise ValueError("failed run does not have the expected terminal case record count")
    source_manifest = json.loads((source_run_dir / "run-manifest.json").read_text(encoding="utf-8"))
    if source_manifest.get("run_id") != source_run_dir.name:
        raise ValueError("failed run manifest identity does not match its directory")
    if any(
        record.get("execution_status") in {"completed", "completed_empty_source"}
        for record in result_records
    ):
        raise ValueError(
            "Recovery-01 all-error report requires a run with no successful predictions"
        )

    report = runner_openai_luna.recompute_run_report(source_run_dir)
    if report["report_status"] != "complete" or report["quality_status"] != "NOT_MEASURABLE":
        raise ValueError("failed run did not produce the expected complete unmeasurable report")

    output_dir = recovery_root / source_run_dir.name
    output_dir.mkdir(parents=True, exist_ok=False)
    for filename, value in (
        ("recovery-report.json", report),
        ("operational-metrics.json", report["operational_metrics"]),
        ("provider-error-breakdown.json", report["provider_error_breakdown"]),
        ("error-analysis.json", report["error_analysis"]),
    ):
        (output_dir / filename).write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    manifest: dict[str, Any] = {
        "recovery_milestone": "PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-01-RECOVERY-01",
        "source_run_id": source_run_dir.name,
        "source_artifact_sha256": source_hashes,
        "source_case_count": len(result_records),
        "source_run_mutated": False,
        "report_status": report["report_status"],
        "quality_status": report["quality_status"],
        "provider_calls_during_recomputation": 0,
    }
    (output_dir / "recovery-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    for filename, expected_hash in source_hashes.items():
        if _sha((source_run_dir / filename).read_bytes()) != expected_hash:
            raise RuntimeError(f"source run changed during offline recovery: {filename}")
    return output_dir


def main() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    eval_root = backend_root / "evals/job_semantics/requirement_breakdown_01/openai-gpt-6-luna-v1"
    source_run = eval_root / "runs" / FAILED_RUN_ID
    output = write_recovery_report(
        source_run,
        eval_root / "recovery-01",
        expected_source_hashes=FAILED_RUN_ARTIFACT_SHA256,
        expected_case_count=40,
    )
    print(f"wrote offline Recovery-01 report: {output}")


if __name__ == "__main__":
    main()
