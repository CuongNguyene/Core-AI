from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class CandidateRecord(Base):
    __tablename__ = "candidates"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    primary_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_by_actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    current_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateDocumentRecord(Base):
    __tablename__ = "candidate_documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    document_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateProfileRecord(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    governance_version: Mapped[int] = mapped_column(Integer, nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateCVRecord(Base):
    __tablename__ = "candidate_cvs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateCVVersionRecord(Base):
    __tablename__ = "candidate_cv_versions"
    __table_args__ = (UniqueConstraint("candidate_cv_id", "version", name="uq_candidate_cv_version"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_cv_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_cvs.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), unique=True, nullable=False)
    created_by_actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateClaimRecord(Base):
    __tablename__ = "candidate_claims"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_index: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[str] = mapped_column(String(2048), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(32), nullable=False)
    context: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)


class CandidateEvidenceRecord(Base):
    __tablename__ = "candidate_evidence"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_claims.id"), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    source_locator: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    excerpt: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    context: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class CandidateReviewActionRecordModel(Base):
    __tablename__ = "candidate_review_actions"

    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
