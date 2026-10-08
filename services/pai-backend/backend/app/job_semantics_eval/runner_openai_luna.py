"""Frozen, sequential OpenAI Luna baseline runner for synthetic EVAL-00."""

from __future__ import annotations

import asyncio
import json
import statistics
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.job_semantics_eval.freeze_openai_luna import (
    LUNA_EVAL,
    verify_luna_freeze,
    verify_source_eval00,
)
from app.job_semantics_eval.metrics import _match_case, evaluate_dataset
from app.job_semantics_eval.openai_luna import (
    build_openai_luna_gateway,
    openai_execution_status,
    prepare_openai_luna_settings,
)
from app.job_semantics_eval.provider import extract_requirements
from app.job_semantics_eval.runner import _load_cases, model_drifted
from app.job_semantics_eval.source_adapter import build_source_blocks
from app.job_semantics_eval.validation import InvalidProviderProvenance
from app.model_gateway.contracts import InferenceAuditMetadata
from app.model_gateway.errors import (
    PrivacyDeniedError,
    ProviderIncompleteError,
    ProviderRefusalError,
    ProviderResponseError,
    ProviderSchemaError,
    ProviderTimeoutError,
    StructuredOutputFailedError,
)
from app.model_gateway.openai_responses import LUNA_MODEL
from app.shared.config import Settings


class ModelDriftError(RuntimeError):
    """Raised immediately when the returned model violates the frozen identity."""


def safe_error_category(exc: Exception) -> str:
    if isinstance(exc, InvalidProviderProvenance):
        return exc.category
    if isinstance(exc, ProviderRefusalError):
        return "refusal"
    if isinstance(exc, ProviderIncompleteError):
        return "incomplete"
    if isinstance(exc, (ProviderSchemaError, StructuredOutputFailedError)):
        return "schema_error"
    if isinstance(exc, PrivacyDeniedError):
        return "privacy_denied"
    transport_diagnostics = getattr(exc, "transport_diagnostics", None)
    if transport_diagnostics:
        diagnostic = transport_diagnostics[-1]
        if diagnostic.get("error_class") == "APIConnectionError":
            return "connection_error"
        if diagnostic.get("error_class") == "APITimeoutError":
            return "timeout"
    if isinstance(exc, ProviderTimeoutError):
        return "timeout"
    if isinstance(exc, ProviderResponseError):
        return "provider_error"
    return "provider_or_gateway_error"


def operational_metrics(records: list[dict[str, Any]], *, nonempty_cases: int) -> dict[str, Any]:
    attempts = [int(row.get("attempts", 0)) for row in records]
    latencies = sorted(int(row.get("latency_ms", 0)) for row in records)
    token_rows = [row.get("usage") or {} for row in records]

    def percentile(values: list[int], q: float) -> float | None:
        if not values:
            return None
        index = max(0, min(len(values) - 1, round((len(values) - 1) * q)))
        return float(values[index])

    statuses = [str(row.get("execution_status", "")) for row in records]
    return {
        "case_executions": len(records),
        "nonempty_cases": nonempty_cases,
        "provider_calls": sum(attempts),
        "retries": sum(max(0, attempt - 1) for attempt in attempts),
        "skipped_empty_source_cases": sum(
            status == "completed_empty_source" for status in statuses
        ),
        "completed_cases": sum(status.startswith("completed") for status in statuses),
        "errors": sum(status not in {"completed", "completed_empty_source"} for status in statuses),
        "refusals": sum(row.get("error_category") == "refusal" for row in records),
        "incomplete": sum(row.get("error_category") == "incomplete" for row in records),
        "schema_errors": sum(row.get("error_category") == "schema_error" for row in records),
        "provider_errors": sum(
            row.get("error_category")
            in {"timeout", "connection_error", "provider_error", "provider_or_gateway_error"}
            for row in records
        ),
        "latency_ms": {
            "total": sum(latencies),
            "mean": statistics.fmean(latencies) if latencies else None,
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
        },
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in token_rows),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in token_rows),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in token_rows),
        "cost": "NOT AVAILABLE; no approved deterministic price table",
        "observed_model_identities": sorted(
            {str(row["actual_model"]) for row in records if row.get("actual_model")}
        ),
    }


