"""Run the bounded EXT-03A.1 native/text x high/medium matrix."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.extraction.capability_projection import aggregate_capabilities
from app.extraction.diagnostic_matrix import (
    InputMode,
    MatrixRun,
    MatrixTokenUsage,
    ThinkingLevel,
    capability_coverage,
    classify_experience_recall,
    duplicate_count,
    education_recall,
    matrix_markdown,
    recommend,
)
from app.extraction.fixtures import FixtureDocument
from app.extraction.prompts import (
    FULL_EXTRACTION_SCHEMA_V2_VERSION,
    register_extraction_contracts,
)
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionInputMode, ExtractionMode
from app.extraction.schemas import CVFullExtractionOutputV2, DocumentKind, ExtractionJob, JobStatus
from app.extraction.worker import ExtractionWorker
from app.main import create_app
from app.model_gateway.gemini import GeminiProvider
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.providers import ProviderRegistry
from app.model_gateway.routing import RoutingPolicy
from app.model_gateway.schema_registry import OutputSchemaRegistry
from app.model_gateway.service import ModelGatewayService
from app.privacy.service import LocalPIIInspector, PrivacyService


def _gateway(settings: Any, thinking: str) -> ModelGatewayService:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)
    provider = GeminiProvider(
        endpoint=settings.vllm_base_url,
        api_key=settings.vllm_api_key,
        model=settings.vllm_model,
        timeout_seconds=settings.vllm_timeout_seconds,
        max_retries=settings.vllm_max_retries,
        max_tokens=settings.vllm_max_tokens,
        thinking_level=thinking,
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


async def _run_cell(
    app: Any,
    source_document: FixtureDocument,
    input_mode: InputMode,
    thinking: ThinkingLevel,
    prompt_version: str = FULL_EXTRACTION_SCHEMA_V2_VERSION,
) -> MatrixRun:
    native = input_mode == ExtractionInputMode.NATIVE_PDF.value
    document = source_document if native else source_document.model_copy(
        update={"content_type": None, "raw_bytes": None}
    )
    repository = InMemoryExtractionRepository()
    job = ExtractionJob(
        id=str(uuid4()),
        document_id=source_document.document_id,
        document_kind=DocumentKind.CV,
        owner_actor_id=UUID("00000000-0000-0000-0000-000000000005"),
        correlation_id=str(uuid4()),
        status=JobStatus.QUEUED,
    )
    await repository.enqueue(job)
    class SingleDocumentSource:
        async def get(self, _document_id: str, _kind: DocumentKind) -> FixtureDocument:
            return document

    worker = ExtractionWorker(
        repository,
        SingleDocumentSource(),
        _gateway(app.state.settings, thinking),
        output_token_budget=65536,
        extraction_mode=ExtractionMode.FULL_DOCUMENT,
        full_prompt_version=prompt_version,
    )
    await worker.run_once()
    completed = await repository.get_job(job.id)
    profile = await repository.get_profile(completed.profile_id or "") if completed else None
    if completed is None or completed.status is not JobStatus.SUCCEEDED or profile is None:
        details = completed.error_details if completed else None
        return MatrixRun(
            run_id=job.id,
            input_mode=input_mode,
            thinking=thinking,
            provider="gemini",
            model=app.state.settings.vllm_model,
            prompt_id="cv_full_extraction",
            prompt_version=prompt_version,
            success=False,
            failure_stage=str(details.get("failure_stage")) if details else None,
            failure_code=str(details.get("failure_code")) if details else completed.error_category if completed else "job_missing",
            latency_ms=0,
            token_usage=MatrixTokenUsage(),
            counts={},
            quality={},
        )

    if not isinstance(profile.output, CVFullExtractionOutputV2):
        return MatrixRun(
            run_id=job.id,
            input_mode=input_mode,
            thinking=thinking,
            provider="gemini",
            model=app.state.settings.vllm_model,
            prompt_id="cv_full_extraction",
            prompt_version=prompt_version,
            success=False,
            failure_stage="schema_validation",
            failure_code="unexpected_output_schema",
            latency_ms=0,
            token_usage=MatrixTokenUsage(),
            counts={},
            quality={},
        )
    output = profile.output
    capabilities = aggregate_capabilities(output.capabilities)
    names = [item.canonical_name for item in capabilities]
    audit = profile.audit
    usage = audit.get("usage") if isinstance(audit.get("usage"), dict) else {}
    input_tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
    output_tokens = usage.get("output_tokens") if isinstance(usage, dict) else None
    total = input_tokens + output_tokens if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None
    grounded = sum(bool(item.evidence) for item in capabilities)
    counts = {
        "experience": len(output.experience),
        "capabilities": len(capabilities),
        "tools_platforms": len(output.tools_platforms),
        "education": len(output.education),
    }
    return MatrixRun(
        run_id=job.id,
        input_mode=input_mode,
        thinking=thinking,
        provider="gemini",
        model=app.state.settings.vllm_model,
        prompt_id="cv_full_extraction",
        prompt_version=prompt_version,
        success=True,
        latency_ms=(
            audit["latency_ms"]
            if isinstance(audit.get("latency_ms"), int)
            else 0
        ),
        token_usage=MatrixTokenUsage(
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
            total_tokens=total,
        ),
        finish_reason=str(audit["finish_reason"]) if audit.get("finish_reason") else None,
        counts=counts,
        quality={
            "grounded_capabilities": grounded,
            "grounded_capability_rate": grounded / len(capabilities) if capabilities else 0.0,
            "unsupported_capability_count": 0,
            "duplicate_capability_count": duplicate_count(names),
        },
        capability_names=names,
        tool_names=[item.name for item in output.tools_platforms],
        education_summary=[item.degree for item in output.education],
        capability_coverage=capability_coverage(names),
        experience_recall=classify_experience_recall(len(output.experience)),
        education_recall=education_recall(len(output.education)),
        candidate_profile_created=profile.candidate_profile is not None,
    )


async def main(document_id: str, output_dir: Path) -> None:
    app = create_app()
    document = await app.state.document_source.get(document_id, DocumentKind.CV)
    runs = [
        await _run_cell(app, document, input_mode, thinking)
        for input_mode in ("native_pdf", "whole_parsed_text")
        for thinking in ("high", "medium")
    ]
    decision = recommend(runs)
    artifact = {
        "milestone": "EXT-03A.1-DIAG",
        "generated_at": datetime.now(UTC).isoformat(),
        "reference_fixture": "Nguyen Vu Minh Thien CV PDF",
        "document_id": document_id,
        "configuration": {
            "provider": "gemini",
            "model": app.state.settings.vllm_model,
            "prompt_id": "cv_full_extraction",
            "prompt_version": "2.0",
            "output_token_budget": 65536,
            "structured_repair_retries": 0,
        },
        "runs": [run.model_dump(mode="json") for run in runs],
        "decision": decision,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "matrix.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    (output_dir / "matrix.md").write_text(matrix_markdown(runs, decision), encoding="utf-8")
    print(json.dumps({"runs": [run.model_dump(mode="json") for run in runs], "decision": decision}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", required=True)
    parser.add_argument(
        "--output-dir",
        default="test/results/ext-03a1-diagnostic-matrix",
    )
    args = parser.parse_args()
    asyncio.run(main(args.document_id, Path(args.output_dir)))
