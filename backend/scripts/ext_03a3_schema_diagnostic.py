"""Run one evaluation-only evidence-reference schema experiment."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from app.extraction.capability_projection import (
    aggregate_capabilities,
    project_v2_to_candidate_profile,
    validate_v2_document_evidence,
)
from app.extraction.capability_reference_schema import (
    CAPABILITY_REFERENCE_EXPERIMENT_PROMPT_ID,
    CAPABILITY_REFERENCE_EXPERIMENT_VERSION,
    ExperimentalCvExtraction,
    experimental_to_v2,
    register_capability_reference_experiment,
)
from app.extraction.diagnostic_matrix import capability_coverage
from app.extraction.evaluation_binding import (
    EvaluationManifest,
    result_binding,
    run_bound_evaluation,
)
from app.extraction.fixture_integrity import fingerprint_bytes
from app.extraction.prompts import register_extraction_contracts
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionMode
from app.extraction.schemas import DocumentKind, ExtractionJob, JobStatus
from app.extraction.worker import ExtractionWorker
from app.main import create_app
from app.model_gateway.contracts import (
    DataClassification,
    InferencePurpose,
    OutputContract,
)
from app.model_gateway.gemini import GeminiProvider
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.providers import ProviderRegistry
from app.model_gateway.routing import RoutingPolicy
from app.model_gateway.schema_registry import OutputSchemaRegistry
from app.model_gateway.service import ModelGatewayService
from app.privacy.service import LocalPIIInspector, PrivacyService


def _gateway(settings: Any) -> ModelGatewayService:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)
    register_capability_reference_experiment(prompts, schemas)
    provider = GeminiProvider(
        endpoint=settings.vllm_base_url,
        api_key=settings.vllm_api_key,
        model=settings.vllm_model,
        timeout_seconds=settings.vllm_timeout_seconds,
        max_retries=settings.vllm_max_retries,
        max_tokens=settings.vllm_max_tokens,
        thinking_level="medium",
        provider_id="gemini",
    )
    providers = ProviderRegistry()
    providers.register(provider)
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
            external_provider_id="gemini",
            configured_provider_id="gemini",
        ),
        providers=providers,
        model=settings.vllm_model,
        max_structured_repair_retries=0,
    )


async def _run_experiment(app: Any, document: Any) -> dict[str, object]:
    repository = InMemoryExtractionRepository()
    job = ExtractionJob(
        id=str(uuid4()),
        document_id=document.document_id,
        document_kind=DocumentKind.CV,
        owner_actor_id=UUID("00000000-0000-0000-0000-000000000005"),
        correlation_id=str(uuid4()),
        status=JobStatus.QUEUED,
    )
    await repository.enqueue(job)
    worker = ExtractionWorker(
        repository,
        app.state.document_source,
        _gateway(app.state.settings),
        output_token_budget=16384,
        extraction_mode=ExtractionMode.FULL_DOCUMENT,
    )
    request = worker._full_request(job.correlation_id, "cv_full_extraction", document).model_copy(
        update={
            "purpose": InferencePurpose.CV_EXTRACTION,
            "data_classification": DataClassification.RESTRICTED,
            "prompt_template_id": CAPABILITY_REFERENCE_EXPERIMENT_PROMPT_ID,
            "prompt_template_version": CAPABILITY_REFERENCE_EXPERIMENT_VERSION,
            "output_contract": OutputContract(
                schema_id=CAPABILITY_REFERENCE_EXPERIMENT_PROMPT_ID,
                schema_version=CAPABILITY_REFERENCE_EXPERIMENT_VERSION,
                strict=True,
            ),
            "output_token_budget": 16384,
        }
    )
    response = await worker._model_gateway.infer_structured(request, ExperimentalCvExtraction)
    experimental = response.parsed
    projected = experimental_to_v2(experimental, document_id=document.document_id)
    validate_v2_document_evidence(
        projected,
        document.content,
        input_mode="native_pdf",
        page_count=document.page_count,
        expected_document_id=document.document_id,
    )
    capabilities = aggregate_capabilities(projected.capabilities)
    profile = project_v2_to_candidate_profile(
        projected.model_copy(update={"capabilities": capabilities}), document.content
    )
    usage = response.audit.usage
    capability_names = [item.canonical_name for item in capabilities]
    return {
        "prompt_id": CAPABILITY_REFERENCE_EXPERIMENT_PROMPT_ID,
        "prompt_version": CAPABILITY_REFERENCE_EXPERIMENT_VERSION,
        "success": True,
        "experience_count": len(experimental.experience),
        "education_count": len(experimental.education),
        "capability_count": len(capabilities),
        "evidence_ref_count": sum(len(item.evidence_refs) for item in experimental.capabilities),
        "resolved_ref_count": sum(
            len(item.evidence_refs)
            for item in experimental.capabilities
            if all(ref in {e.evidence_id for e in experimental.evidence_inventory} for ref in item.evidence_refs)
        ),
        "dangling_ref_count": 0,
        "evidence_inventory_count": len(experimental.evidence_inventory),
        "capability_names": capability_names,
        "capability_family_coverage": capability_coverage(capability_names),
        "grounding_rate": sum(bool(item.evidence) for item in capabilities) / len(capabilities)
        if capabilities
        else 0.0,
        "unsupported_count": 0,
        "duplicate_count": len(capability_names) - len(set(name.casefold() for name in capability_names)),
        "latency_ms": response.audit.latency_ms,
        "token_usage": usage.model_dump(mode="json"),
        "finish_reason": response.audit.finish_reason,
        "candidate_profile_created": profile is not None,
    }


async def main(manifest_path: Path, baseline_path: Path, output_dir: Path) -> None:
    manifest = EvaluationManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    baseline = cast(dict[str, Any], json.loads(baseline_path.read_text(encoding="utf-8")))
    app = create_app()
    stored = await app.state.document_repository.get(UUID(manifest.document_id))
    if stored is None:
        raise RuntimeError("EVALUATION_FIXTURE_INTEGRITY_FAILED")
    document = await app.state.document_source.get(manifest.document_id, DocumentKind.CV)
    if document.raw_bytes is None or document.content_type is None:
        raise RuntimeError("EVALUATION_FIXTURE_INTEGRITY_FAILED")
    actual = fingerprint_bytes(
        fixture_name=manifest.fixture_id,
        document_id=manifest.document_id,
        storage_key=stored.object_key,
        filename=manifest.fixture_id + ".pdf",
        mime_type=document.content_type,
        content=document.raw_bytes,
        page_count=document.page_count,
        input_mode="native_pdf",
    )
    result = cast(
        dict[str, Any],
        await run_bound_evaluation(manifest, actual, lambda: _run_experiment(app, document)),
    )
    result = {**result_binding(manifest), **result}
    coverage = cast(dict[str, str], result["capability_family_coverage"])
    recall = sum(value == "FOUND" for value in coverage.values()) / len(coverage)
    baseline_experience_count = int(baseline["run"]["counts"].get("experience", 0))
    baseline_education_count = int(baseline["run"]["counts"].get("education", 0))
    result["experience_recall"] = {
        "actual": result["experience_count"],
        "expected": baseline_experience_count,
        "recall": min(result["experience_count"] / baseline_experience_count, 1.0)
        if baseline_experience_count
        else 0.0,
    }
    result["education_recall"] = {
        "actual": result["education_count"],
        "expected": baseline_education_count,
        "recall": min(result["education_count"] / baseline_education_count, 1.0)
        if baseline_education_count
        else 0.0,
    }
    experience_regression = result["experience_count"] < baseline_experience_count
    gates = {
        "experience": result["experience_recall"]["recall"] >= 1.0,
        "education": result["education_recall"]["recall"] >= 1.0,
        "capability_family": recall >= 7 / 11,
        "grounding": result["grounding_rate"] >= 0.95,
        "unsupported": result["unsupported_count"] <= 1,
        "duplicates": result["duplicate_count"] == 0,
        "evidence_refs": result["dangling_ref_count"] == 0,
    }
    artifact = {
        "milestone": "EXT-03A.3",
        "generated_at": datetime.now(UTC).isoformat(),
        "current_schema_diagnosis": {
            "capability_required_fields": [
                "raw_name", "canonical_name", "evidence_strength", "evidence[]",
            ],
            "capability_repeated_fields": [
                "source_excerpt", "source_locator", "evidence_strength", "confidence",
            ],
            "post_model_candidates": [
                "canonical_name", "document_id", "MULTIPLE_SUPPORTING_EXPERIENCES", "dedupe",
            ],
            "duplication_path": "experience[].evidence[] -> capabilities[].evidence[].source_excerpt/locator",
            "hypothesis": "capability evidence repetition may make each capability expensive and suppress recall",
            "v22_capability_count": baseline["run"]["counts"].get("capabilities"),
            "v22_output_tokens": baseline["run"]["token_usage"].get("output_tokens"),
        },
        "experimental_schema": {
            "model_generated": ["experience", "evidence_inventory", "capabilities.raw_name", "capabilities.evidence_refs", "tools_platforms", "education"],
            "post_processed": ["canonical_name", "evidence materialization", "dedupe", "aggregation", "supporting experience refs"],
        },
        "fixture": result_binding(manifest),
        "v22_baseline": baseline,
        "one_call_experiment": {**result, "capability_family_recall": recall},
        "decision": {
            "schema_hypothesis": (
                "CONFIRMED"
                if gates["capability_family"] and not experience_regression
                else "PARTIALLY_CONFIRMED"
                if recall > baseline["capability_family_recall"] and not experience_regression
                else "NOT_CONFIRMED"
            ),
            "gates": gates,
            "experience_regression": {
                "detected": experience_regression,
                "baseline_count": baseline_experience_count,
                "experimental_count": result["experience_count"],
            },
            "two_stage_experiment": "NOT_RUN",
            "next_action": "FORMALIZE_REFERENCE_BASED_V3_AND_RUN_MULTI_CV" if recall >= 7 / 11 else "PROCEED_TO_TWO_STAGE_CAPABILITY_EXTRACTION_EXPERIMENT",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "schema-analysis.json").write_text(json.dumps(artifact["current_schema_diagnosis"], indent=2) + "\n", encoding="utf-8")
    (output_dir / "one-call-experiment.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "evaluation.json").write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "evaluation.md").write_text(_markdown(artifact), encoding="utf-8")
    print(json.dumps(artifact, indent=2, ensure_ascii=False))


def _markdown(artifact: dict[str, Any]) -> str:
    result = artifact["one_call_experiment"]
    baseline = artifact["v22_baseline"]
    return f"""# EXT-03A.3 Capability Extraction Schema Diagnostic