def error_analysis(
    cases: list[dict[str, Any]],
    predictions: dict[str, tuple[Any, ...]],
    execution_errors: dict[str, str] | None = None,
) -> dict[str, Any]:
    failures = execution_errors or {}
    per_case: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        if case_id not in predictions:
            per_case.append(
                {
                    "case_id": case_id,
                    "execution_error": failures.get(case_id),
                    "statement_type_errors": 0,
                    "capability_relevance_errors": 0,
                    "over_split": 0,
                    "under_split": 0,
                    "hallucinated": 0,
                    "missed": 0,
                    "exact_decomposition": False,
                }
            )
            continue
        match = _match_case(case, predictions.get(case_id, ()))
        type_errors = sum(
            pair.gold["statement_type"] != pair.prediction.statement_type for pair in match.pairs
        )
        relevance_errors = sum(
            pair.gold["capability_relevance"] != pair.prediction.capability_relevance
            for pair in match.pairs
        )
        per_case.append(
            {
                "case_id": case_id,
                "matched": len(match.pairs),
                "statement_type_errors": type_errors,
                "capability_relevance_errors": relevance_errors,
                "over_split": len(match.over_split_predictions),
                "under_split": len(match.under_split_gold),
                "hallucinated": len(match.hallucinated_predictions),
                "missed": len(match.missed_gold),
                "exact_decomposition": match.exact,
            }
        )
    return {
        "analysis_after_full_run_only": True,
        "case_count": len(per_case),
        "case_diagnostics": per_case,
        "classification_errors": {
            "statement_type": sum(row["statement_type_errors"] for row in per_case),
            "capability_relevance": sum(row["capability_relevance_errors"] for row in per_case),
        },
        "decomposition_errors": {
            "over_split": sum(row["over_split"] for row in per_case),
            "under_split": sum(row["under_split"] for row in per_case),
            "hallucinated": sum(row["hallucinated"] for row in per_case),
            "missed": sum(row["missed"] for row in per_case),
        },
    }


