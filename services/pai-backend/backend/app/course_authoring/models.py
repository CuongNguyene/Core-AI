from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base

if TYPE_CHECKING:
    from .brief_revision_schemas import AuthoringBriefRevision


class CourseAuthoringRequestRecord(Base):
    __tablename__ = "course_authoring_requests"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    training_brief: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    audience_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    learning_need_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    objective_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    instructional_blueprint_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    constraints: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    authoring_workflow_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by_actor_ref: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuthoringBriefRevisionRecord(Base):
    __tablename__ = "authoring_brief_revisions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    clarification: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    author_feedback: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    supersedes_revision_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)

    @classmethod
    def from_domain(cls, revision: object) -> AuthoringBriefRevisionRecord:
        from .brief_revision_schemas import AuthoringBriefRevision

        value = revision
        if not isinstance(value, AuthoringBriefRevision):
            raise TypeError("authoring_revision_required")
        return cls(
            id=value.id,
            request_id=value.request_id,
            version=value.version,
            status=value.status.value,
            payload=value.payload.model_dump(mode="json"),
            clarification=value.clarification.model_dump(mode="json"),
            author_feedback=value.author_feedback,
            supersedes_revision_id=value.supersedes_revision_id,
            confirmed_at=value.confirmed_at,
            confirmed_by=value.confirmed_by,
            created_at=value.created_at,
            created_by=value.created_by,
        )

    def to_domain(self) -> AuthoringBriefRevision:
        import json

        from .brief_revision_schemas import AuthoringBriefRevision

        return AuthoringBriefRevision.model_validate_json(
            json.dumps(
                {
                    "id": self.id,
                    "request_id": self.request_id,
                    "version": self.version,
                    "status": self.status,
                    "payload": self.payload,
                    "clarification": self.clarification,
                    "author_feedback": self.author_feedback,
                    "supersedes_revision_id": self.supersedes_revision_id,
                    "confirmed_at": self.confirmed_at,
                    "confirmed_by": str(self.confirmed_by) if self.confirmed_by else None,
                    "created_at": self.created_at,
                    "created_by": str(self.created_by),
                },
                default=str,
            )
        )

    def apply_domain(self, revision: object) -> None:
        from .brief_revision_schemas import AuthoringBriefRevision

        if not isinstance(revision, AuthoringBriefRevision):
            raise TypeError("authoring_revision_required")
        self.status = revision.status.value
        self.clarification = revision.clarification.model_dump(mode="json")
        self.confirmed_at = revision.confirmed_at
        self.confirmed_by = revision.confirmed_by
