from __future__ import annotations

import hashlib
import json

from app.job_semantics_eval import recovery_01


def _sha(path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_recovery_report_is_written_separately_and_preserves_failed_run(
    tmp_path, monkeypatch
) -> None:
    source_run = tmp_path / "failed-run"
    source_run.mkdir()
    cases = [
        {
            "case_id": f"fixture-{index:03d}",
            "target_job_source": {"job_description_html": f"synthetic {index}"},
            "expected_statements": [],
            "domain": "TECHNICAL_FIXTURE",
            "language_profile": "ENGLISH",
            "difficulty": "EASY",
            "boundary_tags": [],
        }
        for index in range(40)
    ]
    monkeypatch.setattr(recovery_01.runner_openai_luna, "_load_cases", lambda: cases)
    records = [
        {
            "case_id": case["case_id"],
            "execution_status": "PROVIDER_ERROR",
            "error_category": "connection_error",
            "attempts": 2,
            "latency_ms": 50,
            "usage": {},
            "transport_diagnostics": [
                {
                    "error_class": "APIConnectionError",
                    "transport_error_class": "ConnectError",
                    "transport_phase": "connect",
                    "attempt": attempt,
                    "cause_chain": ["APIConnectionError", "ConnectError"],
                }
                for attempt in (1, 2)
            ],
        }
        for case in cases
    ]
    result_path = source_run / "results.jsonl"
    result_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    manifest_path = source_run / "run-manifest.json"
    manifest_path.write_text(
        json.dumps({"run_id": source_run.name, "expected_cases": 40}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    expected_hashes = {
        "results.jsonl": _sha(result_path),
        "run-manifest.json": _sha(manifest_path),
    }
    before = {
        name: path.read_bytes()
        for name, path in (("results.jsonl", result_path), ("run-manifest.json", manifest_path))
    }

    report_dir = recovery_01.write_recovery_report(
        source_run,
        tmp_path / "recovery-output",
        expected_source_hashes=expected_hashes,
        expected_case_count=40,
    )

    assert {
        name: path.read_bytes()
        for name, path in (("results.jsonl", result_path), ("run-manifest.json", manifest_path))
    } == before
    report = json.loads((report_dir / "recovery-report.json").read_text())
    recovery_manifest = json.loads((report_dir / "recovery-manifest.json").read_text())
    assert report["report_status"] == "complete"
    assert report["quality_status"] == "NOT_MEASURABLE"
    assert report["quality_metrics"] is None
    assert report["operational_metrics"]["provider_calls"] == 80
    assert report["provider_error_breakdown"]["by_transport_phase"] == {"connect": 80}
    assert recovery_manifest["source_artifact_sha256"] == expected_hashes
    assert recovery_manifest["source_run_mutated"] is False


def test_recovery_refuses_changed_failed_run_artifact(tmp_path) -> None:
    source_run = tmp_path / "failed-run"
    source_run.mkdir()
    (source_run / "results.jsonl").write_text("changed\n", encoding="utf-8")
    (source_run / "run-manifest.json").write_text('{"run_id":"failed-run"}\n', encoding="utf-8")

    try:
        recovery_01.write_recovery_report(
            source_run,
            tmp_path / "recovery-output",
            expected_source_hashes={
                "results.jsonl": "sha256:wrong",
                "run-manifest.json": _sha(source_run / "run-manifest.json"),
            },
            expected_case_count=1,
        )
    except ValueError as exc:
        assert "immutable failed-run hash mismatch" in str(exc)
    else:
        raise AssertionError("changed failed run was accepted")
