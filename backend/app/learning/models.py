from datetime import date, datetime
from uuid import UUID

from sqlalchemy import JSON, Date, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class LearningPathRecord(Base):
    __tablename__ = "learning_paths"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    subject_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    target_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_profile_version: Mapped[str] = mapped_column(String(64), nullable=False)
    preliminary_match_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    verified_competency_record_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    approved_gap_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    development_goal: Mapped[str] = mapped_column(String(500), nullable=False)
    target_completion_date: Mapped[date] = mapped_column(Date, nullable=False)
    objectives: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    prerequisite_nodes: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    prerequisite_edges: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    learning_objects: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    lessons: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    modules: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    blueprints: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    generator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="verified")
    capability_analysis_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    capability_analysis_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_candidate_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_target_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_gap_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    source_evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    source_recommendation_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    validation: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, server_default='{"valid": true, "ready_for_review": true, "findings": []}')
    reviewed: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    reviewed_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)


class LearningAuditEventRecord(Base):
    __tablename__ = "learning_audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    path_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
