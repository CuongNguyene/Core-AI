from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoleStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class Role(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    organization_id: UUID
    role_code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    status: RoleStatus = RoleStatus.ACTIVE
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    active_role_profile_id: str | None = None


class RoleJD(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    role_id: UUID
    created_at: datetime
    updated_at: datetime


class RoleJDVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    role_jd_id: UUID
    role_id: UUID
    version: int = Field(ge=1)
    document_id: UUID
    created_by: UUID
    created_at: datetime


class CreateRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=2000)


class UpdateRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=2000)
    status: RoleStatus | None = None


class RoleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    organization_id: UUID
    role_code: str
    title: str
    status: RoleStatus
    jd_version_count: int = Field(ge=0)
    current_jd_version: int | None = Field(default=None, ge=1)
