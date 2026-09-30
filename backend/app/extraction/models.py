from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class ExtractionJobRecord(Base):
    __tablename__ = "extraction_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    document_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    completed_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(128))
    error_details: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExtractionProfileRecord(Base):
    __tablename__ = "extraction_profiles"
    __table_args__ = (
        UniqueConstraint("job_id", "version", name="uq_extraction_profiles_job_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("extraction_jobs.id"), nullable=False, index=True
    )
    document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    document_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("extraction_profiles.id"), nullable=True, index=True
    )
    normalized_output: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class ExtractionAuditEventRecord(Base):
    __tablename__ = "extraction_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("extraction_jobs.id"), nullable=False, index=True
    )
    profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
