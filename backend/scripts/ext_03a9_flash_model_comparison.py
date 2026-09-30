"""Compare the locked EXT-03A.8 Stage-2 formulation across Flash models."""

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
    get_taxonomy,
    merge_taxonomy_selections,
    validate_taxonomy_selection,
)
from app.extraction.ext_03a8_selection_semantics import (
    CRITERIA_PROMPT_ID,
    STRICT_CRITERIA,
    register_selection_semantics,
)
from app.extraction.ext_03a9_flash_model_comparison import (
    FLASH_MODELS,
    build_comparison_manifest,
    choose_flash_candidate,
    compare_model_metrics,
    model_endpoint,
    validate_comparison_inputs,
)
from app.extraction.fixture_integrity import fingerprint_bytes
from app.extraction.fixtures import FixtureDocument, FixtureDocumentSource
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionMode
from app.extraction.schemas import DocumentKind, ExtractionJob, JobStatus
from app.extraction.stage1_reuse import (
    ReusableStage1FactsArtifact,
    load_reusable_stage1_facts,
)
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


def fixture_path(input_dir: Path, filename: str) -> Path:
    matches = sorted(input_dir.rglob(filename))
    if len(matches) != 1:
        raise RuntimeError(f"FIXTURE_PATH_NOT_UNIQUE:{filename}:{len(matches)}")
    return matches[0]


def build_gateway(settings: Any, model: str) -> ModelGatewayService:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_two_stage_experiment(prompts, schemas)
    register_selection_semantics(prompts, schemas)
    provider = GeminiProvider(
        endpoint=model_endpoint(settings.vllm_base_url, model),
        api_key=settings.vllm_api_key,
        model=model,
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
        model=model,
        max_structured_repair_retries=0,
    )


def selection_request(facts: ExperimentalCvFacts) -> InferenceRequest:
    return InferenceRequest(
        purpose=InferencePurpose.CV_EXTRACTION,
        data_classification=DataClassification.RESTRICTED,
        prompt_template_id=CRITERIA_PROMPT_ID,
        prompt_template_version="1.0",
        payload={"facts": facts.model_dump(mode="json")},
        output_contract=OutputContract(
            schema_id=CRITERIA_PROMPT_ID,
            schema_version="1.0",
            strict=True,
        ),
        output_token_budget=16384,
        correlation_id=str(uuid4()),
    )


