from uuid import UUID

import pytest

from app.extraction.jd_review_projection import build_jd_review_projection
from app.extraction.schemas import (
    DocumentKind,
    EvidenceStatus,
    ExtractionProfile,
    JDRequirementExtractionOutputV2,
    JDRequirementExtractionV2,
    JDRequirementModality,
    NativePdfLocator,
    ReviewState,
)

ACTOR_ID = UUID("00000000-0000-0000-0000-000000000004")


def _profile(*, locator: object, kind: DocumentKind = DocumentKind.JD) -> ExtractionProfile:
    output = JDRequirementExtractionOutputV2(
        requirements=[
            JDRequirementExtractionV2(
                requirement_id="req-responsibility",
                statement="May support onboarding of junior sales staff",
                criterion_dimension=None,
                modality=JDRequirementModality.RESPONSIBILITY,
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_locator=locator,
                source_excerpt="May support onboarding of junior sales staff",
            ),
            JDRequirementExtractionV2(
                requirement_id="req-credential",
                statement="PMP certification",
                criterion_dimension="credential",
                modality=JDRequirementModality.PREFERRED,
                confidence=0.8,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_locator=locator,
                source_excerpt="PMP certification",
            ),
            JDRequirementExtractionV2(
                requirement_id="req-scope",
                statement="Warehouse knowledge is not required",
                criterion_dimension=None,
                modality=JDRequirementModality.UNSPECIFIED,
                confidence=0.8,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_locator=locator,
                source_excerpt="Warehouse knowledge is not required",
            ),
        ]
    )
    return ExtractionProfile(
        id="profile-jd-1",
        job_id="job-jd-1",
        document_id="document-jd-1",
        document_kind=kind,
        owner_actor_id=ACTOR_ID,
        version=2,
        review_state=ReviewState.CORRECTED,
        output=output,
        audit={"schema_version": "2.2", "pipeline_mode": "two_stage", "unsafe": "omit"},
    )


def test_jd_review_projection_groups_semantics_and_keeps_version_scoped_ids() -> None:
    projection = build_jd_review_projection(
        _profile(
            locator=NativePdfLocator(document_id="document-jd-1", page_number=3),
        )
    )

    assert projection.profile_id == "profile-jd-1"
    assert projection.version == 2
    assert [group.key for group in projection.groups] == [
        "responsibilities",
        "preferred",
        "scope_exclusions",
    ]
    assert projection.requirement_count == 3
    item = projection.groups[0].items[0]
    assert item.modality == "responsibility"
    assert item.criterion_dimension is None
    assert item.review_item_id.startswith("profile-jd-1:v2:requirement:0:")
    assert item.evidence_location.kind == "pdf_page"
    assert item.evidence_location.display_label == "Page 3"
    assert item.evidence_location.page_number == 3
    assert projection.safe_metadata == {
        "pipeline_mode": "two_stage",
        "schema_version": "2.2",
    }


def test_jd_review_projection_normalizes_text_locator_without_exposing_class_name() -> None:
    from app.extraction.locators import SourceLocator

    projection = build_jd_review_projection(
        _profile(
            locator=SourceLocator(
                document_id="document-jd-1",
                section="requirements",
                start_offset=14,
                end_offset=30,
            )
        )
    )

    location = projection.requirements[0].evidence_location
    assert location.kind == "text_span"
    assert location.display_label == "JD text"
    assert location.start_offset == 14
    assert location.end_offset == 30
    assert "SourceLocator" not in location.model_dump_json()


def test_jd_review_projection_fails_closed_for_non_jd_profile() -> None:
    with pytest.raises(ValueError, match="JD extraction profile"):
        build_jd_review_projection(
            _profile(
                kind=DocumentKind.CV,
                locator=NativePdfLocator(document_id="document-jd-1", page_number=1),
            )
        )
