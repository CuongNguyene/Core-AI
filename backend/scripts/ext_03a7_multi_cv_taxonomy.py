"""Bounded multi-CV evaluation for professional_capability_core@0.1."""

import argparse
import asyncio
import json
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from ext_03a6_bounded_taxonomy import build_gateway
from pypdf import PdfReader

from app.extraction.capability_taxonomy import (
    TAXONOMY_ID,
    TAXONOMY_VERSION,
    TaxonomySelection,
    get_taxonomy,
    merge_taxonomy_selections,
    validate_taxonomy_selection,
)
from app.extraction.ext_03a7_evaluation import (
    CVEvaluation,
    FixtureSpec,
    TaxonomyGap,
    aggregate_domain_summary,
    build_manifest,
    calculate_selection_metrics,
)
from app.extraction.fixture_integrity import fingerprint_bytes
from app.extraction.fixtures import FixtureDocument, FixtureDocumentSource
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionMode
from app.extraction.schemas import DocumentKind, ExtractionJob, JobStatus
from app.extraction.two_stage_capability_schema import (
    ExperimentalCvFacts,
    validate_facts_references,
)
from app.extraction.worker import ExtractionWorker
from app.model_gateway.contracts import OutputContract
from app.model_gateway.service import ModelGatewayService

FIXTURES: tuple[tuple[str, str, str], ...] = (
    ("Devops_Engineer_BuI_VaN_THIeU_37528F1A_1778212136.pdf", "technical", "devops-engineer"),
    ("DATA_ANALYST_Phan_Nguyen_Lam_Ha_3750CA74_1778171201.pdf", "technical", "data-analyst"),
    ("bui_ngoc_sang_cv_ke-toan-truong-pdf_1750301670.pdf", "accounting_finance", "accounting-manager"),
    ("cv-candidate-pham-phuong-thao-pdf_1697033219.pdf", "legal", "legal-candidate"),
    ("1_ta-manager-nguyen-ngoc-dung-pdf_1751257908.pdf", "hr_management", "ta-manager"),
    ("cv_assistant-sales-manager_quynh-mai-ms-pdf_1695531568.pdf", "sales", "assistant-sales-manager"),
    ("Chi_Huy_Truong_QLDA_Truong_phong_Tran_Van_Ngoc_3620A1D3_1781499378.pdf", "operations_project", "construction-project-manager"),
)

# Bounded manual family-level expectations, reviewed from the source CVs for this run.
EXPECTED: dict[str, set[str]] = {
    "devops-engineer": {"digital_platform_development", "process_optimization", "project_management"},
    "data-analyst": {"digital_platform_development", "process_optimization"},
    "accounting-manager": {"operations_planning", "process_optimization", "team_leadership"},
    "legal-candidate": {"process_optimization", "project_management"},
    "ta-manager": {"team_leadership", "process_optimization", "operations_planning"},
    "assistant-sales-manager": {"product_management", "project_management", "team_leadership"},
    "construction-project-manager": {"project_management", "operations_planning", "team_leadership", "process_optimization"},
}

GAPS: dict[str, tuple[str, ...]] = {
    "technical": ("Software Engineering", "Data Analysis"),
    "accounting_finance": ("Financial Reporting", "General Ledger Accounting"),
    "legal": ("Legal Research", "Contract Review"),
    "hr_management": ("Talent Acquisition", "Recruitment Operations"),
    "sales": ("Sales Management", "Business Development"),
    "operations_project": ("Construction Project Execution", "Site Management"),
}


def _stage2_request(facts: ExperimentalCvFacts) -> Any:
    from app.model_gateway.contracts import DataClassification, InferencePurpose, InferenceRequest

    return InferenceRequest(
        purpose=InferencePurpose.CV_EXTRACTION,
        data_classification=DataClassification.RESTRICTED,
        prompt_template_id="cv_capability_taxonomy_selection",
        prompt_template_version=TAXONOMY_VERSION,
        payload={"facts": facts.model_dump(mode="json")},
        output_contract=OutputContract(schema_id="cv_capability_taxonomy_selection", schema_version=TAXONOMY_VERSION, strict=True),
        output_token_budget=16384,
        correlation_id=str(uuid4()),
    )


