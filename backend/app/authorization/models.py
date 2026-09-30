from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class UserRecord(Base):
    __tablename__ = "authorization_users"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrganizationRecord(Base):
    __tablename__ = "authorization_organizations"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrganizationMembershipRecord(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("authorization_users.id"), index=True)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("authorization_organizations.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserRoleAssignmentRecord(Base):
    __tablename__ = "user_role_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", "role", name="uq_user_org_role"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("authorization_users.id"), index=True)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("authorization_organizations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    granted_by: Mapped[UUID] = mapped_column(ForeignKey("authorization_users.id"), nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScopedDelegationRecord(Base):
    __tablename__ = "scoped_delegations"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("authorization_users.id"), index=True)
    permission: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("authorization_organizations.id"), index=True
    )
    competency_scope: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    granted_by: Mapped[UUID] = mapped_column(ForeignKey("authorization_users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthorizationAuditEventRecord(Base):
    __tablename__ = "authorization_audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("authorization_users.id"), nullable=False)
    delegation_id: Mapped[UUID | None] = mapped_column(ForeignKey("scoped_delegations.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
