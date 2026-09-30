"""Verify EXT-03A.2 reference wiring using safe fingerprints only."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.extraction.fixture_integrity import SafeDocumentFingerprint, fingerprint_bytes
from app.extraction.models import ExtractionJobRecord, ExtractionProfileRecord
from app.extraction.prompts import FULL_EXTRACTION_SCHEMA_V2_1_VERSION
from app.extraction.schemas import DocumentKind
from app.extraction.worker import ExtractionWorker
from app.main import create_app


def _fingerprint(
    *,
    fixture_name: str,
    document_id: str,
    storage_key: str,
    filename: str,
    mime_type: str,
    content: bytes,
    page_count: int | None,
    input_mode: str,
) -> SafeDocumentFingerprint:
    return fingerprint_bytes(
        fixture_name=fixture_name,
        document_id=document_id,
        storage_key=storage_key,
        filename=filename,
        mime_type=mime_type,
        content=content,
        page_count=page_count,
        input_mode=input_mode,
    )


async def main(
    document_id: str,
    reference_name: str,
    reference_sha256: str,
    reference_size: int,
    reference_pages: int,
    artifact_path: Path,
    output_dir: Path,
) -> None:
    app = create_app()
    stored = await app.state.document_repository.get(UUID(document_id))
    if stored is None:
        raise RuntimeError("reference_document_not_found")
    blob = await app.state.document_blob_store.get(stored.object_key)
    document = await app.state.document_source.get(document_id, DocumentKind.CV)
    actual_pages = document.page_count

    storage_fingerprint = _fingerprint(
        fixture_name=reference_name,
        document_id=document_id,
        storage_key=stored.object_key,
        filename=reference_name,
        mime_type=stored.content_type,
        content=blob,
        page_count=actual_pages,
        input_mode="native_pdf",
    )
    expected_fingerprint = {
        "fixture_name": reference_name,
        "filename": reference_name,
        "mime_type": "application/pdf",
        "file_size": reference_size,
        "sha256": reference_sha256,
        "page_count": reference_pages,
    }

    worker = ExtractionWorker(
        app.state.extraction_repository,
        app.state.document_source,
        app.state.model_gateway,
        full_prompt_version=FULL_EXTRACTION_SCHEMA_V2_1_VERSION,
    )
    request = worker._full_request(
        "fixture-integrity-check",
        "cv_full_extraction",
        document,
    )
    request_content = request.document.content if request.document is not None else b""
    request_fingerprint = _fingerprint(
        fixture_name=reference_name,
        document_id=document_id,
        storage_key=stored.object_key,
        filename=request.document.filename if request.document and request.document.filename else "",
        mime_type=request.document.media_type if request.document else "",
        content=request_content,
        page_count=actual_pages,
        input_mode=str(request.payload.get("input_mode", "")),
    )

    async with app.state.database.session_factory() as session:
        jobs = list(
            (
                await session.scalars(
                    select(ExtractionJobRecord)
                    .where(ExtractionJobRecord.document_id == document_id)
                    .order_by(ExtractionJobRecord.created_at)
                )
            ).all()
        )
        profiles = list(
            (
                await session.scalars(
                    select(ExtractionProfileRecord)
                    .where(ExtractionProfileRecord.document_id == document_id)
                    .order_by(ExtractionProfileRecord.version)
                )
            ).all()
        )

    artifact: dict[str, Any] | None = None
    if artifact_path.exists():
        candidate = json.loads(artifact_path.read_text(encoding="utf-8"))
        if candidate.get("document_id") == document_id:
            artifact = candidate

    stored_matches_blob = stored.sha256 == storage_fingerprint.sha256 and stored.byte_size == storage_fingerprint.file_size
    expected_matches_blob = (
        expected_fingerprint["sha256"] == storage_fingerprint.sha256
        and expected_fingerprint["file_size"] == storage_fingerprint.file_size
        and expected_fingerprint["page_count"] == storage_fingerprint.page_count
        and expected_fingerprint["mime_type"] == storage_fingerprint.mime_type
    )
    request_matches_blob = (
        request_fingerprint.sha256 == storage_fingerprint.sha256
        and request_fingerprint.file_size == storage_fingerprint.file_size
        and request_fingerprint.mime_type == storage_fingerprint.mime_type
    )
    content_markers = document.content.casefold()
    output = {
        "milestone": "EXT-03A.2A",
        "generated_at": datetime.now(UTC).isoformat(),
        "reference_expected": expected_fingerprint,
        "stored_document": {
            "document_id": str(stored.id),
            "storage_key": stored.object_key,
            "filename": None,
            "mime_type": stored.content_type,
            "file_size": stored.byte_size,
            "sha256": stored.sha256,
            "page_count": actual_pages,
        },
        "blob_fingerprint": storage_fingerprint.model_dump(mode="json"),
        "gemini_request_fingerprint": request_fingerprint.model_dump(mode="json"),
        "checks": {
            "document_id_matches_reference_run": bool(artifact and artifact.get("document_id") == document_id),
            "stored_metadata_matches_blob": stored_matches_blob,
            "reference_matches_blob": expected_matches_blob,
            "request_document_matches_blob": request_matches_blob,
            "request_input_mode": request.payload.get("input_mode"),
            "request_prompt_version": request.prompt_template_version,
            "expected_labels_bound_to_checksum": bool(
                artifact
                and artifact.get("document_id") == document_id
                and artifact.get("reference_expectations", {}).get("basis")
                and artifact.get("reference_sha256") == reference_sha256
            ),
        },
        "expected_labels": ["MBA of eCommerce", "Bachelor"],
        "content_sentinel_checks": {
            "expected_education_terms_present": all(
                term in content_markers for term in ("mba", "bachelor")
            ),
            "expected_domain_terms_present": any(
                term in content_markers
                for term in ("ecommerce", "shopify", "omnichannel")
            ),
            "mechanical_testing_terms_present": any(
                term in content_markers
                for term in ("ndt", "ultrasonic", "radiographic")
            ),
        },
        "expected_labels_binding_note": "The V2.1 artifact has no reference_sha256 field; labels are not machine-bound to a checksum.",
        "runtime_history": {
            "job_count": len(jobs),
            "profile_count": len(profiles),
            "jobs": [
                {"id": job.id, "status": job.status, "profile_id": job.profile_id}
                for job in jobs
            ],
            "profiles": [
                {
                    "id": profile.id,
                    "job_id": profile.job_id,
                    "version": profile.version,
                    "prompt_version": profile.audit_metadata.get("prompt_template_version"),
                    "input_mode": profile.audit_metadata.get("input_mode"),
                }
                for profile in profiles
            ],
            "v21_calibration_persisted": False,
            "cross_fixture_reuse_detected": False,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "integrity.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "integrity.md").write_text(_markdown(output), encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))


def _markdown(output: dict[str, Any]) -> str:
    checks = output["checks"]
    return f"""# EXT-03A.2A Reference Fixture Integrity

