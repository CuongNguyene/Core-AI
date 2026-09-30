from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class CompetencyRecordRecord(Base):
    __tablename__ = "competency_records"
    __table_args__ = (
        UniqueConstraint(
            "subject_id", "organization_id", "competency_id", name="uq_competency_subject_org"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    subject_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    competency_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    level: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_decision_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reassessment_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompetencyDecisionRecord(Base):
    __tablename__ = "competency_decisions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    competency_record_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("competency_records.id"), nullable=False, index=True
    )
    assessment_submission_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    delegation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reassessment_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompetencyAuditEventRecord(Base):
    __tablename__ = "competency_audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    competency_record_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("competency_records.id"), nullable=False, index=True
    )
    competency_decision_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("competency_decisions.id"), nullable=True, index=True
    )
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
