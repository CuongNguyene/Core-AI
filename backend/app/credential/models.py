from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class CredentialPolicyRecord(Base):
    __tablename__ = "credential_policies"
    __table_args__ = (
        UniqueConstraint("policy_id", "version", name="uq_credential_policy_version"),
    )

    record_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    valid_for_days: Mapped[int] = mapped_column(Integer, nullable=False)
    allow_duplicate_active: Mapped[bool] = mapped_column(nullable=False)
    requires_distinct_approver_and_issuer: Mapped[bool] = mapped_column(nullable=False)
    competency_id: Mapped[str | None] = mapped_column(String(128))
    minimum_level: Mapped[int | None] = mapped_column(Integer)


class CredentialRequestRecord(Base):
    __tablename__ = "credential_requests"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    source_reference_id: Mapped[str | None] = mapped_column(String(512))
    eligibility: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requested_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    approver_id: Mapped[UUID | None] = mapped_column(Uuid)
    issuer_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CredentialRecord(Base):
    __tablename__ = "credentials"
    __table_args__ = (UniqueConstraint("request_id", name="uq_credential_request"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    request_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("credential_requests.id"), nullable=False
    )
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class CredentialAuditEventRecord(Base):
    __tablename__ = "credential_audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    request_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("credential_requests.id"))
    credential_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("credentials.id"))
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
