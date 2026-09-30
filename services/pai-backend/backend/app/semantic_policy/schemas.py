from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SemanticPolicyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class SemanticPolicyRef(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)


class SemanticPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    core_version: str = Field(default="semantic-core-v1", min_length=1)
    status: SemanticPolicyStatus
    domain_pack_id: str = Field(min_length=1)
    domain_pack_version: str = Field(min_length=1)
    domain_pack_checksum: str = Field(min_length=1)
    description: str = Field(min_length=1)
    created_by: str | None = None
    reviewed_by: str | None = None
    created_at: datetime | None = None
    activated_at: datetime | None = None
    deprecated_at: datetime | None = None


class ResolvedSemanticPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    policy_id: str
    policy_version: str
    core_version: str
    policy_status: SemanticPolicyStatus
    domain_pack_id: str
    domain_pack_version: str
    domain_pack_checksum: str
    target_id: str
    target_type: str
    resolution_status: str = "resolved"