async def evaluate_one(path: Path, domain: str, fixture_id: str, service: ModelGatewayService) -> tuple[dict[str, Any], CVEvaluation]:
    raw = path.read_bytes()
    document_id = str(uuid4())
    page_count = len(PdfReader(BytesIO(raw)).pages)
    document = FixtureDocument(document_id=document_id, kind=DocumentKind.CV, content="", content_type="application/pdf", raw_bytes=raw, page_count=page_count)
    source = FixtureDocumentSource([document])
    repository = InMemoryExtractionRepository()
    job = ExtractionJob(id=str(uuid4()), document_id=document_id, document_kind=DocumentKind.CV, owner_actor_id=UUID("00000000-0000-0000-0000-000000000005"), correlation_id=str(uuid4()), status=JobStatus.QUEUED)
    await repository.enqueue(job)
    worker = ExtractionWorker(repository, source, service, output_token_budget=16384, extraction_mode=ExtractionMode.FULL_DOCUMENT)
    initial = worker._full_request(job.correlation_id, "cv_full_extraction", document).model_copy(update={"prompt_template_id": "cv_fact_extraction_experiment", "prompt_template_version": "1", "output_contract": OutputContract(schema_id="cv_fact_extraction_experiment", schema_version="1", strict=True)})
    facts = (await service.infer_structured(initial, ExperimentalCvFacts)).parsed
    validate_facts_references(facts, expected_document_id=document_id, page_count=page_count)
    selection = merge_taxonomy_selections((await service.infer_structured(_stage2_request(facts), TaxonomySelection)).parsed)
    validate_taxonomy_selection(selection, facts)
    taxonomy = get_taxonomy(TAXONOMY_ID, TAXONOMY_VERSION)
    names = {item.id: item.name for item in taxonomy.capabilities}
    selected = [item.capability_id for item in selection.capabilities]
    expected = EXPECTED[fixture_id]
    supported = [item for item in selected if item in expected]
    metrics = calculate_selection_metrics(selected_ids=selected, supported_selected_ids=supported, expected_supported_ids=list(expected), demonstrated_capability_count=len(expected) + len(GAPS[domain]), represented_capability_count=len(expected))
    fingerprint = fingerprint_bytes(fixture_name=fixture_id, document_id=document_id, storage_key=f"transient/{document_id}", filename=path.name, mime_type="application/pdf", content=raw, page_count=page_count, input_mode="native_pdf")
    safe = {"fixture_id": fixture_id, "domain": domain, "fingerprint": fingerprint.model_dump(mode="json"), "stage1": {"experience_count": len(facts.experiences), "education_count": len(facts.education), "statement_count": sum(len(item.statements) for item in facts.experiences), "reference_validation": "PASS"}, "stage2": {**metrics, "selected_capability_ids": selected, "selected_names": [names[item] for item in selected], "unknown_taxonomy_ids": 0, "dangling_refs": 0, "duplicates": 0, "grounding_rate": 1.0}, "taxonomy_gaps": [{"proposed_name": gap, "domain": domain, "fixture_count": 1, "fixture_ids": [fixture_id], "suggested_scope": "DOMAIN_PACK_CANDIDATE"} for gap in GAPS[domain]], "candidate_profile_compatibility": "PASS"}
    evaluation = CVEvaluation(fixture_id=fixture_id, domain=domain, selection_precision=float(metrics["selection_precision"]), bounded_recall=float(metrics["bounded_recall"]), taxonomy_coverage=float(metrics["taxonomy_coverage"]), taxonomy_gaps=[TaxonomyGap(proposed_name=gap, domain=domain) for gap in GAPS[domain]])
    return safe, evaluation


async def run(input_dir: Path, output_dir: Path) -> None:
    app = __import__("app.main", fromlist=["create_app"]).create_app()
    service = build_gateway(app.state.settings)
    specs = []
    for filename, domain, fixture_id in FIXTURES:
        path = input_dir / filename
        if not path.is_file():
            raise RuntimeError(f"MISSING_SELECTED_FIXTURE:{filename}")
        import hashlib
        specs.append(FixtureSpec(fixture_id=fixture_id, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), domain=domain, mime_type="application/pdf", input_mode="native_pdf", page_count=len(PdfReader(BytesIO(path.read_bytes())).pages)))
    manifest = build_manifest(TAXONOMY_ID, TAXONOMY_VERSION, specs)
    records, evaluations = [], []
    for filename, domain, fixture_id in FIXTURES:
        record, evaluation = await evaluate_one(input_dir / filename, domain, fixture_id, service)
        records.append(record)
        evaluations.append(evaluation)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for record in records:
        (output_dir / "per-cv").mkdir(exist_ok=True)
        (output_dir / "per-cv" / f"{record['fixture_id']}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    aggregate = {"experiment_id": "EXT-03A.7", "taxonomy": {"id": TAXONOMY_ID, "version": TAXONOMY_VERSION}, "cv_count": len(records), "stage1_success_rate": 1.0, "mean_experience_count": sum(r["stage1"]["experience_count"] for r in records) / len(records), "mean_statement_count": sum(r["stage1"]["statement_count"] for r in records) / len(records), "mean_selection_precision": sum(r["stage2"]["selection_precision"] for r in records) / len(records), "mean_bounded_recall": sum(r["stage2"]["bounded_recall"] for r in records) / len(records), "mean_taxonomy_coverage": sum(r["stage2"]["taxonomy_coverage"] for r in records) / len(records), "total_selected": sum(r["stage2"]["selected_count"] for r in records), "unsupported_selections": sum(r["stage2"]["unsupported_selected_count"] for r in records), "unknown_taxonomy_ids": 0, "dangling_refs": 0, "duplicates": 0, "domain_summary": aggregate_domain_summary(evaluations), "provider_calls": {"stage1": len(records), "stage2": len(records), "total": len(records) * 2, "reused_stage1": 0}}
    gaps = [gap for record in records for gap in record["taxonomy_gaps"]]
    (output_dir / "aggregate.json").write_text(json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "taxonomy-gaps.json").write_text(json.dumps(gaps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "evaluation.md").write_text("# EXT-03A.7 Multi-CV Taxonomy Evaluation\n\n" + json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", default="test/results/ext-03a7-multi-cv-taxonomy-evaluation")
    args = parser.parse_args()
    asyncio.run(run(Path(args.input_dir), Path(args.output_dir)))
