from uuid import UUID

from app.documents.schemas import StoredDocument
from app.extraction.schemas import ExtractionProfile
from app.role_registry.schemas import Role, RoleJDVersion


def validate_role_jd_lineage(
    *,
    role: Role,
    jd_version: RoleJDVersion,
    source_profile: ExtractionProfile,
    document: StoredDocument,
    organization_id: UUID,
) -> None:
    """Validate the exact source chain used by a new role-aware draft."""
    if role.organization_id != organization_id:
        raise ValueError("role organization does not match actor organization")
    if jd_version.role_id != role.id:
        raise ValueError("JD version belongs to a different role")
    if jd_version.document_id != document.id:
        raise ValueError("JD version document does not match source document")
    if source_profile.document_id != str(document.id):
        raise ValueError("source extraction document does not match JD version document")
    if document.organization_id != organization_id:
        raise ValueError("source document organization does not match actor organization")
    if source_profile.document_kind.value != "jd":
        raise ValueError("source extraction profile is not a JD")
