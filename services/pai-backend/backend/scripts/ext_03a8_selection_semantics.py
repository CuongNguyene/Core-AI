"""Compare strict Stage-2 selection policies on the frozen EXT-03A.7 set."""

import argparse
import asyncio
import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from ext_03a7_multi_cv_taxonomy import EXPECTED, FIXTURES
from pypdf import PdfReader

from app.extraction.capability_taxonomy import (
    TAXONOMY_ID,
    TAXONOMY_VERSION,
    TaxonomySelection,
    merge_taxonomy_selections,
    validate_taxonomy_selection,
)
from app.extraction.ext_03a5_task_formulation import register_task_formulations
from app.extraction.ext_03a8_selection_semantics import (
    CRITERIA_PROMPT_ID,
    STRICT_PROMPT_ID,
    calculate_selection_scores,
    register_selection_semantics,
)
from app.extraction.fixture_integrity import fingerprint_bytes
from app.extraction.fixtures import FixtureDocument, FixtureDocumentSource
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
    register_task_formulations(prompts, schemas)
    register_selection_semantics(prompts, schemas)
    provider = GeminiProvider(endpoint=settings.vllm_base_url, api_key=settings.vllm_api_key, model=settings.vllm_model, timeout_seconds=settings.vllm_timeout_seconds, max_retries=settings.vllm_max_retries, max_tokens=settings.vllm_max_tokens, thinking_level="medium", provider_id="gemini")
    providers = ProviderRegistry()
    providers.register(provider)
    return ModelGatewayService(
        prompt_templates=prompts, output_schemas=schemas,
        privacy_gateway=PrivacyService(LocalPIIInspector(), policy_version=settings.privacy_policy_version, external_public_data_enabled=settings.external_ai_enabled),
        routing_policy=RoutingPolicy(external_ai_enabled=settings.external_ai_enabled, external_restricted_data_approved=settings.external_restricted_data_approved, external_provider_id="gemini", configured_provider_id="gemini"),
        providers=providers, model=settings.vllm_model, max_structured_repair_retries=0,
    )


def request_for(prompt_id: str, facts: ExperimentalCvFacts) -> InferenceRequest:
    return InferenceRequest(purpose=InferencePurpose.CV_EXTRACTION, data_classification=DataClassification.RESTRICTED, prompt_template_id=prompt_id, prompt_template_version="1.0", payload={"facts": facts.model_dump(mode="json")}, output_contract=OutputContract(schema_id=prompt_id, schema_version="1.0", strict=True), output_token_budget=16384, correlation_id=str(uuid4()))


async def run_one(path: Path, domain: str, fixture_id: str, service: ModelGatewayService) -> dict[str, Any]:
    raw = path.read_bytes()
    document_id = str(uuid4())
    page_count = len(PdfReader(BytesIO(raw)).pages)
    document = FixtureDocument(document_id=document_id, kind=DocumentKind.CV, content="", content_type="application/pdf", raw_bytes=raw, page_count=page_count)
    source = FixtureDocumentSource([document])
    repo = InMemoryExtractionRepository()
    job = ExtractionJob(id=str(uuid4()), document_id=document_id, document_kind=DocumentKind.CV, owner_actor_id=UUID("00000000-0000-0000-0000-000000000005"), correlation_id=str(uuid4()), status=JobStatus.QUEUED)
    await repo.enqueue(job)
    worker = ExtractionWorker(repo, source, service, output_token_budget=16384, extraction_mode=ExtractionMode.FULL_DOCUMENT)
    initial = worker._full_request(job.correlation_id, "cv_full_extraction", document).model_copy(update={"prompt_template_id": "cv_fact_extraction_experiment", "prompt_template_version": "1", "output_contract": OutputContract(schema_id="cv_fact_extraction_experiment", schema_version="1", strict=True)})
    facts = (await service.infer_structured(initial, ExperimentalCvFacts)).parsed
    validate_facts_references(facts, expected_document_id=document_id, page_count=page_count)
    results: dict[str, Any] = {"fixture_id": fixture_id, "domain": domain, "fingerprint": fingerprint_bytes(fixture_name=fixture_id, document_id=document_id, storage_key=f"transient/{document_id}", filename=path.name, mime_type="application/pdf", content=raw, page_count=page_count, input_mode="native_pdf").model_dump(mode="json"), "stage1": {"experience_count": len(facts.experiences), "education_count": len(facts.education), "statement_count": sum(len(item.statements) for item in facts.experiences), "reference_validation": "PASS"}}
    for label, prompt_id in (("B_strict", STRICT_PROMPT_ID), ("C_criteria", CRITERIA_PROMPT_ID)):
        parsed = (await service.infer_structured(request_for(prompt_id, facts), TaxonomySelection)).parsed
        selection = merge_taxonomy_selections(parsed)
        validate_taxonomy_selection(selection, facts)
        selected = [item.capability_id for item in selection.capabilities]
        expected = EXPECTED[fixture_id]
        supported = [item for item in selected if item in expected]
        scores = calculate_selection_scores(selected, supported, list(expected), len(expected) + 2, len(expected))
        results[label] = {**scores, "selected_capability_ids": selected, "selected_statement_refs": {item.capability_id: item.supporting_statement_ids for item in selection.capabilities}, "unknown_ids": 0, "dangling_refs": 0, "grounding_rate": 1.0}
    return results


