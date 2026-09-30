import pytest

from app.extraction.capability_projection import (
    aggregate_capabilities,
    bind_v2_document_evidence,
    project_v2_to_legacy,
    validate_v2_document_evidence,
)
from app.extraction.locators import SourceLocator
from app.extraction.schemas import (
    CapabilityEvidence,
    CapabilityItem,
    CVFullExtractionOutputV2,
    EvidenceStrength,
    ExperienceItem,
    NativePdfLocator,
)


def ev(text: str, start: int, strength: EvidenceStrength) -> CapabilityEvidence:
    return CapabilityEvidence(
        source_excerpt=text,
        source_locator=SourceLocator(
            document_id="cv-1", section="experience", start_offset=start, end_offset=start + len(text)
        ),
        evidence_strength=strength,
        confidence=0.9,
    )


def test_aggregation_keeps_one_capability_and_promotes_distinct_experiences() -> None:
    items = [
        CapabilityItem(
            raw_name="Project Development & Management",
            canonical_name="Project Management",
            supporting_experience_refs=["exp-1"],
            evidence=[ev("managed delivery", 0, EvidenceStrength.DEMONSTRATED_IN_ROLE)],
        ),
        CapabilityItem(
            raw_name="Project Management",
            canonical_name="Project Management",
            supporting_experience_refs=["exp-2"],
            evidence=[ev("led project delivery", 30, EvidenceStrength.DEMONSTRATED_WITH_OUTCOME)],
        ),
    ]

    result = aggregate_capabilities(items)

    assert len(result) == 1
    assert result[0].canonical_name == "Project Management"
    assert len(result[0].evidence) == 2
    assert result[0].evidence_strength is EvidenceStrength.MULTIPLE_SUPPORTING_EXPERIENCES


def test_legacy_projection_does_not_replace_the_v2_evidence_collection() -> None:
    capability = CapabilityItem(
        raw_name="Project Management",
        canonical_name="Project Management",
        supporting_experience_refs=["exp-1", "exp-2", "exp-3"],
        evidence=[
            ev("planned projects", 0, EvidenceStrength.DEMONSTRATED_IN_ROLE),
            ev("delivered projects", 30, EvidenceStrength.DEMONSTRATED_WITH_OUTCOME),
            ev("managed projects", 60, EvidenceStrength.DEMONSTRATED_IN_ROLE),
        ],
    )
    output = CVFullExtractionOutputV2(
        capabilities=[capability],
        experience=[ExperienceItem(title="Project Director")],
    )

    legacy = project_v2_to_legacy(output)

    assert len(output.capabilities[0].evidence) == 3
    assert [claim.value for claim in legacy.skills] == ["Project Management"]
    assert len(legacy.skills[0].evidence) == 3


def test_title_only_experience_is_projected_as_role_not_capability() -> None:
    output = CVFullExtractionOutputV2(
        experience=[
            ExperienceItem(
                title="Senior Project Director",
                evidence=[ev("Senior Project Director", 0, EvidenceStrength.EXPLICIT_MENTION)],
            )
        ]
    )

    legacy = project_v2_to_legacy(output)

    assert [claim.value for claim in legacy.experience] == ["Senior Project Director"]
    assert legacy.skills == []


def test_native_pdf_locator_requires_page_and_document_identity() -> None:
    output = CVFullExtractionOutputV2(
        capabilities=[
            CapabilityItem(
                raw_name="Python",
                canonical_name="Python",
                evidence=[
                    CapabilityEvidence(
                        source_excerpt="Built APIs",
                        source_locator=NativePdfLocator(
                            document_id="cv-1", page_number=2, section="experience"
                        ),
                        evidence_strength=EvidenceStrength.DEMONSTRATED_IN_ROLE,
                    )
                ],
            )
        ]
    )

    validate_v2_document_evidence(
        output, "unused parsed support", page_count=2, expected_document_id="cv-1"
    )
    with pytest.raises(ValueError, match="locator_document_id_mismatch"):
        validate_v2_document_evidence(
            output, "unused parsed support", page_count=2, expected_document_id="other"
        )


def test_v2_evidence_binding_resolves_provider_whitespace_and_offsets() -> None:
    document = "Experience\nBuilt Python APIs for internal systems."
    output = CVFullExtractionOutputV2(
        capabilities=[
            CapabilityItem(
                raw_name="Python",
                canonical_name="Python",
                evidence=[
                    CapabilityEvidence(
                        source_excerpt="Built Python  APIs for internal systems.",
                        source_locator=SourceLocator(
                            document_id="provider-placeholder",
                            section="experience",
                            start_offset=0,
                            end_offset=1,
                        ),
                        evidence_strength=EvidenceStrength.DEMONSTRATED_IN_ROLE,
                    )
                ],
            )
        ]
    )

    normalized = bind_v2_document_evidence(output, document_id="cv-1", document=document)

    validate_v2_document_evidence(normalized, document, expected_document_id="cv-1")
    evidence = normalized.capabilities[0].evidence[0]
    assert evidence.source_excerpt == "Built Python APIs for internal systems."
    assert evidence.source_locator.document_id == "cv-1"
    assert (evidence.source_locator.start_offset, evidence.source_locator.end_offset) == (11, 50)
