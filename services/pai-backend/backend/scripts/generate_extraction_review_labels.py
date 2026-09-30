#!/usr/bin/env python3
"""Create reviewer-pending labels and metrics for an extraction run."""

import argparse
import json
from pathlib import Path

from app.extraction.benchmark_labels import (
    build_review_labels,
    compute_domain_metrics,
)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--profiles-dir", type=Path, required=True)
    parser.add_argument("--labels-out", type=Path, required=True)
    parser.add_argument("--metrics-out", type=Path, required=True)
    args = parser.parse_args()

    manifest = _read_json(args.manifest)
    if not isinstance(manifest, list):
        raise SystemExit("manifest must be a JSON array")
    profiles = []
    for path in sorted(args.profiles_dir.glob("*.json")):
        value = _read_json(path)
        if isinstance(value, dict):
            profiles.append(value)
    jobs, labels = build_review_labels(manifest, profiles)
    metrics = compute_domain_metrics(jobs, labels)
    args.labels_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    args.labels_out.write_text(
        json.dumps(
            {
                "schema_version": "benchmark_review_labels@1",
                "review_state": "pending_reviewer",
                "same_dataset": True,
                "jobs": [job.model_dump(mode="json") for job in jobs],
                "labels": [label.model_dump(mode="json") for label in labels],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    args.metrics_out.write_text(
        json.dumps(
            {
                "schema_version": "benchmark_metrics@1",
                "review_state": "pending_reviewer",
                "by_domain": {
                    domain: value.model_dump(mode="json")
                    for domain, value in metrics.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
