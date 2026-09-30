"""Run the bounded EXT-03A.2 native-PDF prompt calibration."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.extraction.diagnostic_matrix import CAPABILITY_FAMILIES, MatrixRun
from app.extraction.prompts import FULL_EXTRACTION_SCHEMA_V2_1_VERSION
from app.extraction.schemas import DocumentKind
from app.main import create_app
from scripts.ext_03a1_diagnostic_matrix import _run_cell


def _metric(run: MatrixRun | None) -> dict[str, object] | None:
    if run is None:
        return None
    return {
        "success": run.success,
        "failure_stage": run.failure_stage,
        "failure_code": run.failure_code,
        "counts": run.counts,
        "quality": run.quality,
        "capability_coverage": run.capability_coverage,
        "experience_recall": run.experience_recall,
        "education_recall": run.education_recall,
        "latency_ms": run.latency_ms,
        "token_usage": run.token_usage.model_dump(mode="json"),
        "candidate_profile_created": run.candidate_profile_created,
    }


def _coverage(run: MatrixRun | None) -> float | None:
    if run is None or not run.success:
        return None
    found = sum(value == "FOUND" for value in run.capability_coverage.values())
    return found / len(CAPABILITY_FAMILIES)


def _baseline_metric(artifact: dict[str, Any], group: str, key: str) -> object:
    baseline = artifact.get("baseline_v2_0_medium")
    if not isinstance(baseline, dict):
        return "—"
    values = baseline if not group else baseline.get(group)
    return values.get(key, "—") if isinstance(values, dict) else "—"


async def main(document_id: str, output_dir: Path, baseline_path: Path) -> None:
    app = create_app()
    document = await app.state.document_source.get(document_id, DocumentKind.CV)
    calibrated = await _run_cell(
        app,
        document,
        input_mode="native_pdf",
        thinking="medium",
        prompt_version=FULL_EXTRACTION_SCHEMA_V2_1_VERSION,
    )

    baseline: dict[str, Any] | None = None
    if baseline_path.exists():
        source = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline = next(
            (
                run
                for run in source.get("runs", [])
                if run.get("input_mode") == "native_pdf"
                and run.get("thinking") == "medium"
                and run.get("prompt_version") == "2.0"
            ),
            None,
        )

    artifact = {
        "milestone": "EXT-03A.2",
        "generated_at": datetime.now(UTC).isoformat(),
        "reference_fixture": "Nguyen Vu Minh Thien CV PDF",
        "document_id": document_id,
        "configuration": {
            "input_mode": "native_pdf",
            "thinking": "medium",
            "provider": "gemini",
            "model": app.state.settings.vllm_model,
            "prompt_id": "cv_full_extraction",
            "prompt_version": FULL_EXTRACTION_SCHEMA_V2_1_VERSION,
            "output_token_budget": 16384,
            "structured_repair_retries": 0,
        },
        "reference_expectations": {
            "experience_minimum": 4,
            "education_count": 2,
            "capability_families": list(CAPABILITY_FAMILIES),
            "basis": "bounded evaluation metadata from the reviewed reference fixture; not production logic",
        },
        "baseline_v2_0_medium": baseline,
        "calibrated_v2_1_medium": calibrated.model_dump(mode="json"),
        "comparison": {
            "baseline": baseline,
            "calibrated": _metric(calibrated),
            "baseline_capability_family_recall": (
                sum(value == "FOUND" for value in baseline.get("capability_coverage", {}).values())
                / len(CAPABILITY_FAMILIES)
                if baseline and isinstance(baseline.get("capability_coverage"), dict)
                else None
            ),
            "calibrated_capability_family_recall": _coverage(calibrated),
        },
        "candidate_profile_compatibility": calibrated.candidate_profile_created,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reference-v21.json").write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "evaluation.md").write_text(_markdown(artifact), encoding="utf-8")
    print(json.dumps(artifact, indent=2, ensure_ascii=False))


def _markdown(artifact: dict[str, Any]) -> str:
    calibrated = artifact["calibrated_v2_1_medium"]
    return f"""# EXT-03A.2 Prompt Coverage Calibration

## Configuration

- Input: native PDF
- Thinking: medium
- Prompt: cv_full_extraction@2.1
- Model: {artifact["configuration"]["model"]}
- Output budget: 16384

## Result

| Metric | V2.0 Medium | V2.1 Medium |
| --- | ---: | ---: |
| Technical success | {bool(artifact["baseline_v2_0_medium"] and artifact["baseline_v2_0_medium"].get("success"))} | {calibrated["success"]} |
| Experience | {_baseline_metric(artifact, "counts", "experience")} | {calibrated["counts"].get("experience", "—")} |
| Education | {_baseline_metric(artifact, "counts", "education")} | {calibrated["counts"].get("education", "—")} |
| Capabilities | {_baseline_metric(artifact, "counts", "capabilities")} | {calibrated["counts"].get("capabilities", "—")} |
| Tools | {_baseline_metric(artifact, "counts", "tools_platforms")} | {calibrated["counts"].get("tools_platforms", "—")} |
| Grounded rate | {_baseline_metric(artifact, "quality", "grounded_capability_rate")} | {calibrated["quality"].get("grounded_capability_rate", "—")} |
| Latency | {_baseline_metric(artifact, "", "latency_ms")}ms | {calibrated["latency_ms"]}ms |

The artifact contains counts and metrics only; it does not contain document text or a raw provider response.
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--output-dir", default="test/results/ext-03a2-prompt-coverage")
    parser.add_argument(
        "--baseline",
        default="test/results/ext-03a1-diagnostic-matrix/matrix.json",
    )
    args = parser.parse_args()
    asyncio.run(main(args.document_id, Path(args.output_dir), Path(args.baseline)))
