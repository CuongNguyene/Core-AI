import pytest

from app.extraction.ext_03a7_evaluation import (
    CVEvaluation,
    FixtureSpec,
    TaxonomyGap,
    aggregate_domain_summary,
    build_manifest,
    calculate_selection_metrics,
)


def fixture(name: str, sha: str) -> FixtureSpec:
    return FixtureSpec(fixture_id=name, sha256=sha, domain="technical", mime_type="application/pdf", input_mode="native_pdf", page_count=2)


def test_manifest_binds_taxonomy_and_rejects_duplicate_fixture_or_sha() -> None:
    manifest = build_manifest("professional_capability_core", "0.1", [fixture("a", "sha-a")])
    assert manifest.taxonomy_id == "professional_capability_core"
    assert manifest.taxonomy_version == "0.1"
    with pytest.raises(ValueError, match="duplicate_fixture_id"):
        build_manifest("professional_capability_core", "0.1", [fixture("a", "sha-a"), fixture("a", "sha-b")])
    with pytest.raises(ValueError, match="duplicate_sha256"):
        build_manifest("professional_capability_core", "0.1", [fixture("a", "sha-a"), fixture("b", "sha-a")])


def test_selection_precision_and_bounded_recall_use_independent_expectations() -> None:
    metrics = calculate_selection_metrics(
        selected_ids=["project_management", "team_leadership", "ecommerce"],
        supported_selected_ids=["project_management", "team_leadership"],
        expected_supported_ids=["project_management", "team_leadership", "process_optimization"],
        demonstrated_capability_count=4,
        represented_capability_count=3,
    )
    assert metrics["selection_precision"] == pytest.approx(2 / 3)
    assert metrics["bounded_recall"] == pytest.approx(2 / 3)
    assert metrics["taxonomy_coverage"] == pytest.approx(3 / 4)


def test_domain_summary_and_gap_aggregation_are_deterministic() -> None:
    records = [
        CVEvaluation(fixture_id="a", domain="technical", selection_precision=1.0, bounded_recall=0.5, taxonomy_coverage=0.25, taxonomy_gaps=[TaxonomyGap(proposed_name="Backend Development", domain="technical")]),
        CVEvaluation(fixture_id="b", domain="technical", selection_precision=0.5, bounded_recall=1.0, taxonomy_coverage=0.5, taxonomy_gaps=[TaxonomyGap(proposed_name="Backend Development", domain="technical")]),
    ]
    summary = aggregate_domain_summary(records)
    assert summary["technical"]["cv_count"] == 2
    assert summary["technical"]["mean_selection_precision"] == pytest.approx(0.75)
    assert summary["technical"]["top_taxonomy_gaps"][0]["proposed_name"] == "Backend Development"
    assert summary["technical"]["top_taxonomy_gaps"][0]["fixture_count"] == 2
