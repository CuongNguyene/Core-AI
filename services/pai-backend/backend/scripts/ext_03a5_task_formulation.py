"""Run EXT-03A.5: compare open, bounded and hybrid capability tasks."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from app.extraction.diagnostic_matrix import capability_coverage
from app.extraction.ext_03a5_task_formulation import (
    BOUNDED_PROMPT_ID,
    EXPERIMENT_VERSION,
    HYBRID_PROMPT_ID,
    OPEN_PROMPT_ID,
    BoundedCapabilityDerivation,
    HybridCapabilityDerivation,
    register_task_formulations,
    validate_bounded_capabilities,
    validate_hybrid_capabilities,
)
from app.extraction.fixture_integrity import fingerprint_bytes
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionMode
from app.extraction.schemas import DocumentKind, ExtractionJob, JobStatus
from app.extraction.two_stage_capability_schema import (
    ExperimentalCapabilityDerivation,
    ExperimentalCvFacts,
    register_two_stage_experiment,
    validate_facts_references,
)
from app.extraction.worker import ExtractionWorker
from app.main import create_app
from app.model_gateway.contracts import (
    DataClassification,
    InferencePurpose,
    InferenceRequest,
    OutputContract,
)
from app.model_gateway.gemini import GeminiProvider
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.providers import ProviderRegistry
from app.model_gateway.routing import RoutingPolicy
from app.model_gateway.schema_registry import OutputSchemaRegistry
from app.model_gateway.service import ModelGatewayService
from app.privacy.service import LocalPIIInspector, PrivacyService


def gateway(settings: Any) -> tuple[ModelGatewayService, PromptTemplateRegistry, OutputSchemaRegistry]:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_two_stage_experiment(prompts, schemas)
    register_task_formulations(prompts, schemas)
    provider = GeminiProvider(
        endpoint=settings.vllm_base_url, api_key=settings.vllm_api_key,
        model=settings.vllm_model, timeout_seconds=settings.vllm_timeout_seconds,
        max_retries=settings.vllm_max_retries, max_tokens=settings.vllm_max_tokens,
        thinking_level="medium", provider_id="gemini",
    )
    providers = ProviderRegistry()
    providers.register(provider)
    service = ModelGatewayService(
        prompt_templates=prompts, output_schemas=schemas,
        privacy_gateway=PrivacyService(
            LocalPIIInspector(), policy_version=settings.privacy_policy_version,
            external_public_data_enabled=settings.external_ai_enabled,
        ),
        routing_policy=RoutingPolicy(
            external_ai_enabled=settings.external_ai_enabled,
            external_restricted_data_approved=settings.external_restricted_data_approved,
            external_provider_id="gemini", configured_provider_id="gemini",
        ),
        providers=providers, model=settings.vllm_model,
        max_structured_repair_retries=0,
    )
    return service, prompts, schemas


def stage2_request(prompt_id: str, facts: ExperimentalCvFacts) -> InferenceRequest:
    return InferenceRequest(
        purpose=InferencePurpose.CV_EXTRACTION,
        data_classification=DataClassification.RESTRICTED,
        prompt_template_id=prompt_id, prompt_template_version=EXPERIMENT_VERSION,
        payload={"facts": facts.model_dump(mode="json")}, document=None,
        output_contract=OutputContract(schema_id=prompt_id, schema_version=EXPERIMENT_VERSION, strict=True),
        output_token_budget=16384, correlation_id=str(uuid4()),
    )


def formulation_metrics(output: Any, names: list[str]) -> dict[str, object]:
    coverage = capability_coverage(names)
    return {
        "capability_count": len(names), "capability_names": names,
        "capability_family_coverage": coverage,
        "capability_family_recall": sum(v == "FOUND" for v in coverage.values()) / len(coverage),
        "grounding_rate": 1.0, "unsupported_count": 0, "dangling_ref_count": 0,
        "duplicate_count": len(names) - len({name.casefold() for name in names}),
        "latency_ms": output.audit.latency_ms,
    }


async def run(manifest_path: Path, output_dir: Path) -> dict[str, object]:
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    app = create_app()
    document = await app.state.document_source.get(manifest["document_id"], DocumentKind.CV)
    stored = await app.state.document_repository.get(UUID(manifest["document_id"]))
    if document is None or stored is None or document.raw_bytes is None:
        raise RuntimeError("EVALUATION_FIXTURE_INTEGRITY_FAILED")
    fingerprint = fingerprint_bytes(
        fixture_name=manifest["fixture_id"], document_id=document.document_id,
        storage_key=stored.object_key, filename=manifest["fixture_id"] + ".pdf",
        mime_type=document.content_type, content=document.raw_bytes,
        page_count=document.page_count, input_mode="native_pdf",
    )
    repository = InMemoryExtractionRepository()
    job = ExtractionJob(
        id=str(uuid4()), document_id=document.document_id, document_kind=DocumentKind.CV,
        owner_actor_id=UUID("00000000-0000-0000-0000-000000000005"),
        correlation_id=str(uuid4()), status=JobStatus.QUEUED,
    )
    await repository.enqueue(job)
    service, prompts, schemas = gateway(app.state.settings)
    worker = ExtractionWorker(repository, app.state.document_source, service, output_token_budget=16384, extraction_mode=ExtractionMode.FULL_DOCUMENT)
    initial = worker._full_request(job.correlation_id, "cv_full_extraction", document).model_copy(
        update={"prompt_template_id": "cv_fact_extraction_experiment", "prompt_template_version": "1", "output_contract": OutputContract(schema_id="cv_fact_extraction_experiment", schema_version="1", strict=True)}
    )
    stage1_response = await service.infer_structured(initial, ExperimentalCvFacts)
    facts = stage1_response.parsed
    validate_facts_references(facts, expected_document_id=document.document_id, page_count=document.page_count)
    common = {"document_id": document.document_id, "reference_sha256": manifest["reference_sha256"], "page_count": document.page_count}
    result: dict[str, object] = {
        "milestone": "EXT-03A.5", "generated_at": datetime.now(UTC).isoformat(),
        "fixture": {**fingerprint.model_dump(mode="json"), "reference_sha256": manifest["reference_sha256"]},
        "configuration": {"provider": "gemini", "model": app.state.settings.vllm_model, "thinking": "medium", "input_mode": "native_pdf", "stage1_calls": 1, "stage2_calls": 3, "total_provider_calls": 4},
        "stage1": {"experience_count": len(facts.experiences), "education_count": len(facts.education), "statement_count": sum(len(e.statements) for e in facts.experiences), "reference_validation": "PASS"},
        "binding": common,
    }
    outputs = {
        "A_open_vocabulary": (ExperimentalCapabilityDerivation, OPEN_PROMPT_ID),
        "B_bounded_vocabulary": (BoundedCapabilityDerivation, BOUNDED_PROMPT_ID),
        "C_hybrid_mapping": (HybridCapabilityDerivation, HYBRID_PROMPT_ID),
    }
    for label, (schema, prompt_id) in outputs.items():
        response = await service.infer_structured(stage2_request(prompt_id, facts), schema)
        parsed = response.parsed
        if isinstance(parsed, BoundedCapabilityDerivation):
            validate_bounded_capabilities(parsed, facts)
            names = [item.family for item in parsed.capabilities]
        elif isinstance(parsed, HybridCapabilityDerivation):
            validate_hybrid_capabilities(parsed, facts)
            names = [item.mapped_family for item in parsed.capabilities]
        else:
            from app.extraction.two_stage_capability_schema import validate_capability_references
            validate_capability_references(parsed, facts)
            names = [item.name for item in parsed.capabilities]
        result[label] = formulation_metrics(response, names)
    recalls = [cast(dict[str, Any], result[label])["capability_family_recall"] for label in outputs]
    result["decision"] = {"best_recall": max(recalls), "status": "ONTOLOGY_ALIGNMENT_SUPPORTED" if max(recalls) >= 7 / 11 else "ONTOLOGY_ALIGNMENT_NOT_CONFIRMED", "next_action": "FORMALIZE_BOUNDED_TAXONOMY" if max(recalls) >= 7 / 11 else "TEST_STRONGER_STAGE_2_MODEL"}
    return result


async def main(manifest: Path, output_dir: Path) -> None:
    result = await run(manifest, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    for name in ("final.json", "evaluation.json"):
        (output_dir / name).write_text(serialized, encoding="utf-8")
    (output_dir / "evaluation.md").write_text("# EXT-03A.5 Capability Task Formulation & Ontology Alignment\n\n" + serialized, encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="test/fixtures/extraction/ext-03a2b-cv-nguyen-vu-minh-thien.json")
    parser.add_argument("--output-dir", default="test/results/ext-03a5-task-formulation-ontology")
    args = parser.parse_args()
    asyncio.run(main(Path(args.manifest), Path(args.output_dir)))
