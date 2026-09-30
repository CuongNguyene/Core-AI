from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentKind(StrEnum):
    CV = "cv"
    JD = "jd"


class DocumentStatus(StrEnum):
    QUARANTINED = "quarantined"
    CLEAN = "clean"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DELETED = "deleted"


class StoredDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    owner_actor_id: UUID
    organization_id: UUID
    kind: DocumentKind
    content_type: str
    byte_size: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_key: str = Field(min_length=1)
    status: DocumentStatus
    retention_until: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_extractable(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return self.status is DocumentStatus.CLEAN and self.retention_until > current
