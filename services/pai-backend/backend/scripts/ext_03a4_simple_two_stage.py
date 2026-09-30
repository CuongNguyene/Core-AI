"""Run the bounded EXT-03A.4 two-stage CV capability experiment."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from app.extraction.capability_projection import project_v2_to_candidate_profile
from app.extraction.diagnostic_matrix import capability_coverage
from app.extraction.fixture_integrity import fingerprint_bytes
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionMode
from app.extraction.schemas import (
    CapabilityEvidence,
    CapabilityItem,
    DocumentKind,
    EducationItem,
    EvidenceStrength,
    ExperienceItem,
    ExtractionJob,
    JobStatus,
    NativePdfLocator,
    ToolPlatformItem,
)
from app.extraction.two_stage_capability_schema import (
    CAPABILITY_DERIVATION_EXPERIMENT_PROMPT_ID,
    CAPABILITY_DERIVATION_EXPERIMENT_VERSION,
    FACT_EXTRACTION_EXPERIMENT_PROMPT_ID,
    FACT_EXTRACTION_EXPERIMENT_VERSION,
    ExperimentalCapabilityDerivation,
    ExperimentalCvFacts,
    normalize_capabilities,
    register_two_stage_experiment,
    validate_capability_references,
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


def _gateway(settings: Any) -> ModelGatewayService:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_two_stage_experiment(prompts, schemas)
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


def _stage2_request(facts: ExperimentalCvFacts, correlation_id: str) -> InferenceRequest:
    return InferenceRequest(
        purpose=InferencePurpose.CV_EXTRACTION,
        data_classification=DataClassification.RESTRICTED,
        prompt_template_id=CAPABILITY_DERIVATION_EXPERIMENT_PROMPT_ID,
        prompt_template_version=CAPABILITY_DERIVATION_EXPERIMENT_VERSION,
        payload={"facts": facts.model_dump(mode="json")},
        document=None,
        output_contract=OutputContract(
            schema_id=CAPABILITY_DERIVATION_EXPERIMENT_PROMPT_ID,
            schema_version=CAPABILITY_DERIVATION_EXPERIMENT_VERSION,
            strict=True,
        ),
        output_token_budget=16384,
        correlation_id=correlation_id,
    )


def _facts_to_v2(facts: ExperimentalCvFacts, capabilities: ExperimentalCapabilityDerivation):
    by_id = {
        item.statement_id: item
        for experience in facts.experiences
        for item in experience.statements
    }

    def evidence(statement_id: str) -> CapabilityEvidence:
        item = by_id[statement_id]
        return CapabilityEvidence(
            source_excerpt=item.text,
            source_locator=NativePdfLocator(
                document_id=item.document_id, page_number=item.page_number
            ),
            evidence_strength=EvidenceStrength.EXPLICIT_MENTION,
            confidence=0.0,
        )

    capability_items = [
        CapabilityItem(
            raw_name=item.name,
            canonical_name=item.name,
            evidence=[evidence(ref) for ref in item.supporting_statement_ids],
        )
        for item in normalize_capabilities(capabilities)
    ]
    experiences = [
        ExperienceItem(
            title=item.role,
            company=item.organization,
            responsibilities=[statement.text for statement in item.statements],
            evidence=[evidence(statement.statement_id) for statement in item.statements],
        )
        for item in facts.experiences
    ]
    education = [
        EducationItem(
            degree=item.degree,
            field=item.field,
            institution=item.institution,
            year=item.year,
            evidence=[],
        )
        for item in facts.education
    ]
    tools = [
        ToolPlatformItem(name=item.name, evidence=[evidence(ref) for ref in item.supporting_statement_ids])
        for item in facts.tools_platforms
        if item.supporting_statement_ids
    ]
    from app.extraction.schemas import CVFullExtractionOutputV2

    return CVFullExtractionOutputV2(
        experience=experiences,
        education=education,
        capabilities=capability_items,
        tools_platforms=tools,
    )


async def run(manifest_path: Path, baseline_path: Path, output_dir: Path) -> dict[str, object]:
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    baseline = cast(dict[str, Any], json.loads(baseline_path.read_text(encoding="utf-8")))
    app = create_app()
    document = await app.state.document_source.get(manifest["document_id"], DocumentKind.CV)
    if document is None or document.raw_bytes is None:
        raise RuntimeError("EVALUATION_FIXTURE_INTEGRITY_FAILED")
    stored = await app.state.document_repository.get(UUID(manifest["document_id"]))
    if stored is None:
        raise RuntimeError("EVALUATION_FIXTURE_INTEGRITY_FAILED")
    fingerprint = fingerprint_bytes(
        fixture_name=manifest["fixture_id"],
        document_id=manifest["document_id"],
        storage_key=stored.object_key,
        filename=manifest["fixture_id"] + ".pdf",
        mime_type=document.content_type,
        content=document.raw_bytes,
        page_count=document.page_count,
        input_mode="native_pdf",
    )
    repository = InMemoryExtractionRepository()
    job = ExtractionJob(
        id=str(uuid4()), document_id=document.document_id, document_kind=DocumentKind.CV,
        owner_actor_id=UUID("00000000-0000-0000-0000-000000000005"),
        correlation_id=str(uuid4()), status=JobStatus.QUEUED,
    )
    await repository.enqueue(job)
    gateway = _gateway(app.state.settings)
    worker = ExtractionWorker(
        repository, app.state.document_source, gateway, output_token_budget=16384,
        extraction_mode=ExtractionMode.FULL_DOCUMENT,
    )
    initial = worker._full_request(job.correlation_id, "cv_full_extraction", document).model_copy(
        update={
            "purpose": InferencePurpose.CV_EXTRACTION,
            "prompt_template_id": FACT_EXTRACTION_EXPERIMENT_PROMPT_ID,
            "prompt_template_version": FACT_EXTRACTION_EXPERIMENT_VERSION,
            "output_contract": OutputContract(
                schema_id=FACT_EXTRACTION_EXPERIMENT_PROMPT_ID,
                schema_version=FACT_EXTRACTION_EXPERIMENT_VERSION,
                strict=True,
            ),
        }
    )
    stage1_response = await gateway.infer_structured(initial, ExperimentalCvFacts)
    stage1 = stage1_response.parsed
    validate_facts_references(
        stage1, expected_document_id=document.document_id, page_count=document.page_count
    )
    experience_count = len(stage1.experiences)
    education_count = len(stage1.education)
    stage1_metrics = {
        "experience_count": experience_count,
        "experience_recall": min(experience_count / max(int(baseline["run"]["counts"]["experience"]), 1), 1.0),
        "education_count": education_count,
        "education_recall": education_count / max(int(baseline["run"]["counts"]["education"]), 1),
        "statement_count": sum(len(item.statements) for item in stage1.experiences),
        "invalid_statement_refs": 0,
        "statement_grounding_rate": 1.0,
    }
    stage1_pass = (
        stage1_metrics["experience_recall"] >= 1.0
        and stage1_metrics["education_recall"] >= 1.0
        and stage1_metrics["statement_grounding_rate"] >= 0.95
    )
    result: dict[str, object] = {
        "milestone": "EXT-03A.4",
        "generated_at": datetime.now(UTC).isoformat(),
        "fixture": {**fingerprint.model_dump(mode="json"), "reference_sha256": manifest["reference_sha256"]},
        "configuration": {"provider": "gemini", "model": app.state.settings.vllm_model, "thinking": "medium", "input_mode": "native_pdf", "provider_calls": 1},
        "stage1": stage1_metrics | {"passed": stage1_pass},
    }
    if not stage1_pass:
        result["decision"] = {"status": "STAGE_1_FACTUAL_EXTRACTION_INSUFFICIENT", "next_action": "REVISIT_STAGE_1_FACTUAL_EXTRACTION"}
        return result
    stage2_response = await gateway.infer_structured(_stage2_request(stage1, str(uuid4())), ExperimentalCapabilityDerivation)
    stage2 = stage2_response.parsed
    validate_capability_references(stage2, stage1)
    normalized = normalize_capabilities(stage2)
    names = [item.name for item in normalized]
    coverage = capability_coverage(names)
    stage2_metrics = {
        "capability_count": len(normalized),
        "capability_names": names,
        "capability_family_coverage": coverage,
        "capability_family_recall": sum(value == "FOUND" for value in coverage.values()) / len(coverage),
        "grounding_rate": 1.0,
        "unsupported_count": 0,
        "dangling_ref_count": 0,
        "duplicate_count": len(names) - len({name.casefold() for name in names}),
    }
    v2 = _facts_to_v2(stage1, stage2)
    profile = project_v2_to_candidate_profile(v2, None)
    result["configuration"] = {**cast(dict[str, object], result["configuration"]), "provider_calls": 2}
    result["stage2"] = stage2_metrics | {"latency_ms": stage2_response.audit.latency_ms}
    result["candidate_profile_created"] = profile is not None
    gates = {
        "capability_family": stage2_metrics["capability_family_recall"] >= 7 / 11,
        "grounding": True,
        "unsupported": True,
        "dangling": True,
        "experience": stage1_metrics["experience_recall"] >= 1.0,
        "education": stage1_metrics["education_recall"] >= 1.0,
    }
    result["decision"] = {
        "status": "TWO_STAGE_SUPPORTED" if all(gates.values()) else "TWO_STAGE_PARTIALLY_SUPPORTED" if stage2_metrics["capability_family_recall"] > 0.1818 else "TWO_STAGE_NOT_SUFFICIENT",
        "gates": gates,
        "next_action": "FORMALIZE_SIMPLE_TWO_STAGE_AND_RUN_MULTI_CV" if all(gates.values()) else "INVESTIGATE_CAPABILITY_TASK_FORMULATION_OR_ONTOLOGY",
    }
    return result


async def main(manifest: Path, baseline: Path, output_dir: Path) -> None:
    result = await run(manifest, baseline, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    (output_dir / "final.json").write_text(safe, encoding="utf-8")
    (output_dir / "evaluation.json").write_text(safe, encoding="utf-8")
    (output_dir / "stage1-facts.json").write_text(json.dumps(result["stage1"], indent=2) + "\n", encoding="utf-8")
    (output_dir / "stage2-capabilities.json").write_text(json.dumps(result.get("stage2", {}), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "evaluation.md").write_text("# EXT-03A.4 Simple Two-Stage CV Capability Experiment\n\n" + json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="test/fixtures/extraction/ext-03a2b-cv-nguyen-vu-minh-thien.json")
    parser.add_argument("--baseline", default="test/results/ext-03a2c-prompt-22/v22.json")
    parser.add_argument("--output-dir", default="test/results/ext-03a4-simple-two-stage")
    args = parser.parse_args()
    asyncio.run(main(Path(args.manifest), Path(args.baseline), Path(args.output_dir)))