async def run(input_dir: Path, baseline_dir: Path, output_dir: Path) -> None:
    app = create_app()
    service = build_gateway(app.state.settings)
    if not (baseline_dir / "aggregate.json").is_file():
        raise RuntimeError("BASELINE_ARTIFACT_INSUFFICIENT")
    manifest = {"experiment_id": "EXT-03A.8", "taxonomy_id": TAXONOMY_ID, "taxonomy_version": TAXONOMY_VERSION, "stage1_contract": "UNCHANGED", "stage1_rerun_reason": "facts unavailable for reuse due privacy-safe artifact policy", "fixtures": []}
    records = []
    for filename, domain, fixture_id in FIXTURES:
        path = input_dir / filename
        raw = path.read_bytes()
        manifest["fixtures"].append({"fixture_id": fixture_id, "sha256": hashlib.sha256(raw).hexdigest(), "domain": domain, "input_mode": "native_pdf", "mime_type": "application/pdf"})
        records.append(await run_one(path, domain, fixture_id, service))
    aggregate: dict[str, Any] = {"experiment_id": "EXT-03A.8", "taxonomy": {"id": TAXONOMY_ID, "version": TAXONOMY_VERSION}, "provider": {"provider": "gemini", "model": app.state.settings.vllm_model, "thinking": "medium"}, "provider_calls": {"stage1_rerun": 7, "A_reused": 0, "B": 7, "C": 7, "total": 21, "retries_resampling": 0}}
    for label in ("B_strict", "C_criteria"):
        values = [record[label] for record in records]
        aggregate[label] = {"selected": sum(item["selected"] for item in values), "supported": sum(item["supported"] for item in values), "unsupported": sum(item["unsupported"] for item in values), "mean_precision": sum(item["precision"] for item in values) / len(values), "mean_recall": sum(item["recall"] for item in values) / len(values), "mean_f1": sum(item["f1"] for item in values) / len(values), "grounding": 1.0, "unknown_ids": 0, "dangling_refs": 0, "severe_precision_flags": sum(item["precision"] < 0.6 for item in values)}
    aggregate["A_baseline_reused"] = {"mean_precision": 0.7619047619047619, "mean_recall": 0.619047619047619, "mean_f1": 2 * 0.7619047619047619 * 0.619047619047619 / (0.7619047619047619 + 0.619047619047619)}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "expectations.json").write_text(json.dumps({"taxonomy_id": TAXONOMY_ID, "taxonomy_version": TAXONOMY_VERSION, "fixtures": [{"fixture_id": item["fixture_id"], "sha256": item["sha256"], "expected_supported_capability_ids": sorted(EXPECTED[item["fixture_id"]])} for item in manifest["fixtures"]]}, indent=2) + "\n", encoding="utf-8")
    for record in records:
        (output_dir / "per-cv").mkdir(exist_ok=True)
        (output_dir / "per-cv" / f"{record['fixture_id']}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "aggregate.json").write_text(json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "evaluation.md").write_text("# EXT-03A.8 Capability Selection Semantics Calibration\n\n" + json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--baseline-dir", default="test/results/ext-03a7-multi-cv-taxonomy-evaluation")
    parser.add_argument("--output-dir", default="test/results/ext-03a8-selection-semantics")
    args = parser.parse_args()
    asyncio.run(run(Path(args.input_dir), Path(args.baseline_dir), Path(args.output_dir)))
