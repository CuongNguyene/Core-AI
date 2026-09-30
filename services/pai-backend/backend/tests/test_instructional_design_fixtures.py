from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.quality_gate import evaluate_instructional_design
from app.instructional_design.schemas import ResearchProvenanceType


def test_three_domain_diverse_research_fixtures_are_explicitly_research_only() -> None:
    fixtures = research_fixture_bundles()

    assert set(fixtures) == {
        "model_monitoring",
        "python_data_processing",
        "technical_communication",
    }
    assert {bundle.brief.capability.name for bundle in fixtures.values()} == {
        "model monitoring response",
        "python data processing",
        "technical communication",
    }
    assert all(
        bundle.brief.provenance.type is ResearchProvenanceType.RESEARCH_FIXTURE
        for bundle in fixtures.values()
    )
    assert all(bundle.snapshot.quality_report.passed is True for bundle in fixtures.values())


def test_fixtures_have_reproducible_deterministic_quality_reports() -> None:
    for bundle in research_fixture_bundles().values():
        first = evaluate_instructional_design(
            brief=bundle.brief,
            objectives=bundle.objectives,
            assessments=bundle.assessments,
            prerequisites=bundle.prerequisites,
            course_outline=bundle.course_outline,
            lessons=bundle.lessons,
        )
        second = evaluate_instructional_design(
            brief=bundle.brief,
            objectives=bundle.objectives,
            assessments=bundle.assessments,
            prerequisites=bundle.prerequisites,
            course_outline=bundle.course_outline,
            lessons=bundle.lessons,
        )

        assert first == second == bundle.snapshot.quality_report
        assert bundle.snapshot.generation_provenance.provider == "research-fixture"
