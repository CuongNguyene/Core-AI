from __future__ import annotations

import json

from app.job_semantics_eval import runner_openai_luna as runner


def test_recompute_report_is_offline_and_preserves_empty_success(tmp_path, monkeypatch) -> None:
    cases = [
        {
            "case_id": "fixture-001",
            "target_job_source": None,
            "expected_statements": [],
            "domain": "TECHNICAL_FIXTURE",
            "language_profile": "ENGLISH",
            "difficulty": "EASY",
            "boundary_tags": [],
        },
        {
            "case_id": "fixture-002",
            "target_job_source": None,
            "expected_statements": [],
            "domain": "TECHNICAL_FIXTURE",
            "language_profile": "ENGLISH",
            "difficulty": "EASY",
            "boundary_tags": [],
        },
    ]
    monkeypatch.setattr(runner, "_load_cases", lambda: cases)
    monkeypatch.setattr(
        runner,
        "build_openai_luna_gateway",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("provider must not be built")
        ),
    )
    run_dir = tmp_path / "offline-run"
    run_dir.mkdir()
    records = [
        {
            "case_id": "fixture-001",
            "execution_status": "completed_empty_source",
            "attempts": 0,
            "latency_ms": 0,
            "validated_prediction": [],
            "usage": {},
        },
        {
            "case_id": "fixture-002",
            "execution_status": "completed_empty_source",
            "attempts": 0,
            "latency_ms": 0,
            "validated_prediction": [],
            "usage": {},
        },
    ]
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    report = runner.recompute_run_report(run_dir)

    assert report["provider_calls_during_recomputation"] == 0
    assert report["metrics"]["execution"]["completed_cases"] == 2
    assert report["metrics"]["decomposition"]["case_exact_decomposition_rate"] == 1.0
    assert report["operational_metrics"]["skipped_empty_source_cases"] == 2


def test_operational_metrics_separates_attempts_retries_and_empty_skips() -> None:
    records = [
        {
            "execution_status": "completed",
            "attempts": 2,
            "latency_ms": 200,
            "usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
        },
        {"execution_status": "completed_empty_source", "attempts": 0, "latency_ms": 0, "usage": {}},
        {
            "execution_status": "REFUSAL",
            "error_category": "refusal",
            "attempts": 1,
            "latency_ms": 80,
            "usage": {},
        },
    ]

    result = runner.operational_metrics(records, nonempty_cases=2)

    assert result["provider_calls"] == 3
    assert result["retries"] == 1
    assert result["skipped_empty_source_cases"] == 1
    assert result["refusals"] == 1
    assert result["input_tokens"] == 20
    assert result["output_tokens"] == 5


def test_historical_eval00_artifacts_verify_without_rewriting_freeze_identity() -> None:
    result = runner.verify_source_eval00()

    assert result["manifest"]["counts"]["posting_count"] == 40
    assert result["manifest"]["counts"]["atomic_statement_count"] == 301
    assert result["manifest"]["code_head"] == "0654cf0f3d64aafaa7c001c74e578643d07d1e03"


def test_all_provider_errors_produce_complete_unmeasurable_report_offline(
    tmp_path, monkeypatch
) -> None:
    cases = [
        {
            "case_id": f"fixture-{index:03d}",
            "target_job_source": {"job_description_html": f"Synthetic source {index}"},
            "expected_statements": [],
            "domain": "TECHNICAL_FIXTURE",
            "language_profile": "ENGLISH",
            "difficulty": "EASY",
            "boundary_tags": [],
        }
        for index in range(40)
    ]
    monkeypatch.setattr(runner, "_load_cases", lambda: cases)
    monkeypatch.setattr(
        runner,
        "build_openai_luna_gateway",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("report recomputation must remain offline")
        ),
    )
    run_dir = tmp_path / "failed-run"
    run_dir.mkdir()
    records = [
        {
            "case_id": case["case_id"],
            "execution_status": "PROVIDER_ERROR",
            "error_category": "connection_error",
            "attempts": 2,
            "latency_ms": 1000,
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
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    report = runner.recompute_run_report(run_dir)

    assert report["report_status"] == "complete"
    assert report["quality_status"] == "NOT_MEASURABLE"
    assert report["quality_metrics"] is None
    assert report["metrics"] is None
    assert report["operational_metrics"]["provider_calls"] == 80
    assert report["operational_metrics"]["errors"] == 40
    assert report["provider_error_breakdown"]["attempt_count"] == 80
    assert report["provider_error_breakdown"]["by_error_class"] == {"APIConnectionError": 80}
    assert report["provider_error_breakdown"]["by_transport_phase"] == {"connect": 80}
    assert report["error_analysis"]["case_count"] == 40
    assert report["error_analysis"]["classification_errors"] == {
        "statement_type": 0,
        "capability_relevance": 0,
    }
    assert report["provider_calls_during_recomputation"] == 0
