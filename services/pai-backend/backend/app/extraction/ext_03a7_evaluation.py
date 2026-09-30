"""Deterministic evaluation mechanics for EXT-03A.7 multi-CV runs."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FixtureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fixture_id: str = Field(min_length=1)
    sha256: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    mime_type: str = Field(min_length=1)
    input_mode: str = Field(min_length=1)
    page_count: int = Field(ge=1)


class EvaluationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: str = Field(min_length=1)
    taxonomy_id: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    fixtures: tuple[FixtureSpec, ...] = Field(min_length=1)


def build_manifest(taxonomy_id: str, taxonomy_version: str, fixtures: list[FixtureSpec]) -> EvaluationManifest:
    ids = [item.fixture_id for item in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_fixture_id")
    hashes = [item.sha256 for item in fixtures]
    if len(hashes) != len(set(hashes)):
        raise ValueError("duplicate_sha256")
    return EvaluationManifest(
        experiment_id="EXT-03A.7",
        taxonomy_id=taxonomy_id,
        taxonomy_version=taxonomy_version,
        fixtures=tuple(fixtures),
    )


def calculate_selection_metrics(
    *,
    selected_ids: list[str],
    supported_selected_ids: list[str],
    expected_supported_ids: list[str],
    demonstrated_capability_count: int,
    represented_capability_count: int,
) -> dict[str, float | int]:
    selected = len(selected_ids)
    supported = len(supported_selected_ids)
    expected = len(expected_supported_ids)
    return {
        "selected_count": selected,
        "supported_selected_count": supported,
        "unsupported_selected_count": selected - supported,
        "selection_precision": supported / selected if selected else 0.0,
        "bounded_recall": len(set(supported_selected_ids) & set(expected_supported_ids)) / expected if expected else 0.0,
        "demonstrated_capability_count": demonstrated_capability_count,
        "represented_capability_count": represented_capability_count,
        "taxonomy_gap_count": demonstrated_capability_count - represented_capability_count,
        "taxonomy_coverage": represented_capability_count / demonstrated_capability_count if demonstrated_capability_count else 0.0,
    }


class TaxonomyGap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    proposed_name: str = Field(min_length=1)
    domain: str = Field(min_length=1)


@dataclass(frozen=True)
class CVEvaluation:
    fixture_id: str
    domain: str
    selection_precision: float
    bounded_recall: float
    taxonomy_coverage: float
    taxonomy_gaps: list[TaxonomyGap] = field(default_factory=list)


def aggregate_domain_summary(records: list[CVEvaluation]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[CVEvaluation]] = defaultdict(list)
    for record in records:
        grouped[record.domain].append(record)
    result: dict[str, dict[str, Any]] = {}
    for domain, items in sorted(grouped.items()):
        gaps: dict[str, set[str]] = defaultdict(set)
        for item in items:
            for gap in item.taxonomy_gaps:
                gaps[gap.proposed_name].add(item.fixture_id)
        top_gaps = [
            {"proposed_name": name, "fixture_count": len(fixture_ids)}
            for name, fixture_ids in sorted(gaps.items(), key=lambda pair: (-len(pair[1]), pair[0]))
        ]
        result[domain] = {
            "cv_count": len(items),
            "mean_selection_precision": sum(item.selection_precision for item in items) / len(items),
            "mean_bounded_recall": sum(item.bounded_recall for item in items) / len(items),
            "mean_taxonomy_coverage": sum(item.taxonomy_coverage for item in items) / len(items),
            "top_taxonomy_gaps": top_gaps,
        }
    return result
