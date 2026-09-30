import pytest

from app.extraction.ext_03a5_task_formulation import (
    CAPABILITY_FAMILIES,
    BoundedCapabilityDerivation,
    HybridCapability,
    HybridCapabilityDerivation,
    validate_bounded_capabilities,
    validate_hybrid_capabilities,
)
from app.extraction.two_stage_capability_schema import (
    ExperimentalCapabilityDerivation,
    ExperimentalCvFacts,
    ExperimentalExperienceFact,
    ExperimentalStatement,
)


def source() -> ExperimentalCvFacts:
    return ExperimentalCvFacts(
        document_id="doc-1",
        experiences=[
            ExperimentalExperienceFact(
                experience_id="exp-1",
                role="Engineer",
                statements=[
                    ExperimentalStatement(
                        statement_id="s1",
                        text="Managed warehouse, delivery, and order strategies.",
                        document_id="doc-1",
                        page_number=1,
                    )
                ],
            )
        ],
    )


def test_bounded_taxonomy_is_explicit_and_stable() -> None:
    assert CAPABILITY_FAMILIES == (
        "Project Management", "Product Management", "eCommerce",
        "Omnichannel Commerce", "Order Management", "Warehouse Management",
        "Delivery / Logistics Management", "Operations Planning",
        "Digital Platform Development", "Team Leadership", "Process Optimization",
    )


def test_bounded_formulation_rejects_unknown_family_and_dangling_ref() -> None:
    valid = BoundedCapabilityDerivation(capabilities=[{"family": "Order Management", "supporting_statement_ids": ["s1"]}])
    validate_bounded_capabilities(valid, source())
    with pytest.raises(ValueError, match="unknown_capability_family"):
        validate_bounded_capabilities(BoundedCapabilityDerivation(capabilities=[{"family": "Operations", "supporting_statement_ids": ["s1"]}]), source())
    with pytest.raises(ValueError, match="unknown_statement_ref"):
        validate_bounded_capabilities(BoundedCapabilityDerivation(capabilities=[{"family": "Order Management", "supporting_statement_ids": ["missing"]}]), source())


def test_hybrid_formulation_requires_bounded_mapping_and_grounding() -> None:
    valid = HybridCapabilityDerivation(capabilities=[HybridCapability(proposed_name="Operations Management", mapped_family="Operations Planning", supporting_statement_ids=["s1"])])
    validate_hybrid_capabilities(valid, source())
    with pytest.raises(ValueError, match="unknown_capability_family"):
        validate_hybrid_capabilities(HybridCapabilityDerivation(capabilities=[HybridCapability(proposed_name="Operations", mapped_family="Operations", supporting_statement_ids=["s1"])]), source())


def test_open_formulation_reuses_stage_two_reference_validation() -> None:
    output = ExperimentalCapabilityDerivation(capabilities=[{"name": "Operations Management", "supporting_statement_ids": ["s1"]}])
    assert output.capabilities[0].supporting_statement_ids == ["s1"]
