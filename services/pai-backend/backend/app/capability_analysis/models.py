from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class CapabilityGapPortfolioRecord(Base):
    __tablename__ = "capability_gap_portfolios"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    cv_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    cv_profile_version: Mapped[int] = mapped_column(nullable=False)
    current_target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    current_target_version: Mapped[str] = mapped_column(String(64), nullable=False)
    current_usage_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    future_target_id: Mapped[str | None] = mapped_column(String(128))
    future_target_version: Mapped[str | None] = mapped_column(String(64))
    future_usage_mode: Mapped[str | None] = mapped_column(String(16))
    owner_actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    analysis_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ready")
    analysis_version: Mapped[int] = mapped_column(nullable=False, server_default="1")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    snapshot_schema_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="capability-gap-v1"
    )
    preview_readiness: Mapped[dict[str, object] | None] = mapped_column(JSON)
    verification_queue: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    semantic_policy: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RequirementAssessmentRecord(Base):
    __tablename__ = "capability_gap_assessments"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "target_type", "requirement_id", name="uq_capability_gap_assessment"
        ),
    )

    record_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("capability_gap_portfolios.id"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class TargetGapRecord(Base):
    __tablename__ = "capability_target_gaps"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "target_type", "requirement_id", name="uq_capability_target_gap"
        ),
    )

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("capability_gap_portfolios.id"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class GapOverlapLinkRecord(Base):
    __tablename__ = "capability_gap_overlap_links"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "source_gap_id", "target_gap_id", name="uq_capability_gap_overlap_link"
        ),
    )

    record_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("capability_gap_portfolios.id"), nullable=False, index=True
    )
    source_gap_id: Mapped[str] = mapped_column(String(256), nullable=False)
    target_gap_id: Mapped[str] = mapped_column(String(256), nullable=False)
    shared_theme: Mapped[str] = mapped_column(String(256), nullable=False)


class CapabilityGapAuditEventRecord(Base):
    __tablename__ = "capability_gap_audit_events"

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    portfolio_id: Mapped[str | None] = mapped_column(ForeignKey("capability_gap_portfolios.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
