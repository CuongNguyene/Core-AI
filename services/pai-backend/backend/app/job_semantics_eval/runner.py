"""One-pass, append-only runner for the frozen synthetic EVAL-00 baseline."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.job_semantics_eval.freeze import (
    EVAL00,
    EVAL01,
    _canonical,
    _sha,
    verify_eval00,
    verify_or_freeze,
)
from app.job_semantics_eval.metrics import evaluate_dataset
from app.job_semantics_eval.provider import (
    extract_requirements,
    provider_input,
    register_extractor_contracts,
)
from app.job_semantics_eval.source_adapter import build_source_blocks
from app.job_semantics_eval.validation import InvalidProviderProvenance
from app.model_gateway.contracts import InferenceAuditMetadata
from app.model_gateway.errors import (
    PrivacyDeniedError,
    ProviderResponseError,
    ProviderTimeoutError,
    StructuredOutputFailedError,
)
from app.model_gateway.openai_responses import model_identity_matches
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.providers import ProviderRegistry
from app.model_gateway.routing import RoutingPolicy
from app.model_gateway.schema_registry import OutputSchemaRegistry
from app.model_gateway.service import ModelGatewayService
from app.privacy.service import LocalPIIInspector, PrivacyService
from app.shared.config import Settings

EXPECTED_MANIFEST = {
    "dataset_sha256": "sha256:6b9453a1c000f51a95b0ead39a94aca55eb7582489fca2a1b13550128df32cc5",
    "semantic_fingerprint": "sha256:b479fe2ecce0b7278506c4376e336b0cda916eba9f57c4e73b661e829a867421",
    "taxonomy_sha256": "sha256:bfb17a8f931e11f8c3e455048e9b4669c0cdd444246a66ade95a287e5a2622b4",
}


def _load_cases() -> list[dict[str, Any]]:
    path = EVAL00 / "dataset.synthetic.v1.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _safe_error_category(exc: Exception) -> str:
    if isinstance(exc, InvalidProviderProvenance):
        return exc.category
    if isinstance(exc, StructuredOutputFailedError):
        return "invalid_output_schema"
    if isinstance(exc, PrivacyDeniedError):
        return "privacy_denied"
    if isinstance(exc, ProviderTimeoutError):
        return "provider_timeout"
    if isinstance(exc, ProviderResponseError):
        return "provider_response_error"
    if isinstance(exc, ValueError):
        return "invalid_output_provenance"
    return "provider_or_gateway_error"


def model_drifted(configured_model: str, observed_model: str) -> bool:
    """Accept an observed dated snapshot of the configured model ID."""
    return not model_identity_matches(configured_model, observed_model)


def _build_gateway(settings: Settings) -> ModelGatewayService:
    from app.main import _build_model_provider

    provider = _build_model_provider(
        provider_id=settings.model_provider,
        endpoint=settings.vllm_base_url,
        api_key=settings.vllm_api_key,
        model=settings.vllm_model,
        timeout_seconds=settings.vllm_timeout_seconds,
        max_retries=settings.vllm_max_retries,
        max_tokens=settings.vllm_max_tokens,
        thinking_level=settings.gemini_thinking_level,
        retry_delay_seconds=settings.model_retry_base_delay_seconds,
    )
    provider_registry = ProviderRegistry()
    provider_registry.register(provider)
    provider_id = provider.provider_id
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extractor_contracts(prompts, schemas)
    return ModelGatewayService(
        prompt_templates=prompts,
        output_schemas=schemas,
        privacy_gateway=PrivacyService(
            LocalPIIInspector(),
            policy_version=settings.privacy_policy_version,
            external_public_data_enabled=settings.external_ai_enabled,
        ),
        routing_policy=RoutingPolicy(
            external_ai_enabled=settings.external_ai_enabled,
            external_restricted_data_approved=settings.external_restricted_data_approved,
            external_provider_id=(
                provider_id
                if provider.is_external
                else (settings.external_ai_provider or "vilao-external")
            ),
            configured_provider_id=provider_id,
        ),
        providers=provider_registry,
        model=settings.vllm_model,
        max_structured_repair_retries=settings.structured_output_repair_retries,
    )


async def run_full_baseline() -> Path:
    frozen = verify_or_freeze(create=False)
    verify_eval00()  # mandatory second verification immediately before provider execution
    settings = Settings(
        _env_file="/Users/mac/Developers/work/LMS/Core-AI/services/pai-backend/backend/.env"
    )
    spec = json.loads((EVAL01 / "extractor-spec-v1.json").read_text(encoding="utf-8"))
    if (
        not settings.external_ai_enabled
        or not settings.external_restricted_data_approved
        or not settings.vllm_api_key.get_secret_value()
        or settings.model_provider != spec["provider"]
        or settings.vllm_model != spec["model"]
        or settings.vllm_timeout_seconds != spec["provider_timeout_seconds"]
        or settings.vllm_max_retries != spec["provider_transport_retries"]
        or settings.structured_output_repair_retries != spec["structured_output_repair_retries"]
        or settings.gemini_thinking_level != spec["provider_thinking_level"]
        or settings.privacy_policy_version != spec["privacy_policy_version"]
    ):
        raise RuntimeError("runtime provider/privacy configuration does not match the frozen spec")

    cases = _load_cases()
    if len(cases) != 40:
        raise ValueError("frozen EVAL-00 case count changed")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output_dir = EVAL01 / "runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    run_manifest = {
        "run_id": run_id,
        "started_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "dataset_id": "jd-requirement-breakdown-synthetic-v1",
        "dataset_sha256": EXPECTED_MANIFEST["dataset_sha256"],
        "semantic_fingerprint": EXPECTED_MANIFEST["semantic_fingerprint"],
        "extractor_spec_sha256": frozen["extractor_spec_sha256"],
        "provider": spec["provider"],
        "configured_model": spec["model"],
        "model_revisions": [],
        "expected_cases": 40,
        "concurrency": 1,
        "privacy_tier": "RESTRICTED",
        "no_gold_sent": True,
        "live_provider_run": True,
    }
    (output_dir / "run-manifest.json").write_text(
        json.dumps(run_manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    gateway = _build_gateway(settings)
    result_records: list[dict[str, Any]] = []
    predictions: dict[str, tuple[Any, ...]] = {}
    errors: dict[str, str] = {}
    raw_counts: dict[str, int] = {}
    result_path = output_dir / "results.jsonl"
    for case in cases:
        case_id = str(case["case_id"])
        blocks = build_source_blocks(case.get("target_job_source"))
        projected = provider_input(blocks).model_dump(mode="json")
        input_fingerprint = _sha(
            _canonical(
                {
                    "provider_input": projected,
                    "extractor_spec_sha256": frozen["extractor_spec_sha256"],
                    "source_adapter_hash": frozen["component_sha256"][
                        "../../../app/job_semantics_eval/source_adapter.py"
                    ],
                }
            )
        )
        started = datetime.now(UTC)
        if not blocks:
            statements: tuple[Any, ...] = ()
            predictions[case_id] = statements
            record: dict[str, Any] = {
                "case_id": case_id,
                "dataset_fingerprint": EXPECTED_MANIFEST["semantic_fingerprint"],
                "extractor_spec_sha256": frozen["extractor_spec_sha256"],
                "input_fingerprint": input_fingerprint,
                "provider": spec["provider"],
                "configured_model": spec["model"],
                "model_revision": None,
                "execution_status": "completed_empty_source",
                "attempts": 0,
                "latency_ms": 0,
                "validated_prediction": [],
                "structured_output_sha256": None,
                "raw_structured_response_sha256": None,
                "raw_response_capture": "not exposed by ModelGateway",
                "error_category": None,
            }
            raw_counts[case_id] = 0
        else:
            try:
                statements, audit, raw_count, structured_output_sha256 = await extract_requirements(
                    gateway, blocks, input_fingerprint=input_fingerprint
                )
                assert isinstance(audit, InferenceAuditMetadata)
                raw_counts[case_id] = raw_count
                actual_model = audit.model
                model_drift = model_drifted(str(spec["model"]), actual_model)
                record = {
                    "case_id": case_id,
                    "dataset_fingerprint": EXPECTED_MANIFEST["semantic_fingerprint"],
                    "extractor_spec_sha256": frozen["extractor_spec_sha256"],
                    "input_fingerprint": input_fingerprint,
                    "provider": audit.provider,
                    "configured_model": spec["model"],
                    "actual_model": actual_model,
                    "model_revision": audit.model_revision,
                    "source_adapter_hash": frozen["component_sha256"][
                        "../../../app/job_semantics_eval/source_adapter.py"
                    ],
                    "execution_status": "error_model_drift" if model_drift else "completed",
                    "attempts": audit.provider_attempt_count,
                    "latency_ms": audit.latency_ms,
                    "validated_prediction": [row.model_dump(mode="json") for row in statements],
                    "structured_output_sha256": structured_output_sha256,
                    "raw_structured_response_sha256": None,
                    "raw_response_capture": "not exposed by ModelGateway; canonical parsed output hash recorded",
                    "error_category": "model_drift" if model_drift else None,
                }
                if model_drift:
                    errors[case_id] = "model_drift"
                else:
                    predictions[case_id] = statements
            except (
                Exception
            ) as exc:  # safe category only; evidence/provider payload is never logged
                category = _safe_error_category(exc)
                errors[case_id] = category
                raw_counts[case_id] = (
                    int(getattr(exc, "raw_statement_count", 0))
                    if isinstance(exc, InvalidProviderProvenance)
                    else 0
                )
                record = {
                    "case_id": case_id,
                    "dataset_fingerprint": EXPECTED_MANIFEST["semantic_fingerprint"],
                    "extractor_spec_sha256": frozen["extractor_spec_sha256"],
                    "input_fingerprint": input_fingerprint,
                    "provider": spec["provider"],
                    "configured_model": spec["model"],
                    "execution_status": "error",
                    "attempts": int(getattr(exc, "attempt_count", 0)),
                    "latency_ms": int((datetime.now(UTC) - started).total_seconds() * 1000),
                    "validated_prediction": None,
                    "structured_output_sha256": None,
                    "raw_structured_response_sha256": None,
                    "raw_response_capture": "not exposed by ModelGateway",
                    "error_category": category,
                }
        record["completed_at_utc"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with result_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        result_records.append(record)
        # Do not print or inspect per-case outputs before all 40 cases finish.

    metrics = evaluate_dataset(
        cases, predictions, execution_errors=errors, raw_statement_counts=raw_counts
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    run_manifest.update(
        {
            "finished_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "attempted_cases": len(result_records),
            "completed_cases": len(predictions),
            "provider_errors": len(errors),
            "model_revisions": sorted(
                {
                    str(row.get("model_revision"))
                    for row in result_records
                    if row.get("model_revision")
                }
            ),
            "results_jsonl_sha256": _sha(result_path.read_bytes()),
            "metrics_json_sha256": _sha((output_dir / "metrics.json").read_bytes()),
        }
    )
    (output_dir / "run-manifest.json").write_text(
        json.dumps(run_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_dir


def main() -> None:
    output = asyncio.run(run_full_baseline())
    print(f"completed synthetic baseline: {output}")


if __name__ == "__main__":
    main()
