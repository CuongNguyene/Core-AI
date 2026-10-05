from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class CourseRecommendationExecutionRecord(Base):
    __tablename__ = "course_recommendation_executions"
    __table_args__ = (
        UniqueConstraint(
            "organization_ref",
            "actor_ref",
            "request_key",
            name="uq_course_recommendation_execution_scope_key",
        ),
        Index("ix_course_recommendation_executions_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    snapshot_schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    algorithm_id: Mapped[str] = mapped_column(String(128), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    result_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    source_learning_need_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    organization_ref: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_ref: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    result_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    governance_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
