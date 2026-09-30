"""Run one checksum-bound EXT-03A.2C prompt 2.2 reference evaluation."""

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
from app.extraction.prompts import FULL_EXTRACTION_SCHEMA_V2_2_VERSION
from app.extraction.schemas import DocumentKind
from app.main import create_app
from scripts.ext_03a1_diagnostic_matrix import _run_cell


def _metrics(run: Any, manifest: EvaluationManifest) -> dict[str, object]:
    coverage = {
        family: run.capability_coverage.get(family, "NOT_FOUND")
        for family in manifest.expected_capability_families
    }
    education = evaluate_education_recall(run.education_summary, manifest.expected_education)
    experience = int(run.counts.get("experience", 0))
    return {
        "run": run.model_dump(mode="json"),
        "experience_recall": {
            "actual": experience,
            "minimum": manifest.experience_minimum,
            "recall": min(experience / manifest.experience_minimum, 1.0)
            if manifest.experience_minimum
            else 1.0,
        },
        "education_recall": education,
        "capability_family_coverage": coverage,
        "capability_family_recall": sum(value == "FOUND" for value in coverage.values()) / len(coverage)
        if coverage
        else 1.0,
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
    run = await run_bound_evaluation(
        manifest,
        actual,
        lambda: _run_cell(
            app,
            document,
            input_mode="native_pdf",
            thinking="medium",
            prompt_version=FULL_EXTRACTION_SCHEMA_V2_2_VERSION,
        ),
    )
    metrics = _metrics(run, manifest)
    reference = result_binding(manifest)
    artifact = {
        "milestone": "EXT-03A.2C",
        "generated_at": datetime.now(UTC).isoformat(),
        "fixture": reference,
        "baseline": baseline,
        "v22": {
            **reference,
            "prompt_version": FULL_EXTRACTION_SCHEMA_V2_2_VERSION,
            "input_mode": "native_pdf",
            "thinking": "medium",
            "provider": "gemini",
            "model": app.state.settings.vllm_model,
            **metrics,
        },
    }
    v22 = cast(dict[str, Any], artifact["v22"])
    recall = float(v22["capability_family_recall"])
    quality = cast(dict[str, Any], v22["run"]["quality"])
    artifact["decision"] = {
        "capability_gate_passed": recall >= 7 / 11,
        "experience_gate_passed": v22["experience_recall"]["recall"] >= 1.0,
        "education_gate_passed": v22["education_recall"]["recall"] >= 1.0,
        "grounding_gate_passed": quality.get("grounded_capability_rate", 0) >= 0.95,
        "unsupported_gate_passed": quality.get("unsupported_capability_count", 99) <= 1,
        "duplicate_gate_passed": quality.get("duplicate_capability_count", 99) == 0,
        "next_action": (
            "ACCEPT_V2_2_AND_PROCEED_TO_MULTI_CV_EVALUATION"
            if recall >= 7 / 11
            and v22["experience_recall"]["recall"] >= 1.0
            and v22["education_recall"]["recall"] >= 1.0
            and quality.get("grounded_capability_rate", 0) >= 0.95
            and quality.get("unsupported_capability_count", 99) <= 1
            else "REVISIT_V2_SCHEMA_BEFORE_MORE_PROMPT_TUNING"
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "v21-baseline.json").write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "v22.json").write_text(
        json.dumps(v22, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "evaluation.json").write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "evaluation.md").write_text(_markdown(artifact), encoding="utf-8")
    print(json.dumps(artifact, indent=2, ensure_ascii=False))


def _markdown(artifact: dict[str, Any]) -> str:
    base = artifact["baseline"]
    v22 = artifact["v22"]
    decision = artifact["decision"]
    return f"""# EXT-03A.2C Prompt 2.2 Capability Derivation Calibration

## Reference

- Fixture: `{artifact['fixture']['fixture_id']}`
- SHA-256: `{artifact['fixture']['reference_sha256']}`
- Input: native PDF
- Model: `{v22['model']}`
- Thinking: medium
- Provider calls: 1

## Hypothesis

Prompt 2.2 makes capability derivation explicitly dependent on inspecting every
experience record, while preserving V2.1 enumeration, strict grounding,
proficiency safeguards and tool/capability separation.

## Comparison

| Metric | V2.1 | V2.2 |
| --- | ---: | ---: |
| Experience recall | {base['experience_recall']['recall']} | {v22['experience_recall']['recall']} |
| Education recall | {base['education_recall']['recall']} | {v22['education_recall']['recall']} |
| Capability family recall | {base['capability_family_recall']} | {v22['capability_family_recall']} |
| Grounding | {base['run']['quality'].get('grounded_capability_rate')} | {v22['run']['quality'].get('grounded_capability_rate')} |
| Unsupported | {base['run']['quality'].get('unsupported_capability_count')} | {v22['run']['quality'].get('unsupported_capability_count')} |
| Duplicates | {base['run']['quality'].get('duplicate_capability_count')} | {v22['run']['quality'].get('duplicate_capability_count')} |
| Latency | {base['run']['latency_ms']}ms | {v22['run']['latency_ms']}ms |
| Output tokens | {base['run']['token_usage'].get('output_tokens')} | {v22['run']['token_usage'].get('output_tokens')} |

## Capability family results

{chr(10).join(f"- {family}: {status}" for family, status in v22['capability_family_coverage'].items())}

Extracted capabilities are recorded by name and deterministic quality metrics
only; raw CV text and raw Gemini response are not stored.

## Decision

- Capability gate: `{decision['capability_gate_passed']}`
- Experience gate: `{decision['experience_gate_passed']}`
- Education gate: `{decision['education_gate_passed']}`
- Grounding gate: `{decision['grounding_gate_passed']}`
- Unsupported gate: `{decision['unsupported_gate_passed']}`
- Duplicate gate: `{decision['duplicate_gate_passed']}`
- Next action: `{decision['next_action']}`

No prompt 2.3, schema redesign, migration, frontend change or multi-CV run
was performed.
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default="test/fixtures/extraction/ext-03a2b-cv-nguyen-vu-minh-thien.json",
    )
    parser.add_argument(
        "--baseline",
        default="test/results/ext-03a2b-checksum-bound-reference/v21.json",
    )
    parser.add_argument("--output-dir", default="test/results/ext-03a2c-prompt-22")
    args = parser.parse_args()
    asyncio.run(main(Path(args.manifest), Path(args.baseline), Path(args.output_dir)))
