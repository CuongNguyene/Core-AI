import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from app.candidate_source.schemas import CandidateSourceEnvelope
from app.extraction.profile import (
    CandidateProfile,
    CredentialEntity,
    EducationEntity,
    ExperienceEntity,
    ProjectEntity,
)


class CandidateSourceError(ValueError):
    """Stable candidate-source domain failure."""


@dataclass(frozen=True)
class OrganizationExternalMapping:
    source_system: str
    external_company_ref: str
    organization_id: UUID


def resolve_organization(
    mappings: list[OrganizationExternalMapping], *, source_system: str, external_company_ref: str
) -> UUID:
    found = [
        row.organization_id
        for row in mappings
        if row.source_system == source_system and row.external_company_ref == external_company_ref
    ]
    if len(found) != 1:
        raise CandidateSourceError(
            "organization_mapping_not_found" if not found else "organization_mapping_conflict"
        )
    return found[0]


def canonical_fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def snapshot_disposition(
    incoming_revision: int,
    incoming_content_fingerprint: str,
    *,
    current_revision: int | None,
    current_content_fingerprint: str | None,
) -> str:
    if current_revision is None:
        return "INITIAL"
    if incoming_revision > current_revision:
        return "NEWER"
    if incoming_revision < current_revision:
        raise CandidateSourceError("candidate_source_snapshot_stale")
    if current_content_fingerprint is None:
        raise CandidateSourceError("candidate_source_current_content_fingerprint_unavailable")
    if incoming_content_fingerprint == current_content_fingerprint:
        return "REPLAY"
    raise CandidateSourceError("candidate_source_snapshot_revision_conflict")


def source_content_fingerprint(envelope: CandidateSourceEnvelope) -> str:
    """Hash source content without revision or delivery/audit metadata."""
    payload = envelope.model_dump(mode="json")
    payload.pop("source_revision", None)
    payload.pop("source_snapshot", None)
    return canonical_fingerprint(payload)


def project_candidate_profile(envelope: CandidateSourceEnvelope) -> CandidateProfile:
    """Map only explicit structural fields; source assertions are not capabilities."""
    return CandidateProfile(
        employment_history=[
            ExperienceEntity(
                name=_join(row.role, row.company) or row.role or row.company or "Employment",
                role=row.role,
                organization=row.company,
            )
            for row in envelope.career_history
            if row.role or row.company
        ],
        education=[
            EducationEntity(
                institution=row.institution or "Unspecified institution",
                degree=row.degree,
                field=row.field,
            )
            for row in envelope.education
            if row.institution or row.degree or row.field
        ],
        credentials=[
            CredentialEntity(name=row.name) for row in envelope.certifications if row.name
        ],
        projects=[ProjectEntity(name=row.name) for row in envelope.projects],
        # Raw tools, languages, interviews, assessments and ATS signals remain in source evidence.
        skills=[],
    )


def _join(first: str | None, second: str | None) -> str | None:
    values = [value for value in (first, second) if value]
    return " — ".join(values) if values else None


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
