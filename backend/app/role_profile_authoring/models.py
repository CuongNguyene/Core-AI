from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class RoleProfileDraftRecord(Base):
    __tablename__ = "role_profile_drafts"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_jd_profile_id: Mapped[str] = mapped_column(
        ForeignKey("extraction_profiles.id"), nullable=False, index=True
    )
    source_jd_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(256))
    requirements: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    quality_gate: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    approval_eligibility: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    source_schema: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy_v1")
    source_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.1")
    authoring_findings: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    duplicate_candidate_groups: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    approved_role_profile_id: Mapped[str | None] = mapped_column(String(128))
    role_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("roles.id"), index=True)
    role_jd_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("role_jd_versions.id"), index=True
    )
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RoleProfileDraftVersionRecord(Base):
    __tablename__ = "role_profile_draft_versions"

    record_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("role_profile_drafts.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str | None] = mapped_column(String(256))
    requirements: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    quality_gate: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    approval_eligibility: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    source_schema: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy_v1")
    source_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.1")
    authoring_findings: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    duplicate_candidate_groups: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoleProfileDraftAuditRecord(Base):
    __tablename__ = "role_profile_draft_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("role_profile_drafts.id"), nullable=False, index=True
    )
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
