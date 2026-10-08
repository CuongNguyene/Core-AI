"""Immutable OpenAI Luna freeze for the requirement-breakdown EVAL-00 baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.job_semantics_eval.contracts import JobRequirementExtractionOutputV1, ProviderInputV1
from app.job_semantics_eval.openai_luna import (
    openai_luna_spec_fingerprint,
    prepare_openai_luna_settings,
)
from app.job_semantics_eval.provider import (
    SYSTEM_INSTRUCTION,
    USER_INSTRUCTION,
    provider_input,
)
from app.job_semantics_eval.runner import _load_cases
from app.job_semantics_eval.source_adapter import build_source_blocks
from app.model_gateway.openai_responses import LUNA_MODEL
from app.shared.config import Settings
from evals.job_semantics.requirement_breakdown_eval_00.validate_and_freeze import (
    verify_freeze_manifest,
)

BACKEND = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = BACKEND / "evals/job_semantics/requirement_breakdown_01"
LUNA_EVAL = RESEARCH_ROOT / "openai-gpt-6-luna-v1"
EVAL00 = BACKEND / "evals/job_semantics/requirement_breakdown_eval_00"
FREEZE_MANIFEST = LUNA_EVAL / "freeze-manifest.json"

EXPECTED_EVAL00 = {
    "dataset_jsonl_sha256": "sha256:6b9453a1c000f51a95b0ead39a94aca55eb7582489fca2a1b13550128df32cc5",
    "semantic_fingerprint_sha256": "sha256:b479fe2ecce0b7278506c4376e336b0cda916eba9f57c4e73b661e829a867421",
    "taxonomy_sha256": "sha256:bfb17a8f931e11f8c3e455048e9b4669c0cdd444246a66ade95a287e5a2622b4",
}

COMPONENT_FILES = {
    "contracts": "app/job_semantics_eval/contracts.py",
    "provider": "app/job_semantics_eval/provider.py",
    "source_adapter": "app/job_semantics_eval/source_adapter.py",
    "provenance_validator": "app/job_semantics_eval/validation.py",
    "matcher_metrics": "app/job_semantics_eval/metrics.py",
    "openai_gateway_composition": "app/job_semantics_eval/openai_luna.py",
    "baseline_runner": "app/job_semantics_eval/runner_openai_luna.py",
    "freeze_verifier": "app/job_semantics_eval/freeze_openai_luna.py",
    "openai_responses_adapter": "app/model_gateway/openai_responses.py",
    "model_gateway_contract": "app/model_gateway/contracts.py",
    "model_gateway_errors": "app/model_gateway/errors.py",
    "model_gateway_prompts": "app/model_gateway/prompts.py",
    "model_gateway_provider_contract": "app/model_gateway/providers.py",
    "model_gateway_routing": "app/model_gateway/routing.py",
    "model_gateway_schema_registry": "app/model_gateway/schema_registry.py",
    "model_gateway_service": "app/model_gateway/service.py",
    "privacy_gateway": "app/privacy/service.py",
    "settings_contract": "app/shared/config.py",
    "dependency_manifest": "pyproject.toml",
    "dependency_lock": "uv.lock",
    "eval00_freeze_verifier": "evals/job_semantics/requirement_breakdown_eval_00/validate_and_freeze.py",
}

SPEC_FILES = (
    "extractor-spec.json",
    "provider-projection-spec.json",
    "output-schema.json",
    "provenance-spec.json",
    "matching-spec.json",
    "metrics-spec.json",
    "runner-spec.json",
)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def verify_source_eval00() -> dict[str, Any]:
    """Verify frozen corpus bytes while retaining its historical code-head pin."""
    manifest_path = EVAL00 / "manifest.synthetic.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verification = verify_freeze_manifest(EVAL00, manifest)
    for key, expected in EXPECTED_EVAL00.items():
        if "sha256:" + str(manifest.get("hashes", {}).get(key, "")) != expected:
            raise ValueError(f"EVAL-00 expected identity mismatch: {key}")
    if manifest.get("counts", {}).get("posting_count") != 40:
        raise ValueError("EVAL-00 posting count mismatch")
    if manifest.get("counts", {}).get("atomic_statement_count") != 301:
        raise ValueError("EVAL-00 gold statement count mismatch")
    if manifest.get("provider_calls_before_freeze") != 0:
        raise ValueError("EVAL-00 provider_calls_before_freeze must remain zero")
    return {
        "manifest": manifest,
        "verification": verification,
        "artifact_sha256": _sha(manifest_path.read_bytes()),
    }


def _validate_settings(settings: Settings) -> None:
    prepare_openai_luna_settings(settings)
    if settings.vllm_timeout_seconds != 200.0:
        raise ValueError("provider timeout differs from the preregistered 200-second value")
    if settings.vllm_max_retries != 1:
        raise ValueError("provider retry count differs from the preregistered one retry")
    if settings.model_retry_base_delay_seconds != 1.0:
        raise ValueError("provider retry delay differs from the preregistered one-second base")
    if settings.privacy_policy_version != "privacy-v1":
        raise ValueError("privacy policy identity differs from the preregistered value")


def _artifact_specs(settings: Settings) -> dict[str, object]:
    _validate_settings(settings)
    eval00 = verify_source_eval00()["manifest"]
    cases = _load_cases()
    nonempty = sum(bool(build_source_blocks(case.get("target_job_source"))) for case in cases)
    schema = JobRequirementExtractionOutputV1.model_json_schema()
    input_schema = ProviderInputV1.model_json_schema()
    return {
        "extractor-spec.json": {
            "extractor_id": "jd-requirement-breakdown-openai-luna",
            "extractor_version": "1.0.0",
            "provider": "openai",
            "api_family": "responses",
            "model": LUNA_MODEL,
            "structured_output": "Responses API parse + strict Pydantic output_parsed",
            "reasoning_effort": "not exposed by approved adapter",
            "temperature": 0,
            "max_output_tokens": 8192,
            "structured_output_repair_retries": 0,
            "provider_timeout_seconds": settings.vllm_timeout_seconds,
            "provider_transport_retries": settings.vllm_max_retries,
            "retry_base_delay_seconds": settings.model_retry_base_delay_seconds,
            "maximum_attempts_per_case": settings.vllm_max_retries + 1,
            "retry_classes": ["timeout", "connection_failure", "429", "5xx"],
            "retry_request_unchanged": True,
            "model_identity_policy": "exact gpt-6-luna or dated snapshot beginning gpt-6-luna-",
            "privacy_tier": "RESTRICTED",
            "privacy_policy_version": settings.privacy_policy_version,
            "system_instruction": SYSTEM_INSTRUCTION,
            "extractor_instruction": USER_INSTRUCTION,
            "empty_source": "empty prediction; zero provider calls",
            "provider_calls_before_freeze": 0,
            "dataset_sha256": "sha256:" + eval00["hashes"]["dataset_jsonl_sha256"],
            "semantic_fingerprint": "sha256:" + eval00["hashes"]["semantic_fingerprint_sha256"],
            "taxonomy_sha256": "sha256:" + eval00["hashes"]["taxonomy_sha256"],
            "case_count": 40,
            "gold_statement_count": 301,
            "nonempty_cases": nonempty,
            "hard_provider_call_cap": nonempty * (settings.vllm_max_retries + 1),
            "primary_metrics": [
                "statement_f1",
                "case_exact_decomposition_rate",
                "statement_type_macro_f1",
                "capability_relevance_macro_f1",
                "valid_source_span_rate",
            ],
            "no_midrun_tuning": True,
            "no_provider_fallback": True,
        },
        "provider-projection-spec.json": {
            "allowed_payload": {"source_blocks": ["block_id", "source_field", "text"]},
            "source_fields": ["JOB_DESCRIPTION", "JOB_REQUIREMENTS"],
            "excluded": [
                "source_application_ref",
                "job_posting_url",
                "case_id",
                "gold",
                "expected_statements",
                "difficulty",
                "boundary_tags",
                "review_metadata",
                "candidate_data",
                "employee_identity",
                "salary",
                "benefits",
            ],
            "schema_sha256": _sha(_canonical(input_schema)),
        },
        "output-schema.json": schema,
        "provenance-spec.json": {
            "source_text": "exact contiguous visible-text span within cited adjacent block IDs and one source field",
            "source_field": "server-derived from referenced source blocks",
            "source_order": "server-derived source offsets; never provider-authored",
            "unknown_block_id": "invalid output; no repair",
            "invalid_span": "invalid output; no fuzzy match or repair",
            "normalized_statement": "exact source span except optional terminal punctuation",
            "validation_status": "UNVALIDATED",
        },
        "matching-spec.json": {
            "version": "exact-visible-span-v1",
            "statement_identity": ["source_field", "source_text exact"],
            "duplicate_resolution": "multiset occurrence order; source field rank, start/end offsets, output index; gold source_order then statement_id",
            "one_to_one": True,
            "field_agreement_required": True,
            "fuzzy_matching": False,
            "semantic_similarity": False,
            "under_split": "unmatched gold span contained in an unmatched prediction span in same source field",
            "over_split": "unmatched prediction span contained in an unmatched gold span in same source field",
            "signal_text_scoring": "exact/null classification on matched items; no fuzzy scoring",
            "tie_break": "stable source field rank, offsets, output index, gold source_order and statement_id",
        },
        "metrics-spec.json": {
            "version": "jd-breakdown-metrics-v1",
            "primary": [
                "statement_f1",
                "case_exact_decomposition_rate",
                "statement_type_macro_f1",
                "capability_relevance_macro_f1",
                "valid_source_span_rate",
            ],
            "statement_counts": "exact source_field + source_text one-to-one matches",
            "precision": "exact matched predictions / predicted statement count; empty/empty=1",
            "recall": "exact matched gold / gold statement count; empty/empty=1",
            "f1": "harmonic mean; zero when precision+recall=0",
            "classification": "accuracy, macro-F1 over complete frozen enum set, per-class precision/recall/F1, confusion matrix on exact matched spans only",
            "case_exact": "same statement count and all gold statements matched exactly",
            "provenance_validity": "validated statements / raw provider statements; no raw statements gives 0",
            "slices": ["domain", "language_profile", "difficulty", "boundary_tags"],
            "provider_errors": "execution failures, not semantic predictions",
            "operational": [
                "provider_calls",
                "retries",
                "errors",
                "refusals",
                "incomplete",
                "schema_errors",
                "latency_ms_total_mean_p50_p95",
                "input_output_total_tokens",
                "observed_model_identities",
            ],
            "cost": "not calculated without approved pinned pricing",
        },
        "runner-spec.json": {
            "version": "jd-breakdown-openai-luna-runner-v1",
            "execution": "single sequential pass over all 40 cases; no semantic result inspection until terminal records exist for all cases",
            "resume": "new unique run only; never append to or overwrite prior run",
            "concurrency": 1,
            "call_cap": nonempty * (settings.vllm_max_retries + 1),
            "empty_source": "zero calls; completed empty result",
            "model_drift": "stop immediately before next case; no mixed-model run accepted",
            "report_recomputation": "offline only; no provider construction/calls",
            "results": "append-only per-case JSONL; typed structured result hash; no full SDK response persistence",
        },
    }


def _component_hashes() -> dict[str, str]:
    hashes = {
        name: _sha((BACKEND / relative).read_bytes()) for name, relative in COMPONENT_FILES.items()
    }
    hashes.update({name: _sha((LUNA_EVAL / name).read_bytes()) for name in SPEC_FILES})
    return hashes


def freeze_luna(settings: Settings, *, create: bool) -> dict[str, Any]:
    _validate_settings(settings)
    source = verify_source_eval00()
    if create:
        if LUNA_EVAL.exists():
            raise FileExistsError(
                "OpenAI Luna freeze directory already exists; immutable freeze will not be overwritten"
            )
        LUNA_EVAL.mkdir(parents=True)
        specs = _artifact_specs(settings)
        for name, value in specs.items():
            _write_json(LUNA_EVAL / name, value)
    else:
        specs = {
            name: json.loads((LUNA_EVAL / name).read_text(encoding="utf-8")) for name in SPEC_FILES
        }
    component_hashes = _component_hashes()
    extractor_hash = _sha(_canonical(component_hashes))
    spec = specs["extractor-spec.json"]
    assert isinstance(spec, dict)
    provider_spec_hash = openai_luna_spec_fingerprint(
        privacy_policy_identity=f"{settings.privacy_policy_version}:RESTRICTED:external_restricted_data_approved",
        source_adapter_identity=component_hashes["source_adapter"],
    )
    projection_hash = component_hashes["provider-projection-spec.json"]
    if create:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=BACKEND, check=True, capture_output=True, text=True
        ).stdout.strip()
        freeze = {
            "milestone": "PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-01",
            "freeze_version": 1,
            "frozen_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "code_head": head,
            "source_worktree": "Core-AI-jd-breakdown-01",
            "source_worktree_dirty_at_freeze": True,
            "dataset_id": "pai-jd-requirement-breakdown-synthetic",
            "dataset_version": "requirement-breakdown-eval-00-v1",
            "dataset_sha256": "sha256:" + source["manifest"]["hashes"]["dataset_jsonl_sha256"],
            "semantic_fingerprint": "sha256:"
            + source["manifest"]["hashes"]["semantic_fingerprint_sha256"],
            "taxonomy_sha256": "sha256:" + source["manifest"]["hashes"]["taxonomy_sha256"],
            "historical_eval00_code_head": source["manifest"]["code_head"],
            "case_count": 40,
            "gold_statement_count": 301,
            "provider_calls_before_freeze": 0,
            "provider": "openai",
            "api_family": "responses",
            "requested_model": LUNA_MODEL,
            "privacy_tier": "RESTRICTED",
            "privacy_policy_version": settings.privacy_policy_version,
            "timeout_seconds": settings.vllm_timeout_seconds,
            "maximum_attempts": settings.vllm_max_retries + 1,
            "retry_base_delay_seconds": settings.model_retry_base_delay_seconds,
            "hard_provider_call_cap": spec["hard_provider_call_cap"],
            "provider_spec_sha256": provider_spec_hash,
            "provider_projection_sha256": projection_hash,
            "extractor_spec_sha256": extractor_hash,
            "component_sha256": component_hashes,
            "target_definitions_sha256": "not applicable to JD taxonomy; EVAL-00 taxonomy hash is pinned",
            "primary_metrics": spec["primary_metrics"],
            "production_change": False,
            "provider_fallback": None,
        }
        _write_json(FREEZE_MANIFEST, freeze)
    else:
        freeze = json.loads(FREEZE_MANIFEST.read_text(encoding="utf-8"))
        if freeze.get("component_sha256") != component_hashes:
            raise ValueError("OpenAI Luna freeze component hash mismatch")
        if freeze.get("extractor_spec_sha256") != extractor_hash:
            raise ValueError("OpenAI Luna extractor spec hash mismatch")
        if freeze.get("provider_spec_sha256") != provider_spec_hash:
            raise ValueError("OpenAI Luna provider spec hash mismatch")
        if freeze.get("provider_projection_sha256") != projection_hash:
            raise ValueError("OpenAI Luna provider projection hash mismatch")
        if (
            freeze.get("code_head")
            != subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=BACKEND,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        ):
            raise ValueError("OpenAI Luna code HEAD differs from freeze")
        if freeze.get("provider_calls_before_freeze") != 0:
            raise ValueError("OpenAI Luna freeze provider_calls_before_freeze must equal zero")
        if (
            freeze.get("dataset_sha256")
            != "sha256:" + source["manifest"]["hashes"]["dataset_jsonl_sha256"]
        ):
            raise ValueError("OpenAI Luna dataset hash differs from EVAL-00")
        if (
            freeze.get("semantic_fingerprint")
            != "sha256:" + source["manifest"]["hashes"]["semantic_fingerprint_sha256"]
        ):
            raise ValueError("OpenAI Luna semantic fingerprint differs from EVAL-00")
    freeze["freeze_manifest_sha256"] = _sha(FREEZE_MANIFEST.read_bytes())
    cases = _load_cases()
    input_fingerprints: dict[str, str] = {}
    for case in cases:
        case_id = str(case["case_id"])
        projection = provider_input(build_source_blocks(case.get("target_job_source"))).model_dump(
            mode="json"
        )
        input_fingerprints[case_id] = _sha(
            _canonical(
                {
                    "provider_input": projection,
                    "extractor_spec_sha256": extractor_hash,
                    "source_adapter_sha256": component_hashes["source_adapter"],
                }
            )
        )
    freeze["input_fingerprint_by_case"] = input_fingerprints
    return freeze


def verify_luna_freeze(settings: Settings) -> dict[str, Any]:
    return freeze_luna(settings, create=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = freeze_luna(Settings(_env_file=args.env_file), create=args.freeze)
    print(
        json.dumps(
            {
                "valid": True,
                "created": args.freeze,
                "freeze_manifest_sha256": result["freeze_manifest_sha256"],
                "extractor_spec_sha256": result["extractor_spec_sha256"],
                "dataset_sha256": result["dataset_sha256"],
                "case_count": result["case_count"],
                "gold_statement_count": result["gold_statement_count"],
                "provider_calls_before_freeze": result["provider_calls_before_freeze"],
                "hard_provider_call_cap": result["hard_provider_call_cap"],
                "provider": result["provider"],
                "requested_model": result["requested_model"],
                "provider_spec_sha256": result["provider_spec_sha256"],
                "primary_metrics": result["primary_metrics"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
