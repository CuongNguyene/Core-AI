from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class IntegrationLearningResultRecord(Base):
    __tablename__ = "integration_learning_results"

    submission_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    evaluation_reference: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    learner_reference: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    course_reference: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    activity_reference: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    completion_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CandidateIdentityLinkRecord(Base):
    __tablename__ = "candidate_identity_links"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)
    source_subject_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    organization_scope: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("authorization_users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
