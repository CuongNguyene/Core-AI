from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.extraction.models import ExtractionProfileRecord
from app.shared.database import Base


class RoleCompetencyProfileRecord(Base):
    __tablename__ = "role_competency_profiles"
    __table_args__ = (
        UniqueConstraint("id", "version", name="uq_role_profile_id_version"),
        Index(
            "uq_role_competency_profiles_role_governance_version",
            "role_id",
            "governance_version",
            unique=True,
            postgresql_where=text("role_id IS NOT NULL AND governance_version IS NOT NULL"),
            sqlite_where=text("role_id IS NOT NULL AND governance_version IS NOT NULL"),
        ),
    )

    record_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source_jd_profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_jd_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    requirements: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    semantic_core_version: Mapped[str | None] = mapped_column(String(64))
    semantic_pack_refs: Mapped[list[dict[str, str]] | None] = mapped_column(JSON)
    semantic_policy_id: Mapped[str | None] = mapped_column(String(128))
    semantic_policy_version: Mapped[str | None] = mapped_column(String(64))
    role_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("roles.id"), index=True)
    role_jd_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("role_jd_versions.id"), index=True
    )
    governance_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RoleProfileSemanticPolicyMappingRecord(Base):
    __tablename__ = "role_profile_semantic_policy_mappings"

    role_profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    role_profile_version: Mapped[str] = mapped_column(String(64), primary_key=True)
    core_version: Mapped[str] = mapped_column(String(64), nullable=False)
    pack_refs: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    selection_source: Mapped[str] = mapped_column(String(64), nullable=False)


class PreliminaryMatchRecord(Base):
    __tablename__ = "preliminary_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    cv_profile_id: Mapped[str] = mapped_column(
        ForeignKey(ExtractionProfileRecord.id), nullable=False
    )
    cv_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    jd_profile_id: Mapped[str] = mapped_column(
        ForeignKey(ExtractionProfileRecord.id), nullable=False
    )
    jd_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    role_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role_profile_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    criterion_results: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    preliminary_skill_gaps: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approved_gap_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewed_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MatchEvidenceAllocationRecord(Base):
    __tablename__ = "match_evidence_allocations"
    __table_args__ = (
        UniqueConstraint("match_id", "evidence_id", name="uq_match_decisive_evidence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("preliminary_matches.id"), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)


class MatchingAuditEventRecord(Base):
    __tablename__ = "matching_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    match_id: Mapped[str | None] = mapped_column(
        ForeignKey("preliminary_matches.id"), nullable=True
    )
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
