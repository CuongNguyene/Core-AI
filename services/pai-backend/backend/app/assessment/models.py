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


class AssessmentRubricRecord(Base):
    __tablename__ = "assessment_rubrics"
    __table_args__ = (
        UniqueConstraint("rubric_id", "version", name="uq_assessment_rubric_version"),
    )

    record_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    rubric_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    criteria: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)


class AssessmentTemplateRecord(Base):
    __tablename__ = "assessment_templates"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_assessment_template_version"),
    )

    record_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    template_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    competency_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    rubric_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_classification: Mapped[str] = mapped_column(String(16), nullable=False)
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reassessment_lead_days: Mapped[int] = mapped_column(Integer, nullable=False)


class AssessmentTaskRecord(Base):
    __tablename__ = "assessment_tasks"
    __table_args__ = (UniqueConstraint("template_record_id", "task_id", name="uq_assessment_task"),)

    record_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    template_record_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("assessment_templates.record_id"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    task_type: Mapped[str] = mapped_column(String(16), nullable=False)
    prompt_reference: Mapped[str] = mapped_column(String(512), nullable=False)


class AssessmentSubmissionRecord(Base):
    __tablename__ = "assessment_submissions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    template_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    template_version: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    artifact_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssessmentScoreProposalRecord(Base):
    __tablename__ = "assessment_score_proposals"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    submission_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("assessment_submissions.id"), nullable=False, index=True
    )
    rubric_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False)
    criterion_scores: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AssessmentSMEReviewRecord(Base):
    __tablename__ = "assessment_sme_reviews"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    submission_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("assessment_submissions.id"), nullable=False, index=True
    )
    score_proposal_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("assessment_score_proposals.id"), nullable=False, index=True
    )
    reviewer_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    decision_rationale_reference: Mapped[str] = mapped_column(String(512), nullable=False)


class AssessmentDecisionRecord(Base):
    __tablename__ = "assessment_decisions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    submission_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("assessment_submissions.id"), nullable=False
    )
    score_proposal_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("assessment_score_proposals.id"), nullable=False
    )
    review_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("assessment_sme_reviews.id"), nullable=False
    )
    assessor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    risk_classification: Mapped[str] = mapped_column(String(16), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssessmentAuditEventRecord(Base):
    __tablename__ = "assessment_audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    assessment_decision_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("assessment_decisions.id"), nullable=True, index=True
    )
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
