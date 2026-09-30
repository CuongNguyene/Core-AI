import pytest
from pydantic import ValidationError

from app.extraction.locators import SourceLocator
from app.extraction.schemas import (
    CapabilityEvidence,
    CapabilityItem,
    CVFullExtractionOutputV2,
    EducationItem,
    EvidenceStrength,
    ExperienceItem,
    ToolPlatformItem,
)


def locator(start: int = 0, end: int = 20) -> SourceLocator:
    return SourceLocator(
        document_id="cv-1", section="experience", start_offset=start, end_offset=end
    )


def evidence(text: str = "Planned and executed project delivery.") -> CapabilityEvidence:
    return CapabilityEvidence(
        source_excerpt=text,
        source_locator=locator(),
        evidence_strength=EvidenceStrength.DEMONSTRATED_IN_ROLE,
    )


def test_v2_keeps_raw_and_deterministic_canonical_capability_names() -> None:
    item = CapabilityItem(
        raw_name="Project Development & Management",
        canonical_name="Project Management",
        evidence=[evidence()],
    )

    assert item.raw_name != item.canonical_name
    assert item.evidence[0].source_excerpt.startswith("Planned")


def test_v2_rejects_capability_without_grounded_evidence() -> None:
    with pytest.raises(ValidationError):
        CapabilityItem(
            raw_name="Advanced Cloud Architecture",
            canonical_name="Advanced Cloud Architecture",
            evidence=[],
        )


def test_v2_separates_experience_tools_and_structured_education() -> None:
    output = CVFullExtractionOutputV2(
        candidate_summary="Evidence-based summary",
        experience=[ExperienceItem(title="Senior Project Director", evidence=[evidence()])],
        capabilities=[
            CapabilityItem(
                raw_name="Project Management",
                canonical_name="Project Management",
                evidence=[evidence()],
            )
        ],
        tools_platforms=[ToolPlatformItem(name="SAP", evidence=[evidence("SAP")])],
        education=[
            EducationItem(
                degree="MBA",
                field="eCommerce",
                institution="Institute of Business Management",
                location="Singapore",
                year=2012,
                evidence=[evidence("2012: MBA of eCommerce")],
            )
        ],
    )

    assert output.experience[0].title == "Senior Project Director"
    assert output.capabilities[0].canonical_name == "Project Management"
    assert output.tools_platforms[0].name == "SAP"
    assert output.education[0].year == 2012


def test_v2_evidence_strength_is_not_proficiency() -> None:
    assert {item.value for item in EvidenceStrength} == {
        "explicit_mention",
        "demonstrated_in_role",
        "demonstrated_with_outcome",
        "multiple_supporting_experiences",
    }
