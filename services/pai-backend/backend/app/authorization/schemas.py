from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class RoleAssignmentStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Role(StrEnum):
    ADMIN = "admin"
    SME = "sme"
    REVIEWER = "reviewer"
    LEARNER = "learner"


class DelegationStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"


class User(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    display_name: str = Field(min_length=1)
    username: str = Field(min_length=1)
    status: UserStatus
    version: int = Field(ge=1)
    created_at: datetime


class Organization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: OrganizationStatus
    version: int = Field(ge=1)
    created_at: datetime


class OrganizationMembership(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    user_id: UUID
    organization_id: UUID
    status: MembershipStatus
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class UserRoleAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    user_id: UUID
    organization_id: UUID
    role: Role
    status: RoleAssignmentStatus
    granted_by: UUID
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class ActorContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    actor_id: UUID
    organization_id: UUID
    roles: frozenset[Role]
    authentication_method: Literal["development_header", "signed_actor_context"] = "development_header"


class AuthorizationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    allowed: bool
    reason_code: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    matched_role: Role | None = None
    delegation_id: UUID | None = None
    scope_match: bool = False


class ScopedDelegation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    user_id: UUID
    permission: Literal[
        "competency.verify",
        "credential.approve",
        "credential.issue",
        "credential.revoke",
    ]
    organization_id: UUID
    competency_scope: frozenset[str] = Field(min_length=1)
    valid_from: datetime
    valid_until: datetime
    status: DelegationStatus
    granted_by: UUID
    reason: str = Field(min_length=1)
    version: int = Field(ge=1)