def _fact_identity(facts: ExperimentalCvFacts) -> str:
    payload = json.dumps(facts.model_dump(mode="json"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


async def build_stage1_facts(
    input_dir: Path, settings: Any, reusable_dir: Path | None
) -> tuple[dict[str, ExperimentalCvFacts], dict[str, Any]]:
    facts_by_fixture: dict[str, ExperimentalCvFacts] = {}
    provenance: dict[str, Any] = {"reusable": False, "new_calls": 0, "reason": None}
    stage1_gateway = build_gateway(settings, settings.vllm_model)

    for filename, _domain, fixture_id in FIXTURES:
        raw = fixture_path(input_dir, filename).read_bytes()
        fixture_sha256 = hashlib.sha256(raw).hexdigest()
        page_count = len(PdfReader(BytesIO(raw)).pages)
        facts: ExperimentalCvFacts | None = None
        if reusable_dir is not None:
            candidate = reusable_dir / f"{fixture_id}.json"
            if candidate.is_file():
                artifact = ReusableStage1FactsArtifact.model_validate_json(
                    candidate.read_text(encoding="utf-8")
                )
                facts = load_reusable_stage1_facts(
                    artifact,
                    fixture_id=fixture_id,
                    fixture_sha256=fixture_sha256,
                    page_count=page_count,
                )
                provenance["reusable"] = True

        if facts is None:
            document_id = str(uuid4())
            document = FixtureDocument(
                document_id=document_id,
                kind=DocumentKind.CV,
                content="",
                content_type="application/pdf",
                raw_bytes=raw,
                page_count=page_count,
            )
            source = FixtureDocumentSource([document])
            repository = InMemoryExtractionRepository()
            job = ExtractionJob(
                id=str(uuid4()),
                document_id=document_id,
                document_kind=DocumentKind.CV,
                owner_actor_id=UUID("00000000-0000-0000-0000-000000000005"),
                correlation_id=str(uuid4()),
                status=JobStatus.QUEUED,
            )
            await repository.enqueue(job)
            worker = ExtractionWorker(
                repository,
                source,
                stage1_gateway,
                output_token_budget=16384,
                extraction_mode=ExtractionMode.FULL_DOCUMENT,
            )
            request = worker._full_request(
                job.correlation_id, "cv_full_extraction", document
            ).model_copy(
                update={
                    "prompt_template_id": "cv_fact_extraction_experiment",
                    "prompt_template_version": "1",
                    "output_contract": OutputContract(
                        schema_id="cv_fact_extraction_experiment",
                        schema_version="1",
                        strict=True,
                    ),
                }
            )
            facts = (
                await stage1_gateway.infer_structured(request, ExperimentalCvFacts)
            ).parsed
            provenance["new_calls"] += 1
            provenance["reason"] = (
                "facts unavailable for reuse due privacy-safe artifact policy"
            )
        validate_facts_references(
            facts,
            expected_document_id=facts.document_id,
            page_count=page_count,
        )
        facts_by_fixture[fixture_id] = facts

    provenance["fact_ids"] = {
        fixture_id: _fact_identity(facts)
        for fixture_id, facts in facts_by_fixture.items()
    }
    return facts_by_fixture, provenance


def _safe_fingerprint(input_dir: Path, filename: str, fixture_id: str) -> dict[str, Any]:
    raw = fixture_path(input_dir, filename).read_bytes()
    page_count = len(PdfReader(BytesIO(raw)).pages)
    fingerprint = fingerprint_bytes(
        fixture_name=fixture_id,
        document_id=f"evaluation-document:{fixture_id}",
        storage_key=f"evaluation/{fixture_id}",
        filename=filename,
        mime_type="application/pdf",
        content=raw,
        page_count=page_count,
        input_mode="native_pdf",
    )
    return {str(key): value for key, value in fingerprint.model_dump(mode="json").items()}


async def run(
    input_dir: Path,
    output_dir: Path,
    reusable_dir: Path | None,
    models: tuple[str, ...] = FLASH_MODELS,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("OUTPUT_DIR_MUST_BE_EMPTY_NO_RESAMPLING")
    for filename, _domain, _fixture_id in FIXTURES:
        fixture_path(input_dir, filename)

    app = create_app()
    settings = app.state.settings
    expectations = [
        {
            "fixture_id": fixture_id,
            "sha256": hashlib.sha256(fixture_path(input_dir, filename).read_bytes()).hexdigest(),
            "expected_supported_capability_ids": sorted(EXPECTED[fixture_id]),
        }
        for filename, _domain, fixture_id in FIXTURES
    ]
    fixtures = [
        {
            "fixture_id": fixture_id,
            "sha256": hashlib.sha256(fixture_path(input_dir, filename).read_bytes()).hexdigest(),
            "domain": domain,
        }
        for filename, domain, fixture_id in FIXTURES
    ]
    validate_comparison_inputs(
        fixtures=fixtures,
        expectations=expectations,
        taxonomy_id=TAXONOMY_ID,
        taxonomy_version=TAXONOMY_VERSION,
        expected_taxonomy_id=TAXONOMY_ID,
        expected_taxonomy_version=TAXONOMY_VERSION,
        criteria_id=STRICT_CRITERIA.criteria_id,
        expected_criteria_id=STRICT_CRITERIA.criteria_id,
        criteria_version=STRICT_CRITERIA.version,
        expected_criteria_version=STRICT_CRITERIA.version,
    )
    facts_by_fixture, stage1 = await build_stage1_facts(
        input_dir, settings, reusable_dir
    )
    manifest = build_comparison_manifest(
        fixtures=fixtures,
        stage1_fact_ids=stage1["fact_ids"],
        taxonomy_id=TAXONOMY_ID,
        taxonomy_version=TAXONOMY_VERSION,
        criteria_id=STRICT_CRITERIA.criteria_id,
        criteria_version=STRICT_CRITERIA.version,
        prompt_id=CRITERIA_PROMPT_ID,
        prompt_version="1.0",
        expectation_ref="expectations.json",
        models=models,
    )
    manifest["stage1"] = stage1
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "expectations.json").write_text(
        json.dumps(
            {
                "taxonomy_id": TAXONOMY_ID,
                "taxonomy_version": TAXONOMY_VERSION,
                "criteria_id": STRICT_CRITERIA.criteria_id,
                "criteria_version": STRICT_CRITERIA.version,
                "fixtures": expectations,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    taxonomy = get_taxonomy(TAXONOMY_ID, TAXONOMY_VERSION)
    names = {item.id: item.name for item in taxonomy.capabilities}
    per_model: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        gateway = build_gateway(settings, model)
        records: list[dict[str, Any]] = []
        for filename, domain, fixture_id in FIXTURES:
            facts = facts_by_fixture[fixture_id]
            response = await gateway.infer_structured(
                selection_request(facts), TaxonomySelection
            )
            selection = merge_taxonomy_selections(response.parsed)
            validate_taxonomy_selection(selection, facts)
            selected_ids = [item.capability_id for item in selection.capabilities]
            selected_refs = {
                item.capability_id: item.supporting_statement_ids
                for item in selection.capabilities
            }
            expected = EXPECTED[fixture_id]
            supported = [item for item in selected_ids if item in expected]
            record = compare_model_metrics(
                model=model,
                fixture_id=fixture_id,
                selected_ids=selected_ids,
                supported_ids=supported,
                expected_ids=expected,
                statement_refs=selected_refs,
            )
            record.update(
                {
                    "domain": domain,
                    "fingerprint": _safe_fingerprint(input_dir, filename, fixture_id),
                    "selected_names": [names[item] for item in selected_ids],
                    "audit": response.audit.model_dump(mode="json"),
                    "false_positive_categories": {
                        item: "OTHER" for item in selected_ids if item not in expected
                    },
                    "false_negative_categories": {
                        item: "MODEL_MISS" for item in expected if item not in selected_ids
                    },
                }
            )
            records.append(record)
        per_model[model] = records
        (output_dir / f"{model}.json").write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    aggregates: list[dict[str, Any]] = []
    for model, records in per_model.items():
        aggregate = {
            "model": model,
            "precision": sum(item["precision"] for item in records) / len(records),
            "recall": sum(item["recall"] for item in records) / len(records),
            "f1": sum(item["f1"] for item in records) / len(records),
            "selected": sum(item["selected_count"] for item in records),
            "supported": sum(item["supported_count"] for item in records),
            "unsupported": sum(item["unsupported_count"] for item in records),
            "grounding": min(item["grounding"] for item in records),
            "unknown_ids": sum(item["unknown_ids"] for item in records),
            "dangling_refs": sum(item["dangling_refs"] for item in records),
            "duplicates": sum(item["duplicates"] for item in records),
            "mean_latency_ms": sum(item["audit"]["latency_ms"] for item in records)
            / len(records),
            "input_tokens": sum(
                item["audit"]["usage"]["input_tokens"] or 0 for item in records
            ),
            "output_tokens": sum(
                item["audit"]["usage"]["output_tokens"] or 0 for item in records
            ),
            "sales_precision": next(
                item["precision"]
                for item in records
                if item["fixture_id"] == "assistant-sales-manager"
            ),
        }
        aggregates.append(aggregate)

    comparison = {
        "experiment_id": "EXT-03A.9",
        "baseline": {
            "model": "gemini-3.5-flash-lite",
            "precision": 0.8452380952380952,
            "recall": 0.6071428571428571,
            "f1": 0.6728190476190476,
            "unsupported": 4,
            "grounding": 1.0,
            "sales_precision": 0.25,
        },
        "models": aggregates,
        "stage1_provider_calls": stage1["new_calls"],
        "stage2_provider_calls": len(models) * len(FIXTURES),
        "total_provider_calls": stage1["new_calls"] + len(models) * len(FIXTURES),
        "retries_resampling": 0,
        "winner": choose_flash_candidate(aggregates),
    }
    (output_dir / "aggregate.json").write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "false-positive-analysis.json").write_text(
        json.dumps(
            {
                model: [
                    {
                        "fixture_id": item["fixture_id"],
                        "false_positive_categories": item["false_positive_categories"],
                    }
                    for item in records
                ]
                for model, records in per_model.items()
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "baseline.json").write_text(
        json.dumps(comparison["baseline"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    per_cv_dir = output_dir / "per-cv"
    per_cv_dir.mkdir(exist_ok=True)
    for fixture_id in (item[2] for item in FIXTURES):
        payload = {
            "fixture_id": fixture_id,
            "models": {
                model: next(item for item in records if item["fixture_id"] == fixture_id)
                for model, records in per_model.items()
            },
        }
        (per_cv_dir / f"{fixture_id}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    baseline = comparison["baseline"]
    delta = [
        {
            "model": item["model"],
            "precision": item["precision"] - baseline["precision"],
            "recall": item["recall"] - baseline["recall"],
            "f1": item["f1"] - baseline["f1"],
            "unsupported": item["unsupported"] - baseline["unsupported"],
            "sales_precision": item["sales_precision"] - baseline["sales_precision"],
        }
        for item in aggregates
    ]
    (output_dir / "model-deltas.json").write_text(
        json.dumps(delta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    decision = (
        "FLASH_MODEL_SELECTION_SUPPORTED"
        if comparison["winner"]
        else "FLASH_MODELS_INSUFFICIENT"
    )
    (output_dir / "evaluation.md").write_text(
        "# EXT-03A.9 Stage-2 Flash Model Comparison\n\n"
        + f"Decision: `{decision}`\n\n"
        + "```json\n"
        + json.dumps(comparison, indent=2, ensure_ascii=False)
        + "\n```\n",
        encoding="utf-8",
    )
    return comparison


async def main(
    input_dir: Path,
    output_dir: Path,
    reusable_dir: Path | None,
    models: tuple[str, ...],
) -> None:
    result = await run(input_dir, output_dir, reusable_dir, models)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument(
        "--output-dir", default="test/results/ext-03a9-flash-model-comparison"
    )
    parser.add_argument("--reusable-stage1-dir")
    parser.add_argument("--model", action="append", dest="models")
    args = parser.parse_args()
    asyncio.run(
        main(
            Path(args.input_dir),
            Path(args.output_dir),
            Path(args.reusable_stage1_dir) if args.reusable_stage1_dir else None,
            tuple(args.models) if args.models else FLASH_MODELS,
        )
    )
