from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class OrganizationExternalMappingRecord(Base):
    __tablename__ = "organization_external_mappings"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "external_company_ref", name="uq_org_external_source_ref"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("authorization_organizations.id"), nullable=False, index=True
    )
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    external_company_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CandidateExternalEmployeeIdentityRecord(Base):
    __tablename__ = "candidate_external_employee_identities"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_system",
            "employee_ref",
            name="uq_candidate_external_employee_identity",
        ),
        UniqueConstraint(
            "candidate_id", "source_system", name="uq_candidate_external_identity_candidate_source"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("authorization_organizations.id"), nullable=False
    )
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    current_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_source_snapshots.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CandidateSourceSnapshotRecord(Base):
    __tablename__ = "candidate_source_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "fingerprint", name="uq_candidate_source_snapshot_fingerprint"
        ),
        UniqueConstraint(
            "external_identity_id",
            "source_revision",
            name="uq_candidate_source_snapshot_identity_revision",
        ),
        CheckConstraint(
            "source_revision IS NULL OR source_revision > 0",
            name="ck_candidate_source_snapshot_revision_positive",
        ),
        Index("ix_candidate_source_snapshot_candidate_created", "candidate_id", "ingested_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    external_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_external_employee_identities.id"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("authorization_organizations.id"), nullable=False
    )
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_snapshot_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_version: Mapped[str | int | None] = mapped_column(JSON, nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_revision: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ordering_state: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_source_snapshots.id"), nullable=True
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CandidateStructuredEvidenceRecord(Base):
    __tablename__ = "candidate_structured_evidence"
    __table_args__ = (Index("ix_candidate_structured_evidence_snapshot", "snapshot_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_source_snapshots.id"), nullable=False
    )
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    source_record_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_field_path: Mapped[str] = mapped_column(String(512), nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_version: Mapped[str | int | None] = mapped_column(JSON, nullable=True)
    source_value: Mapped[object] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
