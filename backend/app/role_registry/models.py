from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class RoleRecord(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "role_code", name="uq_role_org_code"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    role_code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    active_role_profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class RoleJDRecord(Base):
    __tablename__ = "role_jds"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    role_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RoleJDVersionRecord(Base):
    __tablename__ = "role_jd_versions"
    __table_args__ = (
        UniqueConstraint("role_jd_id", "version", name="uq_role_jd_version"),
        UniqueConstraint("document_id", name="uq_role_jd_document"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    role_jd_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("role_jds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    document_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("documents.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
