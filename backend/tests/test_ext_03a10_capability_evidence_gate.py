import pytest

from app.extraction.capability_evidence_gate import (
    GateIntegrityError,
    apply_capability_evidence_gate,
    build_gate_set,
    calculate_replay_metrics,
    gate_capability,
)
from app.extraction.capability_taxonomy import TaxonomySelectedCapability, TaxonomySelection
from app.extraction.two_stage_capability_schema import (
    ExperimentalCvFacts,
    ExperimentalExperienceFact,
    ExperimentalStatement,
)


def facts(*statements: str) -> ExperimentalCvFacts:
    return ExperimentalCvFacts(
        document_id="doc-1",
        experiences=[
            ExperimentalExperienceFact(
                experience_id="exp-1",
                role="Role",
                statements=[
                    ExperimentalStatement(
                        statement_id=f"stmt-{index}",
                        text=text,
                        document_id="doc-1",
                        page_number=1,
                    )
                    for index, text in enumerate(statements, start=1)
                ],
            )
        ],
    )


@pytest.mark.parametrize(
    ("capability_id", "text"),
    [
        ("team_leadership", "Managed a team of 8 direct reports."),
        ("warehouse_management", "Managed warehouse and inventory operations."),
        ("digital_platform_development", "Built and launched an eCommerce platform."),
        ("process_optimization", "Redesigned the workflow and reduced processing time."),
        ("product_management", "Owned the product roadmap and feature prioritization."),
        ("project_management", "Owned project planning, delivery, scope and timeline."),
    ],
)
def test_observed_direct_action_is_accepted(capability_id: str, text: str) -> None:
    decision = gate_capability(
        capability_id,
        ["stmt-1"],
        facts(text),
        build_gate_set(),
    )

    assert decision.accepted is True
    assert decision.reason_code in {"ACCEPT_DIRECT_ACTION", "ACCEPT_OWNERSHIP", "ACCEPT_OUTCOME"}
    assert decision.accepted_statement_ids == ["stmt-1"]


@pytest.mark.parametrize(
    ("capability_id", "text", "reason"),
    [
        ("team_leadership", "Legal Manager", "REJECT_TITLE_ONLY"),
        ("team_leadership", "Worked with cross-functional teams.", "REJECT_GENERIC_MANAGEMENT"),
        ("warehouse_management", "Managed sales and distribution channels.", "REJECT_DOMAIN_ASSOCIATION"),
        ("digital_platform_development", "Used Shopify for daily sales.", "REJECT_TOOL_ONLY"),
        ("process_optimization", "Responsible for daily process execution.", "REJECT_NO_DIRECT_EVIDENCE"),
        ("product_management", "Sold consumer products.", "REJECT_DOMAIN_ASSOCIATION"),
        ("project_management", "Participated in a project.", "REJECT_NO_DIRECT_EVIDENCE"),
    ],
)
def test_weak_context_is_rejected(capability_id: str, text: str, reason: str) -> None:
    decision = gate_capability(
        capability_id,
        ["stmt-1"],
        facts(text),
        build_gate_set(),
    )

    assert decision.accepted is False
    assert decision.reason_code == reason
    assert decision.rejected_statement_ids == ["stmt-1"]


def test_no_gate_passes_through_with_explicit_reason() -> None:
    decision = gate_capability(
        "order_management",
        ["stmt-1"],
        facts("Managed order processing and fulfillment."),
        build_gate_set(),
    )

    assert decision.accepted is True
    assert decision.reason_code == "NO_GATE_DEFINED"


def test_unknown_capability_fails_closed() -> None:
    with pytest.raises(GateIntegrityError, match="unknown_capability_id"):
        gate_capability("not-in-taxonomy", ["stmt-1"], facts("Anything."), build_gate_set())


def test_dangling_statement_reference_fails_closed() -> None:
    with pytest.raises(GateIntegrityError, match="unknown_statement_ref"):
        gate_capability("team_leadership", ["missing"], facts("Managed a team."), build_gate_set())


def test_taxonomy_mismatch_fails_closed() -> None:
    selection = TaxonomySelection(
        taxonomy_id="wrong-taxonomy",
        taxonomy_version="0.1",
        capabilities=[
            TaxonomySelectedCapability(
                capability_id="team_leadership", supporting_statement_ids=["stmt-1"]
            )
        ],
    )
    with pytest.raises(GateIntegrityError, match="taxonomy_mismatch"):
        apply_capability_evidence_gate(selection, facts("Managed a team."), build_gate_set())


def test_gate_applies_only_to_model_cited_refs() -> None:
    selection = TaxonomySelection(
        taxonomy_id="professional_capability_core",
        taxonomy_version="0.1",
        capabilities=[
            TaxonomySelectedCapability(
                capability_id="team_leadership", supporting_statement_ids=["stmt-1"]
            )
        ],
    )
    gated = apply_capability_evidence_gate(
        selection,
        facts("Worked with a team.", "Managed a team of 8."),
        build_gate_set(),
    )

    assert gated.accepted_capabilities == []
    assert gated.decisions[0].reason_code == "REJECT_GENERIC_MANAGEMENT"
    assert gated.decisions[0].rejected_statement_ids == ["stmt-1"]


def test_duplicate_selection_refs_are_merged_deterministically() -> None:
    selection = TaxonomySelection(
        taxonomy_id="professional_capability_core",
        taxonomy_version="0.1",
        capabilities=[
            TaxonomySelectedCapability(
                capability_id="team_leadership", supporting_statement_ids=["stmt-1"]
            ),
            TaxonomySelectedCapability(
                capability_id="team_leadership", supporting_statement_ids=["stmt-2", "stmt-1"]
            ),
        ],
    )
    gated = apply_capability_evidence_gate(
        selection,
        facts("Managed a team.", "Coached team members."),
        build_gate_set(),
    )

    assert gated.accepted_capabilities == ["team_leadership"]
    assert gated.decisions[0].accepted_statement_ids == ["stmt-1", "stmt-2"]


def test_replay_metrics_measure_before_and_after_selection() -> None:
    before = ["team_leadership", "project_management"]
    after = ["project_management"]

    metrics = calculate_replay_metrics(
        before_ids=before,
        after_ids=after,
        expected_ids=["project_management"],
    )

    assert metrics == {
        "before": {
            "selected": 2,
            "supported": 1,
            "unsupported": 1,
            "precision": 0.5,
            "recall": 1.0,
            "f1": 2 / 3,
        },
        "after": {
            "selected": 1,
            "supported": 1,
            "unsupported": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        },
    }