def provider_error_breakdown(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate only sanitized exception class metadata from result records."""
    errors = [row for row in records if row.get("error_category")]
    diagnostics = [
        diagnostic
        for row in errors
        for diagnostic in row.get("transport_diagnostics", [])
        if isinstance(diagnostic, dict)
    ]
    unclassified_attempts = sum(
        max(0, int(row.get("attempts", 0)) - len(row.get("transport_diagnostics", [])))
        for row in errors
    )

    def counts(field: str) -> dict[str, int]:
        result: dict[str, int] = {}
        for diagnostic in diagnostics:
            value = diagnostic.get(field)
            if isinstance(value, str):
                result[value] = result.get(value, 0) + 1
        return dict(sorted(result.items()))

    return {
        "error_case_count": len(errors),
        "attempt_count": len(diagnostics),
        "attempts_without_transport_diagnostics": unclassified_attempts,
        "by_error_category": _count_values(str(row["error_category"]) for row in errors),
        "by_error_class": counts("error_class"),
        "by_transport_error_class": counts("transport_error_class"),
        "by_transport_phase": counts("transport_phase"),
    }


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def recompute_run_report(run_dir: Path) -> dict[str, Any]:
    """Recompute metrics from stored outcomes without constructing a provider."""
    from app.job_semantics_eval.contracts import ValidatedRequirementStatement

    cases = _load_cases()
    records = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    expected_ids = [str(case["case_id"]) for case in cases]
    actual_ids = [str(record["case_id"]) for record in records]
    if actual_ids != expected_ids:
        raise ValueError("result case IDs/order do not match frozen EVAL-00")
    predictions: dict[str, tuple[Any, ...]] = {}
    errors: dict[str, str] = {}
    raw_counts: dict[str, int] = {}
    for record in records:
        case_id = str(record["case_id"])
        status = record["execution_status"]
        if status in {"completed", "completed_empty_source"}:
            predictions[case_id] = tuple(
                ValidatedRequirementStatement.model_validate(row)
                for row in (record.get("validated_prediction") or [])
            )
            raw_counts[case_id] = len(record.get("validated_prediction") or [])
        else:
            errors[case_id] = str(record.get("error_category") or "unknown_error")
            raw_counts[case_id] = int(record.get("raw_statement_count", 0))
    nonempty = sum(bool(build_source_blocks(case.get("target_job_source"))) for case in cases)
    computed_metrics = evaluate_dataset(
        cases, predictions, execution_errors=errors, raw_statement_counts=raw_counts
    )
    quality_measurable = bool(predictions)
    return {
        "report_status": "complete",
        "quality_status": "MEASURED" if quality_measurable else "NOT_MEASURABLE",
        "quality_metrics": computed_metrics if quality_measurable else None,
        "metrics": computed_metrics if quality_measurable else None,
        "operational_metrics": operational_metrics(records, nonempty_cases=nonempty),
        "provider_error_breakdown": provider_error_breakdown(records),
        "error_analysis": error_analysis(cases, predictions, errors),
        "provider_calls_during_recomputation": 0,
    }


async def run_full_openai_luna_baseline(settings: Settings) -> Path:
    frozen = verify_luna_freeze(settings)
    verify_source_eval00()
    prepared_settings = prepare_openai_luna_settings(settings)
    if settings.model_provider != "openai" or settings.vllm_model != LUNA_MODEL:
        raise ValueError("runtime provider/model differs from the frozen Luna spec")

    cases = _load_cases()
    blocks_by_case = {
        str(case["case_id"]): build_source_blocks(case.get("target_job_source")) for case in cases
    }
    nonempty_cases = sum(bool(blocks) for blocks in blocks_by_case.values())
    hard_call_cap = nonempty_cases * (settings.vllm_max_retries + 1)
    if hard_call_cap != frozen["hard_provider_call_cap"]:
        raise ValueError("runtime hard provider-call cap differs from frozen spec")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-luna-" + uuid.uuid4().hex[:8]
    output_dir = LUNA_EVAL / "runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    run_manifest: dict[str, Any] = {
        "run_id": run_id,
        "started_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "dataset_id": "pai-jd-requirement-breakdown-synthetic",
        "dataset_version": "requirement-breakdown-eval-00-v1",
        "dataset_sha256": frozen["dataset_sha256"],
        "semantic_fingerprint": frozen["semantic_fingerprint"],
        "taxonomy_sha256": frozen["taxonomy_sha256"],
        "freeze_manifest_sha256": frozen["freeze_manifest_sha256"],
        "extractor_spec_sha256": frozen["extractor_spec_sha256"],
        "provider": "openai",
        "api_family": "responses",
        "requested_model": LUNA_MODEL,
        "hard_provider_call_cap": hard_call_cap,
        "provider_calls_before_run": 0,
        "expected_cases": len(cases),
        "nonempty_cases": nonempty_cases,
        "concurrency": 1,
        "privacy_tier": "RESTRICTED",
        "no_gold_sent": True,
        "live_provider_run": True,
        "no_midrun_tuning": True,
    }
    run_manifest_path = output_dir / "run-manifest.json"
    run_manifest_path.write_text(
        json.dumps(run_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    gateway = build_openai_luna_gateway(prepared_settings)
    result_path = output_dir / "results.jsonl"
    records: list[dict[str, Any]] = []
    predictions: dict[str, tuple[Any, ...]] = {}
    errors: dict[str, str] = {}
    provider_calls = 0
    for case in cases:
        case_id = str(case["case_id"])
        blocks = blocks_by_case[case_id]
        input_fingerprint = frozen["input_fingerprint_by_case"][case_id]
        started = datetime.now(UTC)
        record: dict[str, Any]
        if not blocks:
            predictions[case_id] = ()
            record = {
                "case_id": case_id,
                "input_fingerprint": input_fingerprint,
                "provider": "openai",
                "requested_model": LUNA_MODEL,
                "execution_status": "completed_empty_source",
                "attempts": 0,
                "latency_ms": 0,
                "validated_prediction": [],
                "structured_output_sha256": None,
                "error_category": None,
                "usage": {},
            }
        else:
            try:
                statements, audit, raw_count, response_hash = await extract_requirements(
                    gateway, blocks, input_fingerprint=input_fingerprint
                )
                if not isinstance(audit, InferenceAuditMetadata):
                    raise TypeError("ModelGateway returned invalid audit metadata")
                provider_calls += audit.provider_attempt_count
                if audit.provider != "openai" or audit.requested_model != LUNA_MODEL:
                    raise RuntimeError("provider/model identity differs from frozen contract")
                drift = model_drifted(LUNA_MODEL, audit.model)
                if drift:
                    errors[case_id] = "model_drift"
                    record = {
                        "case_id": case_id,
                        "input_fingerprint": input_fingerprint,
                        "provider": audit.provider,
                        "requested_model": audit.requested_model,
                        "actual_model": audit.model,
                        "provider_response_id": audit.provider_response_id,
                        "execution_status": "error_model_drift",
                        "attempts": audit.provider_attempt_count,
                        "latency_ms": audit.latency_ms,
                        "validated_prediction": None,
                        "raw_statement_count": raw_count,
                        "structured_output_sha256": response_hash,
                        "error_category": "model_drift",
                        "usage": audit.usage.model_dump(mode="json"),
                    }
                else:
                    predictions[case_id] = statements
                    record = {
                        "case_id": case_id,
                        "input_fingerprint": input_fingerprint,
                        "provider": audit.provider,
                        "requested_model": audit.requested_model,
                        "actual_model": audit.model,
                        "provider_response_id": audit.provider_response_id,
                        "execution_status": "completed",
                        "attempts": audit.provider_attempt_count,
                        "latency_ms": audit.latency_ms,
                        "validated_prediction": [row.model_dump(mode="json") for row in statements],
                        "raw_statement_count": raw_count,
                        "structured_output_sha256": response_hash,
                        "error_category": None,
                        "usage": audit.usage.model_dump(mode="json"),
                    }
            except Exception as exc:  # no provider input/output or secrets are logged
                if isinstance(exc, PrivacyDeniedError):
                    raise
                category = safe_error_category(exc)
                attempt_count = int(getattr(exc, "attempt_count", 0))
                provider_calls += attempt_count
                errors[case_id] = category
                raw_count = int(getattr(exc, "raw_statement_count", 0))
                record = {
                    "case_id": case_id,
                    "input_fingerprint": input_fingerprint,
                    "provider": "openai",
                    "requested_model": LUNA_MODEL,
                    "execution_status": openai_execution_status(exc),
                    "attempts": attempt_count,
                    "latency_ms": max(0, int((datetime.now(UTC) - started).total_seconds() * 1000)),
                    "validated_prediction": None,
                    "raw_statement_count": raw_count,
                    "structured_output_sha256": None,
                    "error_category": category,
                    "transport_diagnostics": list(getattr(exc, "transport_diagnostics", [])),
                    "usage": {},
                }
        if provider_calls > hard_call_cap:
            raise RuntimeError("provider-call cap exceeded; transport must stop")
        record["dataset_fingerprint"] = frozen["semantic_fingerprint"]
        record["extractor_spec_sha256"] = frozen["extractor_spec_sha256"]
        record["source_adapter_hash"] = frozen["component_sha256"]["source_adapter"]
        record["provider_projection_hash"] = frozen["provider_projection_sha256"]
        record["completed_at_utc"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with result_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        records.append(record)
        if record.get("error_category") == "model_drift":
            raise ModelDriftError("observed model identity violates frozen Luna policy")
        # Intentionally emit no per-case result, so no mid-run semantic inspection/tuning occurs.

    if len(records) != 40:
        raise RuntimeError("full frozen corpus did not receive a terminal execution record")
    reports = recompute_run_report(output_dir)
    metrics = reports["metrics"]
    ops = reports["operational_metrics"]
    analysis = reports["error_analysis"]
    for name, value in (
        ("metrics.json", metrics),
        ("operational-metrics.json", ops),
        ("error-analysis.json", analysis),
        (
            "report-support.json",
            {
                "metrics": metrics,
                "quality_status": reports["quality_status"],
                "quality_metrics": reports["quality_metrics"],
                "operational_metrics": ops,
                "provider_error_breakdown": reports["provider_error_breakdown"],
                "error_analysis": analysis,
                "provider_calls_during_recomputation": 0,
            },
        ),
    ):
        (output_dir / name).write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    run_manifest.update(
        {
            "finished_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "attempted_cases": len(records),
            "completed_cases": len(predictions),
            "provider_errors": len(errors),
            "provider_calls": provider_calls,
            "retries": ops["retries"],
            "observed_model_identities": ops["observed_model_identities"],
            "results_jsonl_sha256": _sha(result_path.read_bytes()),
        }
    )
    run_manifest_path.write_text(
        json.dumps(run_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_dir


def _sha(data: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(data).hexdigest()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings(_env_file=args.env_file)
    output = asyncio.run(run_full_openai_luna_baseline(settings))
    print(f"completed OpenAI Luna baseline: {output}")


if __name__ == "__main__":
    main()
