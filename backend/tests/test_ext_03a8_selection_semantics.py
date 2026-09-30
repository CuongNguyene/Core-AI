import pytest

from app.extraction.capability_taxonomy import TAXONOMY_ID, TAXONOMY_VERSION
from app.extraction.ext_03a8_selection_semantics import (
    CapabilitySelectionCriteria,
    CriteriaSet,
    calculate_selection_scores,
    strict_evidence_decision,
)


def test_direct_action_evidence_is_accepted_but_title_and_tool_only_are_rejected() -> None:
    assert strict_evidence_decision("Designed and implemented a digital platform.", "Digital Platform Development") is True
    assert strict_evidence_decision("Sales Manager", "Team Leadership") is False
    assert strict_evidence_decision("Used Shopify", "Digital Platform Development") is False
    assert strict_evidence_decision("Sold product packages", "Product Management") is False


def test_zero_capability_output_is_valid() -> None:
    scores = calculate_selection_scores([], [], [], 0, 0)
    assert scores["precision"] == 0.0
    assert scores["recall"] == 0.0
    assert scores["f1"] == 0.0


def test_scores_include_f1_and_use_same_expectations() -> None:
    scores = calculate_selection_scores(["a", "b"], ["a"], ["a", "c"], 3, 2)
    assert scores["precision"] == pytest.approx(0.5)
    assert scores["recall"] == pytest.approx(0.5)
    assert scores["f1"] == pytest.approx(0.5)


def test_criteria_must_bind_to_taxonomy_identity_and_known_capability() -> None:
    criteria = CriteriaSet(
        criteria_id="strict-evidence",
        version="0.1",
        taxonomy_id=TAXONOMY_ID,
        taxonomy_version=TAXONOMY_VERSION,
        criteria=(CapabilitySelectionCriteria(capability_id="project_management", positive_signals=("planned",), negative_signals=("title only",)),),
    )
    assert criteria.criteria[0].capability_id == "project_management"
    with pytest.raises(ValueError, match="unknown_criteria_capability"):
        CriteriaSet(criteria_id="bad", version="0.1", taxonomy_id=TAXONOMY_ID, taxonomy_version=TAXONOMY_VERSION, criteria=(CapabilitySelectionCriteria(capability_id="missing", positive_signals=("x",), negative_signals=("y",)),))
