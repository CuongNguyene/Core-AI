"""Prepare condition-blind human-review packets from completed research runs."""

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.instructional_design.experiment import (
    BlindedReviewPayload,
    ExperimentRunResult,
    build_blinded_review_payload,
)


class PrivateReviewMapping(BaseModel):
    """Researcher-only link; never include this file in a reviewer handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    review_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    condition: str = Field(min_length=1)


class BlindedReviewBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    packets: list[BlindedReviewPayload] = Field(min_length=1)
    private_mapping: list[PrivateReviewMapping] = Field(min_length=1)


def build_blinded_review_bundle(results: list[ExperimentRunResult]) -> BlindedReviewBundle:
    """Create deterministic opaque packet IDs; failed runs cannot enter human review."""

    completed = sorted(
        (result for result in results if result.snapshot is not None),
        key=lambda result: result.run.run_id,
    )
    if len(completed) != len(results):
        raise ValueError("all review runs must have a completed research snapshot")
    packets: list[BlindedReviewPayload] = []
    mappings: list[PrivateReviewMapping] = []
    for index, result in enumerate(completed, start=1):
        review_id = f"review-{index:03d}"
        packets.append(build_blinded_review_payload(result, review_id=review_id))
        mappings.append(
            PrivateReviewMapping(
                review_id=review_id,
                run_id=result.run.run_id,
                condition=result.run.condition.value,
            )
        )
    return BlindedReviewBundle(packets=packets, private_mapping=mappings)


def write_blinded_review_bundle(bundle: BlindedReviewBundle, output_dir: Path) -> None:
    """Write reviewer-safe packets separately from the researcher-only mapping."""

    packet_dir = output_dir / "reviewer-packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    for packet in bundle.packets:
        (packet_dir / f"{packet.review_id}.json").write_text(
            json.dumps(packet.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (output_dir / "researcher-private-review-mapping.json").write_text(
        json.dumps(
            {"private_mapping": [item.model_dump(mode="json") for item in bundle.private_mapping]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_experiment_results(results_path: Path) -> list[ExperimentRunResult]:
    """Parse persisted JSON through Pydantic's strict JSON wire-mode validator."""

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    raw_results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(raw_results, list):
        raise ValueError("results artifact must contain a results list")
    return [
        ExperimentRunResult.model_validate_json(json.dumps(item)) for item in raw_results
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare opaque ID-02 blinded-review packets.")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    bundle = build_blinded_review_bundle(load_experiment_results(args.results))
    write_blinded_review_bundle(bundle, args.output_dir)
    print(json.dumps({"packet_count": len(bundle.packets)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
