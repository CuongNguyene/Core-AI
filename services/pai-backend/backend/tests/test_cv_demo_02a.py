import pytest

from app.extraction.capability_taxonomy import (
    TaxonomySelectedCapability,
    TaxonomySelection,
)
from app.extraction.router import CvExtractionPipeline, choose_extraction_mode
from app.extraction.two_stage_capability_schema import (
    ExperimentalCvFacts,
    ExperimentalExperienceFact,
    ExperimentalStatement,
)
from app.extraction.two_stage_composer import compose_two_stage_output


def facts() -> ExperimentalCvFacts:
    return ExperimentalCvFacts(
        document_id="doc-1",
        experiences=[
            ExperimentalExperienceFact(
                experience_id="exp-1",
                role="Project Manager",
                statements=[
                    ExperimentalStatement(
                        statement_id="stmt-1",
                        text="Owned project planning and delivery.",
                        document_id="doc-1",
                        page_number=1,
                    )
                ],
            )
        ],
    )


def selection() -> TaxonomySelection:
    return TaxonomySelection(
        taxonomy_id="professional_capability_core",
        taxonomy_version="0.1",
        capabilities=[
            TaxonomySelectedCapability(
                capability_id="project_management",
                supporting_statement_ids=["stmt-1"],
            )
        ],
    )


def test_two_stage_is_not_limited_by_12k_cutoff() -> None:
    assert CvExtractionPipeline.TWO_STAGE.value == "two_stage"
    assert choose_extraction_mode("x" * 13_000).value == "section_based"


def test_composer_resolves_taxonomy_and_statement_to_native_evidence() -> None:
    output = compose_two_stage_output(facts(), selection(), page_count=1)

    capability = output.capabilities[0]
    assert capability.canonical_name == "Project Management"
    assert capability.evidence[0].source_excerpt == "Owned project planning and delivery."
    assert capability.evidence[0].source_locator.document_id == "doc-1"
    assert capability.supporting_experience_refs == ["exp-1"]


def test_composer_fails_closed_for_dangling_statement() -> None:
    invalid = selection().model_copy(
        update={
            "capabilities": [
                TaxonomySelectedCapability(
                    capability_id="project_management",
                    supporting_statement_ids=["missing"],
                )
            ]
        }
    )

    with pytest.raises(ValueError, match="unknown_statement_ref"):
        compose_two_stage_output(facts(), invalid, page_count=1)
