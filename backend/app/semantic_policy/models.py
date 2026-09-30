from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class SemanticPolicyRecord(Base):
    __tablename__ = "semantic_policies"

    record_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    core_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    domain_pack_id: Mapped[str] = mapped_column(String(128), nullable=False)
    domain_pack_version: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_pack_checksum: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SemanticPolicyAuditEventRecord(Base):
    __tablename__ = "semantic_policy_audit_events"

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
