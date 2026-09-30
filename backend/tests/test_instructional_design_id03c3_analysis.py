from pathlib import Path

from app.instructional_design.id03c3_analysis import (
    RUBRIC_DIMENSIONS,
    analyze,
    write_analysis,
)

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "test/results/instructional-design-id-03c2-completion-merge"


def test_id03c3_accepts_only_ten_canonical_reviews_and_preserves_dimensions() -> None:
    result = analyze(SOURCE)
    assert result["integrity"]["analysis_allowed"] is True
    assert len(result["rows"]) == 10
    assert set(result["rubric"]) == set(RUBRIC_DIMENSIONS)
    assert all(item["count"] == 10 for item in result["rubric"].values())
    assert result["agreement"]["exact_agreement_count"] >= 0


def test_id03c3_machine_and_human_axes_are_separate() -> None:
    result = analyze(SOURCE)
    assert {item["category"] for item in result["machine"]} <= {"A", "B", "C", "D"}
    assert result["integrity"]["canonical_reviews"] == 10


def test_id03c3_writes_required_artifacts_without_composite_winner(tmp_path: Path) -> None:
    write_analysis(SOURCE, tmp_path)
    required = {
        "manifest.json", "dataset-integrity.json", "rubric-summary.json", "domain-analysis.json",
        "reviewer-agreement.json", "special-question-analysis.json", "edit-effort-analysis.json",
        "prerequisite-analysis.json", "thematic-analysis.json", "machine-human-analysis.json",
        "sme-analysis-report.json", "validation-report.json",
    }
    assert required <= {p.name for p in tmp_path.iterdir()}
    report = (tmp_path / "validation-report.json").read_text()
    assert '"composite_winner": false' in report
