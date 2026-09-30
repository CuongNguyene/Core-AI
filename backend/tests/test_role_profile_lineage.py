from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.documents.schemas import DocumentKind, DocumentStatus, StoredDocument
from app.extraction.schemas import (
    DocumentKind as ExtractionDocumentKind,
    EvidenceStatus,
    EvidenceType,
    ExtractedClaim,
    ExtractionProfile,
    JDExtractionOutput,
    ReviewState,
    SourceLocator,
)
from app.matching.schemas import RoleCompetencyProfile
from app.role_profile_authoring.schemas import RoleProfileDraft
from app.role_registry.schemas import Role, RoleJDVersion, RoleStatus


ORG = UUID("00000000-0000-0000-0000-000000000001")
ACTOR = UUID("11111111-1111-4111-8111-111111111111")
ROLE_ID = UUID("22222222-2222-4222-8222-222222222222")
JD_VERSION_ID = UUID("33333333-3333-4333-8333-333333333333")
DOCUMENT_ID = UUID("44444444-4444-4444-8444-444444444444")


def role() -> Role:
    now = datetime.now(UTC)
    return Role(
        id=ROLE_ID,
        organization_id=ORG,
        role_code="ROLE-000001",
        title="Engineer",
        created_by=ACTOR,
        created_at=now,
        updated_at=now,
    )


def jd_version(*, role_id: UUID = ROLE_ID, document_id: UUID = DOCUMENT_ID) -> RoleJDVersion:
    return RoleJDVersion(
        id=JD_VERSION_ID,
        role_jd_id=uuid4(),
        role_id=role_id,
        version=1,
        document_id=document_id,
        created_by=ACTOR,
        created_at=datetime.now(UTC),
    )


def source_profile(*, document_id: str = str(DOCUMENT_ID)) -> ExtractionProfile:
    claim = ExtractedClaim(
        value="Python",
        evidence_type=EvidenceType.EXPLICIT_SKILL,
        confidence=0.9,
        evidence_status=EvidenceStatus.SUPPORTED,
        source_locator=SourceLocator(
            document_id=document_id, section="skills", start_offset=0, end_offset=6
        ),
        source_excerpt="Python",
    )
    return ExtractionProfile(
        id="jd-profile-1",
        job_id="job-1",
        document_id=document_id,
        document_kind=ExtractionDocumentKind.JD,
        owner_actor_id=ACTOR,
        version=1,
        review_state=ReviewState.ACCEPTED,
        accepted_by=ACTOR,
        accepted_at=datetime.now(UTC),
        output=JDExtractionOutput(required_skills=[claim], responsibilities=[], qualifications=[]),
        audit={"provider": "test"},
    )


def document(*, organization_id: UUID = ORG, document_id: UUID = DOCUMENT_ID) -> StoredDocument:
    return StoredDocument(
        id=document_id,
        owner_actor_id=ACTOR,
        organization_id=organization_id,
        kind=DocumentKind.JD,
        content_type="application/pdf",
        byte_size=10,
        sha256="a" * 64,
        object_key=f"jd/{document_id}.pdf",
        status=DocumentStatus.CLEAN,
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )


def test_new_lineage_fields_are_nullable_compatibility_fields() -> None:
    assert RoleProfileDraft.model_fields["role_id"].is_required() is False
    assert RoleProfileDraft.model_fields["role_jd_version_id"].is_required() is False
    assert RoleCompetencyProfile.model_fields["role_id"].is_required() is False
    assert RoleCompetencyProfile.model_fields["role_jd_version_id"].is_required() is False


def test_exact_role_jd_document_lineage_is_accepted() -> None:
    from app.role_profile_authoring.lineage import validate_role_jd_lineage

    validate_role_jd_lineage(
        role=role(),
        jd_version=jd_version(),
        source_profile=source_profile(),
        document=document(),
        organization_id=ORG,
    )


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"document_id": str(uuid4())}, "document"),
        ({"role_id": uuid4()}, "role"),
    ],
)
def test_lineage_mismatch_fails_closed(kwargs: dict[str, object], message: str) -> None:
    from app.role_profile_authoring.lineage import validate_role_jd_lineage

    with pytest.raises(ValueError, match=message):
        validate_role_jd_lineage(
            role=role(),
            jd_version=jd_version(**kwargs),
            source_profile=source_profile(),
            document=document(),
            organization_id=ORG,
        )


def test_cross_organization_lineage_fails_closed() -> None:
    from app.role_profile_authoring.lineage import validate_role_jd_lineage

    with pytest.raises(ValueError, match="organization"):
        validate_role_jd_lineage(
            role=role(),
            jd_version=jd_version(),
            source_profile=source_profile(),
            document=document(organization_id=UUID("00000000-0000-0000-0000-000000000002")),
            organization_id=ORG,
        )