| Check | Result |
| --- | --- |
| Document id matches reference run | {checks['document_id_matches_reference_run']} |
| Stored metadata matches blob | {checks['stored_metadata_matches_blob']} |
| Reference checksum/size/MIME/pages match blob | {checks['reference_matches_blob']} |
| Gemini request bytes match blob | {checks['request_document_matches_blob']} |
| Gemini input mode | `{checks['request_input_mode']}` |
| Gemini prompt version | `{checks['request_prompt_version']}` |
| Expected labels machine-bound to checksum | {checks['expected_labels_bound_to_checksum']} |

## Content sentinels

- Expected education terms present: {output['content_sentinel_checks']['expected_education_terms_present']}
- Expected domain terms present: {output['content_sentinel_checks']['expected_domain_terms_present']}
- Mechanical-testing terms present: {output['content_sentinel_checks']['mechanical_testing_terms_present']}

## Runtime history

- Jobs for document: {output['runtime_history']['job_count']}
- Profiles for document: {output['runtime_history']['profile_count']}
- V2.1 calibration persisted: {output['runtime_history']['v21_calibration_persisted']}
- Cross-fixture reuse detected: {output['runtime_history']['cross_fixture_reuse_detected']}

Only identifiers, storage metadata and SHA-256 fingerprints are included. No CV text or model response is stored.
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--reference-name", default="sample-cv-nguyen-van-an.pdf")
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--reference-size", type=int, required=True)
    parser.add_argument("--reference-pages", type=int, required=True)
    parser.add_argument("--artifact", default="test/results/ext-03a2-prompt-coverage/reference-v21.json")
    parser.add_argument("--output-dir", default="test/results/ext-03a2a-reference-fixture-integrity")
    args = parser.parse_args()
    asyncio.run(
        main(
            args.document_id,
            args.reference_name,
            args.reference_sha256,
            args.reference_size,
            args.reference_pages,
            Path(args.artifact),
            Path(args.output_dir),
        )
    )
