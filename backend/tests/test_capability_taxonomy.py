import pytest

from app.extraction.capability_taxonomy import (
    TAXONOMY_ID,
    TAXONOMY_VERSION,
    CapabilityTaxonomy,
    TaxonomySelectedCapability,
    TaxonomySelection,
    get_taxonomy,
    merge_taxonomy_selections,
    validate_taxonomy_selection,
)
from app.extraction.two_stage_capability_schema import (
    ExperimentalCvFacts,
    ExperimentalExperienceFact,
    ExperimentalStatement,
)


def facts() -> ExperimentalCvFacts:
    return ExperimentalCvFacts(
        document_id="doc-1",
        experiences=[
            ExperimentalExperienceFact(
                experience_id="exp-1",
                role="Engineer",
                statements=[
                    ExperimentalStatement(
                        statement_id="s1", text="Planned delivery work.", document_id="doc-1", page_number=1
                    ),
                    ExperimentalStatement(
                        statement_id="s2", text="Led a team.", document_id="doc-1", page_number=1
                    ),
                ],
            )
        ],
    )


def test_static_taxonomy_has_stable_ids_and_version() -> None:
    taxonomy = get_taxonomy(TAXONOMY_ID, TAXONOMY_VERSION)
    assert isinstance(taxonomy, CapabilityTaxonomy)
    assert taxonomy.taxonomy_id == "professional_capability_core"
    assert taxonomy.version == "0.1"
    assert all(item.id and item.name for item in taxonomy.capabilities)


def test_unknown_taxonomy_or_version_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown_taxonomy"):
        get_taxonomy("unknown", TAXONOMY_VERSION)
    with pytest.raises(ValueError, match="taxonomy_version_mismatch"):
        get_taxonomy(TAXONOMY_ID, "9.9")


def test_selection_requires_known_ids_and_matching_taxonomy_identity() -> None:
    selection = TaxonomySelection(
        taxonomy_id=TAXONOMY_ID,
        taxonomy_version=TAXONOMY_VERSION,
        capabilities=[TaxonomySelectedCapability(capability_id="project_management", supporting_statement_ids=["s1"])],
    )
    validate_taxonomy_selection(selection, facts())
    with pytest.raises(ValueError, match="unknown_capability_id"):
        validate_taxonomy_selection(selection.model_copy(update={"capabilities": [TaxonomySelectedCapability(capability_id="unknown", supporting_statement_ids=["s1"])]}), facts())
    with pytest.raises(ValueError, match="taxonomy_version_mismatch"):
        validate_taxonomy_selection(selection.model_copy(update={"taxonomy_version": "9.9"}), facts())


def test_duplicate_ids_merge_refs_in_first_seen_order() -> None:
    selection = TaxonomySelection(
        taxonomy_id=TAXONOMY_ID,
        taxonomy_version=TAXONOMY_VERSION,
        capabilities=[
            {"capability_id": "project_management", "supporting_statement_ids": ["s2", "s1"]},
            {"capability_id": "project_management", "supporting_statement_ids": ["s1"]},
        ],
    )
    merged = merge_taxonomy_selections(selection)
    assert [item.capability_id for item in merged.capabilities] == ["project_management"]
    assert merged.capabilities[0].supporting_statement_ids == ["s2", "s1"]


def test_taxonomy_identity_is_recordable_in_result_artifact() -> None:
    selection = TaxonomySelection(
        taxonomy_id=TAXONOMY_ID,
        taxonomy_version=TAXONOMY_VERSION,
        capabilities=[],
    )
    assert selection.model_dump(mode="json")["taxonomy_id"] == TAXONOMY_ID
    assert selection.model_dump(mode="json")["taxonomy_version"] == TAXONOMY_VERSION
