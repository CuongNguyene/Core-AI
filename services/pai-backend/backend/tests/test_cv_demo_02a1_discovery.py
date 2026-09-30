import pytest
from pydantic import ValidationError

from app.extraction.capability_discovery import (
    CapabilityDiscoveryCandidate,
    CapabilityDiscoveryOutput,
    CapabilityMappingStatus,
    canonicalize_capabilities,
)
from app.extraction.capability_taxonomy import TAXONOMY_ID, TAXONOMY_VERSION
from app.extraction.schemas import CVFullExtractionOutputV2
from app.extraction.two_stage_capability_schema import (
    ExperimentalCvFacts,
    ExperimentalExperienceFact,
    ExperimentalStatement,
    ExperimentalToolFact,
)
from app.extraction.two_stage_composer import compose_discovered_output


def _facts() -> ExperimentalCvFacts:
    return ExperimentalCvFacts(
        document_id="doc-1",
        experiences=[
            ExperimentalExperienceFact(
                experience_id="exp-1",
                role="Talent Acquisition Specialist",
                statements=[
                    ExperimentalStatement(
                        statement_id="s1",
                        text="Managed end-to-end recruitment and candidate sourcing.",
                        document_id="doc-1",
                        page_number=1,
                    ),
                    ExperimentalStatement(
                        statement_id="s2",
                        text="Built employer branding campaigns.",
                        document_id="doc-1",
                        page_number=1,
                    ),
                ],
            )
        ],
    )


def test_discovery_requires_grounded_statement_refs() -> None:
    with pytest.raises(ValidationError):
        CapabilityDiscoveryCandidate(raw_name="Talent Acquisition", supporting_statement_ids=[])


def test_unknown_discovery_statement_ref_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown_statement_ref"):
        canonicalize_capabilities(
            CapabilityDiscoveryOutput(
                capabilities=[
                    {"raw_name": "Talent Acquisition", "supporting_statement_ids": ["missing"]}
                ]
            ),
            _facts(),
        )


def test_known_capability_maps_and_unknown_capability_is_preserved() -> None:
    result = canonicalize_capabilities(
        CapabilityDiscoveryOutput(
            capabilities=[
                {"raw_name": "Project Management", "supporting_statement_ids": ["s1"]},
                {"raw_name": "Talent Acquisition", "supporting_statement_ids": ["s1"]},
                {"raw_name": "Employer Branding", "supporting_statement_ids": ["s2"]},
            ]
        ),
        _facts(),
    )
    assert [(item.raw_name, item.status, item.canonical_capability_id) for item in result] == [
        ("Project Management", CapabilityMappingStatus.MAPPED, "project_management"),
        ("Talent Acquisition", CapabilityMappingStatus.UNMAPPED_BUT_GROUNDED, None),
        ("Employer Branding", CapabilityMappingStatus.UNMAPPED_BUT_GROUNDED, None),
    ]


def test_duplicate_discovery_names_merge_refs_deterministically() -> None:
    result = canonicalize_capabilities(
        CapabilityDiscoveryOutput(
            capabilities=[
                {"raw_name": "Talent Acquisition", "supporting_statement_ids": ["s2", "s1"]},
                {"raw_name": " talent   acquisition ", "supporting_statement_ids": ["s1"]},
            ]
        ),
        _facts(),
    )
    assert len(result) == 1
    assert result[0].supporting_statement_ids == ["s2", "s1"]


def test_title_only_and_tool_only_candidates_are_rejected() -> None:
    facts = _facts().model_copy(
        update={"tools_platforms": [ExperimentalToolFact(name="Excel", supporting_statement_ids=["s1"])]}
    )
    result = canonicalize_capabilities(
        CapabilityDiscoveryOutput(
            capabilities=[
                {"raw_name": "Talent Acquisition Specialist", "supporting_statement_ids": ["s1"]},
                {"raw_name": "Excel", "supporting_statement_ids": ["s1"]},
            ]
        ),
        facts,
    )
    assert result == []


def test_discovered_capabilities_compose_into_valid_v2_without_fabricating_evidence() -> None:
    mapped = canonicalize_capabilities(
        CapabilityDiscoveryOutput(
            capabilities=[
                {"raw_name": "Project Management", "supporting_statement_ids": ["s1"]},
                {"raw_name": "Talent Acquisition", "supporting_statement_ids": ["s1", "s2"]},
            ]
        ),
        _facts(),
    )
    output = compose_discovered_output(_facts(), mapped, page_count=1)
    assert isinstance(output, CVFullExtractionOutputV2)
    assert [(item.raw_name, item.mapping_status) for item in output.capabilities] == [
        ("Project Management", "mapped"),
        ("Talent Acquisition", "unmapped_but_grounded"),
    ]
    assert all(item.evidence for item in output.capabilities)
    assert output.capabilities[1].canonical_name == "Talent Acquisition"


def test_taxonomy_identity_remains_bound_to_current_registry() -> None:
    assert TAXONOMY_ID == "professional_capability_core"
    assert TAXONOMY_VERSION == "0.1"
