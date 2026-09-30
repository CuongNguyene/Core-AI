"""Run the checksum-bound EXT-03A.2B V2.0/V2.1 reference comparison."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from app.extraction.evaluation_binding import (
    EvaluationManifest,
    evaluate_education_recall,
    result_binding,
    run_bound_evaluation,
)
from app.extraction.fixture_integrity import fingerprint_bytes
from app.extraction.prompts import (
    FULL_EXTRACTION_SCHEMA_V2_1_VERSION,
    FULL_EXTRACTION_SCHEMA_V2_VERSION,
)
from app.extraction.schemas import DocumentKind
from app.main import create_app
from scripts.ext_03a1_diagnostic_matrix import _run_cell


def _load_manifest(path: Path) -> EvaluationManifest:
    return EvaluationManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _run_metrics(run: Any, manifest: EvaluationManifest) -> dict[str, object]:
    education = evaluate_education_recall(
        run.education_summary,
        manifest.expected_education,
    )
    coverage = {
        family: run.capability_coverage.get(family, "NOT_FOUND")
        for family in manifest.expected_capability_families
    }
    count = int(run.counts.get("experience", 0))
    return {
        "run": run.model_dump(mode="json"),
        "experience_recall": {
            "actual": count,
            "minimum": manifest.experience_minimum,
            "recall": min(count / manifest.experience_minimum, 1.0)
            if manifest.experience_minimum
            else 1.0,
        },
        "education_recall": education,
        "capability_family_coverage": coverage,
        "capability_family_recall": (
            sum(value == "FOUND" for value in coverage.values()) / len(coverage)
            if coverage
            else 1.0
        ),
    }


async def main(manifest_path: Path, output_dir: Path) -> None:
    manifest = _load_manifest(manifest_path)
    app = create_app()
    if manifest.document_id is None:
        raise RuntimeError("EVALUATION_FIXTURE_INTEGRITY_FAILED")
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

    async def evaluate(prompt_version: str) -> dict[str, object]:
        run = await run_bound_evaluation(
            manifest,
            actual,
            lambda: _run_cell(
                app,
                document,
                input_mode="native_pdf",
                thinking="medium",
                prompt_version=prompt_version,
            ),
        )
        return {
            **result_binding(manifest),
            "prompt_version": prompt_version,
            "input_mode": "native_pdf",
            "thinking": "medium",
            "provider": "gemini",
            "model": app.state.settings.vllm_model,
            **_run_metrics(run, manifest),
        }

    v20 = cast(dict[str, Any], await evaluate(FULL_EXTRACTION_SCHEMA_V2_VERSION))
    v21 = cast(dict[str, Any], await evaluate(FULL_EXTRACTION_SCHEMA_V2_1_VERSION))
    if v20["reference_sha256"] != v21["reference_sha256"]:
        raise RuntimeError("EVALUATION_FIXTURE_INTEGRITY_FAILED")

    comparison = {
        "experience_recall": {
            "v2.0": v20["experience_recall"]["recall"],
            "v2.1": v21["experience_recall"]["recall"],
        },
        "education_recall": {
            "v2.0": v20["education_recall"]["recall"],
            "v2.1": v21["education_recall"]["recall"],
        },
        "capability_family_recall": {
            "v2.0": v20["capability_family_recall"],
            "v2.1": v21["capability_family_recall"],
        },
        "grounding": {
            "v2.0": v20["run"]["quality"].get("grounded_capability_rate"),
            "v2.1": v21["run"]["quality"].get("grounded_capability_rate"),
        },
        "unsupported": {
            "v2.0": v20["run"]["quality"].get("unsupported_capability_count"),
            "v2.1": v21["run"]["quality"].get("unsupported_capability_count"),
        },
        "duplicates": {
            "v2.0": v20["run"]["quality"].get("duplicate_capability_count"),
            "v2.1": v21["run"]["quality"].get("duplicate_capability_count"),
        },
    }
    artifact = {
        "milestone": "EXT-03A.2B",
        "generated_at": datetime.now(UTC).isoformat(),
        "fixture": result_binding(manifest),
        "expectations": manifest.model_dump(mode="json"),
        "runs": {"v2.0": v20, "v2.1": v21},
        "comparison": comparison,
        "decision": {
            "v2_1_materially_improves_valid_reference_recall": False,
            "previous_comparison_valid": False,
            "next_action": "PROCEED_TO_EXT_03A_2_PROMPT_2_2_CALIBRATION",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "v20.json").write_text(json.dumps(v20, indent=2) + "\n", encoding="utf-8")
    (output_dir / "v21.json").write_text(json.dumps(v21, indent=2) + "\n", encoding="utf-8")
    (output_dir / "evaluation.json").write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "evaluation.md").write_text(_markdown(artifact), encoding="utf-8")
    print(json.dumps(artifact, indent=2, ensure_ascii=False))


def _markdown(artifact: dict[str, Any]) -> str:
    fixture = artifact["fixture"]
    v20 = artifact["runs"]["v2.0"]
    v21 = artifact["runs"]["v2.1"]
    rows = [
        "# EXT-03A.2B Checksum-Bound Reference Evaluation",
        "",
        "## Fixture integrity",
        "",
        f"- Fixture: `{fixture['fixture_id']}`",
        f"- SHA-256: `{fixture['reference_sha256']}`",
        f"- MIME: `{fixture['mime_type']}`",
        f"- Pages: `{fixture['page_count']}`",
        "- Preflight: passed before each provider run",
        "",
        "## Corrected expectations",
        "",
        f"- Education: {', '.join(artifact['expectations']['expected_education'])}",
        f"- Experience minimum: {artifact['expectations']['experience_minimum']}",
        f"- Capability families: {len(artifact['expectations']['expected_capability_families'])}",
        "",
        "## Comparison",
        "",
        "| Metric | V2.0 Medium | V2.1 Medium |",
        "| --- | ---: | ---: |",
        f"| Experience recall | {v20['experience_recall']['recall']:.2f} | {v21['experience_recall']['recall']:.2f} |",
        f"| Education recall | {v20['education_recall']['recall']:.2f} | {v21['education_recall']['recall']:.2f} |",
        f"| Capability family recall | {v20['capability_family_recall']:.2f} | {v21['capability_family_recall']:.2f} |",
        f"| Grounding | {v20['run']['quality'].get('grounded_capability_rate')} | {v21['run']['quality'].get('grounded_capability_rate')} |",
        f"| Unsupported | {v20['run']['quality'].get('unsupported_capability_count')} | {v21['run']['quality'].get('unsupported_capability_count')} |",
        f"| Duplicates | {v20['run']['quality'].get('duplicate_capability_count')} | {v21['run']['quality'].get('duplicate_capability_count')} |",
        f"| Latency | {v20['run']['latency_ms']}ms | {v21['run']['latency_ms']}ms |",
        f"| Output tokens | {v20['run']['token_usage'].get('output_tokens')} | {v21['run']['token_usage'].get('output_tokens')} |",
        "",
        "The previous V2.0/V2.1 calibration is preserved but invalid for recall conclusions: its expected labels were not bound to the evaluated source checksum.",
        "",
        "## Conclusion",
        "",
        "V2.0 and V2.1 above are the only checksum-bound comparison runs. Prompt 2.2 is not created in this milestone.",
        "",
    ]
    return "\n".join(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default="test/fixtures/extraction/ext-03a2b-cv-nguyen-vu-minh-thien.json",
    )
    parser.add_argument(
        "--output-dir",
        default="test/results/ext-03a2b-checksum-bound-reference",
    )
    args = parser.parse_args()
    asyncio.run(main(Path(args.manifest), Path(args.output_dir)))
