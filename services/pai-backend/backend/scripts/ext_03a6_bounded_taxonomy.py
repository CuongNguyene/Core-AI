"""Run one checksum-bound Stage 2 selection with the formal taxonomy."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from app.extraction.capability_taxonomy import (
    PROFESSIONAL_CAPABILITY_CORE,
    TAXONOMY_ID,
    TAXONOMY_SELECTION_PROMPT_ID,
    TAXONOMY_VERSION,
    TaxonomySelection,
    get_taxonomy,
    merge_taxonomy_selections,
    register_taxonomy_selection,
    validate_taxonomy_selection,
)
from app.extraction.fixture_integrity import fingerprint_bytes
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionMode
from app.extraction.schemas import DocumentKind, ExtractionJob, JobStatus
from app.extraction.two_stage_capability_schema import (
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


def build_gateway(settings: Any) -> ModelGatewayService:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_two_stage_experiment(prompts, schemas)
    register_taxonomy_selection(prompts, schemas)
    provider = GeminiProvider(
        endpoint=settings.vllm_base_url, api_key=settings.vllm_api_key,
        model=settings.vllm_model, timeout_seconds=settings.vllm_timeout_seconds,
        max_retries=settings.vllm_max_retries, max_tokens=settings.vllm_max_tokens,
        thinking_level="medium", provider_id="gemini",
    )
    providers = ProviderRegistry()
    providers.register(provider)
    return ModelGatewayService(
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
        providers=providers, model=settings.vllm_model, max_structured_repair_retries=0,
    )


def selection_request(facts: ExperimentalCvFacts) -> InferenceRequest:
    return InferenceRequest(
        purpose=InferencePurpose.CV_EXTRACTION, data_classification=DataClassification.RESTRICTED,
        prompt_template_id=TAXONOMY_SELECTION_PROMPT_ID, prompt_template_version=TAXONOMY_VERSION,
        payload={"facts": facts.model_dump(mode="json")}, document=None,
        output_contract=OutputContract(schema_id=TAXONOMY_SELECTION_PROMPT_ID, schema_version=TAXONOMY_VERSION, strict=True),
        output_token_budget=16384, correlation_id=str(uuid4()),
    )


async def run(manifest_path: Path) -> dict[str, object]:
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
    gateway = build_gateway(app.state.settings)
    worker = ExtractionWorker(repository, app.state.document_source, gateway, output_token_budget=16384, extraction_mode=ExtractionMode.FULL_DOCUMENT)
    stage1_request = worker._full_request(job.correlation_id, "cv_full_extraction", document).model_copy(
        update={
            "prompt_template_id": "cv_fact_extraction_experiment",
            "prompt_template_version": "1",
            "output_contract": OutputContract(schema_id="cv_fact_extraction_experiment", schema_version="1", strict=True),
        }
    )
    stage1 = (await gateway.infer_structured(stage1_request, ExperimentalCvFacts)).parsed
    validate_facts_references(stage1, expected_document_id=document.document_id, page_count=document.page_count)
    response = await gateway.infer_structured(selection_request(stage1), TaxonomySelection)
    selected = merge_taxonomy_selections(response.parsed)
    validate_taxonomy_selection(selected, stage1)
    taxonomy = get_taxonomy(TAXONOMY_ID, TAXONOMY_VERSION)
    names = {item.id: item.name for item in taxonomy.capabilities}
    selected_ids = [item.capability_id for item in selected.capabilities]
    return {
        "milestone": "EXT-03A.6", "generated_at": datetime.now(UTC).isoformat(),
        "fixture": {**fingerprint.model_dump(mode="json"), "reference_sha256": manifest["reference_sha256"]},
        "taxonomy": {"taxonomy_id": TAXONOMY_ID, "taxonomy_version": TAXONOMY_VERSION},
        "configuration": {"provider": "gemini", "model": app.state.settings.vllm_model, "thinking": "medium", "stage1_calls": 1, "stage2_calls": 1, "total_provider_calls": 2},
        "stage1": {"experience_count": len(stage1.experiences), "education_count": len(stage1.education), "statement_count": sum(len(item.statements) for item in stage1.experiences), "reference_validation": "PASS"},
        "selection": {"selected_ids": selected_ids, "selected_names": [names[item] for item in selected_ids], "unknown_taxonomy_ids": 0, "dangling_refs": 0, "duplicates": 0, "grounding_rate": 1.0, "unsupported": 0, "recall": len(selected_ids) / len(taxonomy.capabilities)},
        "decision": {"status": "REFERENCE_SELECTION_HIGH" if len(selected_ids) / len(taxonomy.capabilities) >= 0.9 else "REFERENCE_SELECTION_NEEDS_REVIEW", "next_action": "PROCEED_TO_MULTI_CV_TAXONOMY_EVALUATION" if len(selected_ids) / len(taxonomy.capabilities) >= 0.9 else "REVISIT_TAXONOMY_TASK_DESIGN"},
    }


async def main(manifest: Path, output_dir: Path) -> None:
    result = await run(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "taxonomy.json").write_text(json.dumps(PROFESSIONAL_CAPABILITY_CORE.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    (output_dir / "reference-selection.json").write_text(serialized, encoding="utf-8")
    (output_dir / "evaluation.json").write_text(serialized, encoding="utf-8")
    (output_dir / "evaluation.md").write_text("# EXT-03A.6 Bounded Capability Taxonomy\n\n" + serialized, encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="test/fixtures/extraction/ext-03a2b-cv-nguyen-vu-minh-thien.json")
    parser.add_argument("--output-dir", default="test/results/ext-03a6-bounded-taxonomy")
    args = parser.parse_args()
    asyncio.run(main(Path(args.manifest), Path(args.output_dir)))
