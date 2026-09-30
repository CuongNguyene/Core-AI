#!/usr/bin/env python3
"""Generate the semantic benchmark artifacts from an existing extraction run."""

import argparse
import json
from pathlib import Path

from app.extraction.semantic_benchmark import (
    SemanticBenchmarkLabel,
    build_expected_record_templates,
    build_pilot_selection,
    compute_semantic_metrics,
    generate_decision_report,
)


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _pilot_labels(pilot: dict[str, object]) -> list[SemanticBenchmarkLabel]:
    labels: list[SemanticBenchmarkLabel] = []
    profiles = pilot.get("selected_profiles", [])
    if not isinstance(profiles, list):
        return labels
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        claims = profile.get("claims", [])
        if not isinstance(claims, list):
            continue
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            labels.append(
                SemanticBenchmarkLabel(
                    label_id=str(claim["label_id"]),
                    domain=str(claim["domain"]),
                    source_file=str(profile.get("source_file", "")),
                    profile_id=str(profile["profile_id"]),
                    bucket=str(claim["bucket"]),
                    claim_index=int(claim["claim_index"]),
                    observed_value=claim.get("observed_value"),
                    observed_evidence_type=claim.get("observed_evidence_type"),
                    observed_status=claim.get("observed_status"),
                    locator_resolved=bool(claim.get("locator_resolved", False)),
                )
            )
    return labels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--profiles-dir", type=Path, required=True)
    parser.add_argument("--grounding-queue", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = _read(args.manifest)
    if not isinstance(manifest, list):
        raise SystemExit("manifest must be a JSON array")
    profiles: list[dict[str, object]] = []
    for path in sorted(args.profiles_dir.glob("*.json")):
        value = _read(path)
        if isinstance(value, dict):
            profiles.append(value)
    grounding = _read(args.grounding_queue)
    grounding_items = grounding.get("items", []) if isinstance(grounding, dict) else []
    if not isinstance(grounding_items, list):
        grounding_items = []

    pilot = build_pilot_selection(manifest, profiles)
    labels = _pilot_labels(pilot)
    expected = build_expected_record_templates(manifest)
    metrics = compute_semantic_metrics(manifest, labels, expected, grounding_items)
    report = generate_decision_report(manifest, labels, expected, grounding_items)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    (args.output_dir / "semantic_benchmark_pilot.json").write_text(
        json.dumps(pilot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "semantic_benchmark_review_labels.json").write_text(
        json.dumps(
            {
                "schema_version": "semantic_benchmark_review_labels@1",
                "review_state": "pending_reviewer",
                "rubric_version": "semantic_cv_extraction_v1",
                "labels": [label.model_dump(mode="json") for label in labels],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "semantic_expected_records.json").write_text(
        json.dumps(
            {
                "schema_version": "semantic_expected_records@1",
                "review_state": "pending_reviewer",
                "records": [record.model_dump(mode="json") for record in expected],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "semantic_benchmark_metrics.json").write_text(
        json.dumps(
            {
                "schema_version": "semantic_benchmark_metrics@1",
                "review_state": "pending_reviewer",
                "reliability_metrics_separate": True,
                "by_domain": {
                    domain: metric.model_dump(mode="json")
                    for domain, metric in metrics.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "semantic_benchmark_report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
