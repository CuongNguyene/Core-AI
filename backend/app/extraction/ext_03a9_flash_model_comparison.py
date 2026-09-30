"""Bounded mechanics for the EXT-03A.9 Stage-2 Flash comparison."""

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

FLASH_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
)
QUALITY_PRECISION = 0.90
QUALITY_RECALL = 0.70
QUALITY_GROUNDING = 0.95


def model_endpoint(base_endpoint: str, model: str) -> str:
    """Select a Gemini model without changing an unrelated proxy endpoint."""
    pattern = r"(/models/)[^/:]+(:generateContent(?:$|[/?]))"
    if re.search(pattern, base_endpoint):
        return re.sub(pattern, rf"\g<1>{model}\g<2>", base_endpoint)
    return base_endpoint


def build_comparison_manifest(
    *,
    fixtures: Sequence[Mapping[str, str]],
    stage1_fact_ids: Mapping[str, str],
    taxonomy_id: str,
    taxonomy_version: str,
    criteria_id: str,
    criteria_version: str,
    prompt_id: str,
    prompt_version: str,
    expectation_ref: str,
    models: Sequence[str] = FLASH_MODELS,
) -> dict[str, Any]:
    """Build the immutable identity record shared by every model run."""
    return {
        "experiment_id": "EXT-03A.9",
        "taxonomy": {"id": taxonomy_id, "version": taxonomy_version},
        "criteria": {"id": criteria_id, "version": criteria_version},
        "prompt": {"id": prompt_id, "version": prompt_version},
        "thinking": "medium",
        "models": list(models),
        "expectation_ref": expectation_ref,
        "fixtures": [dict(fixture) for fixture in fixtures],
        "stage1_fact_ids": dict(stage1_fact_ids),
    }


def validate_comparison_inputs(
    *,
    fixtures: Sequence[Mapping[str, str]],
    expectations: Sequence[Mapping[str, object]],
    taxonomy_id: str,
    taxonomy_version: str,
    expected_taxonomy_id: str,
    expected_taxonomy_version: str,
    criteria_id: str,
    expected_criteria_id: str,
    criteria_version: str,
    expected_criteria_version: str,
) -> None:
    """Fail closed when the comparison inputs are not the frozen inputs."""
    if (taxonomy_id, taxonomy_version) != (
        expected_taxonomy_id,
        expected_taxonomy_version,
    ):
        raise ValueError("taxonomy_identity_mismatch")
    if (criteria_id, criteria_version) != (
        expected_criteria_id,
        expected_criteria_version,
    ):
        raise ValueError("criteria_identity_mismatch")

    fixture_identity = {
        str(item["fixture_id"]): str(item["sha256"]) for item in fixtures
    }
    expectation_identity = {
        str(item["fixture_id"]): str(item["sha256"]) for item in expectations
    }
    if fixture_identity != expectation_identity:
        raise ValueError("expectation_fixture_mismatch")


def compare_model_metrics(
    *,
    model: str,
    fixture_id: str,
    selected_ids: Sequence[str],
    supported_ids: Iterable[str],
    expected_ids: Iterable[str],
    statement_refs: Mapping[str, Sequence[str]],
    grounding: float = 1.0,
    unknown_ids: int = 0,
    dangling_refs: int = 0,
    duplicates: int = 0,
) -> dict[str, Any]:
    """Score one model/CV result while retaining safe evidence references."""
    selected = list(selected_ids)
    supported = set(supported_ids)
    expected = set(expected_ids)
    selected_supported = [item for item in selected if item in supported]
    selected_count = len(selected)
    supported_count = len(selected_supported)
    precision = supported_count / selected_count if selected_count else 0.0
    recall = len(set(selected_supported) & expected) / len(expected) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "model": model,
        "fixture_id": fixture_id,
        "selected_count": selected_count,
        "supported_count": supported_count,
        "unsupported_count": selected_count - supported_count,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "grounding": grounding,
        "unknown_ids": unknown_ids,
        "dangling_refs": dangling_refs,
        "duplicates": duplicates,
        "selected_capability_ids": selected,
        "supporting_statement_ids": {
            capability_id: list(statement_refs.get(capability_id, ()))
            for capability_id in selected
        },
    }


def choose_flash_candidate(records: Sequence[Mapping[str, Any]]) -> str | None:
    """Choose the best passing model using the locked quality ordering."""
    passing = [
        record
        for record in records
        if float(record["mean_precision"]) >= QUALITY_PRECISION
        and float(record["mean_recall"]) >= QUALITY_RECALL
        and float(record.get("grounding", 1.0)) >= QUALITY_GROUNDING
        and int(record.get("unknown_ids", 0)) == 0
        and int(record.get("dangling_refs", 0)) == 0
    ]
    if not passing:
        return None
    winner = min(
        passing,
        key=lambda record: (
            -float(record["mean_precision"]),
            -float(record["mean_recall"]),
            -float(record["mean_f1"]),
            -float(record.get("sales_precision", 0.0)),
            float(record.get("mean_latency_ms", 0.0)),
        ),
    )
    return str(winner["model"])