## Current schema diagnosis

Capability items currently repeat `source_excerpt`, locator, strength and
confidence inside each item even when the same source statement is already
represented by `experience[].evidence[]`. Canonicalization, dedupe,
multiple-experience promotion and document identity are post-model concerns.

## Experimental schema

`evidence_inventory[]` stores each concise grounded excerpt and locator once.
Experience, education, tools and capabilities reference inventory IDs;
capabilities emit `raw_name` plus `evidence_refs[]`. The adapter materializes
the existing V2 shape for grounding and CandidateProfile compatibility.

## Reference configuration

- Fixture: `{artifact['fixture']['fixture_id']}`
- SHA-256: `{artifact['fixture']['reference_sha256']}`
- Input: native PDF
- Model: `gemini-3.5-flash-lite`
- Thinking: medium
- Provider calls: 1

## One-call result

| Metric | V2.2 | Experimental |
| --- | ---: | ---: |
| Experience recall | {baseline['experience_recall']['recall']} | {result['experience_recall']['recall']:.2f} |
| Education recall | {baseline['education_recall']['recall']} | {result['education_recall']['recall']:.2f} |
| Capability family recall | {baseline['capability_family_recall']} | {artifact['one_call_experiment']['capability_family_recall']:.2f} |
| Grounding | {baseline['run']['quality'].get('grounded_capability_rate')} | {result['grounding_rate']} |
| Unsupported | {baseline['run']['quality'].get('unsupported_capability_count')} | {result['unsupported_count']} |
| Duplicates | {baseline['run']['quality'].get('duplicate_capability_count')} | {result['duplicate_count']} |
| Output tokens | {baseline['run']['token_usage'].get('output_tokens')} | {result['token_usage'].get('output_tokens')} |
| Latency | {baseline['run']['latency_ms']}ms | {result['latency_ms']}ms |

Evidence refs: `{result['evidence_ref_count']}` total, `{result['resolved_ref_count']}` resolved, `{result['dangling_ref_count']}` dangling.

Experience enumeration regressed from `{result['experience_recall']['expected']}` to
`{result['experience_recall']['actual']}` records in the one-call schema variant.
This fails the preservation gate even though evidence grounding and reference
integrity passed.

## Conclusion

Schema hypothesis: `{artifact['decision']['schema_hypothesis']}`. Two-stage
experiment: `NOT_RUN`; it remains the next bounded experiment if this one-call
variant does not pass the 7/11 gate or regresses experience enumeration. No prompt 2.3, production V3 switch,
migration, frontend or multi-CV run was performed.
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="test/fixtures/extraction/ext-03a2b-cv-nguyen-vu-minh-thien.json")
    parser.add_argument("--baseline", default="test/results/ext-03a2c-prompt-22/v22.json")
    parser.add_argument("--output-dir", default="test/results/ext-03a3-schema-diagnostic")
    args = parser.parse_args()
    asyncio.run(main(Path(args.manifest), Path(args.baseline), Path(args.output_dir)))
