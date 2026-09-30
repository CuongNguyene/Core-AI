from uuid import UUID

from app.authorization.repository import SubjectRepository
from app.authorization.schemas import (
    ActorContext,
    MembershipStatus,
    OrganizationStatus,
    RoleAssignmentStatus,
    UserStatus,
)


class DevelopmentIdentityAdapter:
    def __init__(self, subjects: SubjectRepository) -> None:
        self._subjects = subjects

    async def resolve(self, actor_id: UUID) -> ActorContext:
        user = await self._subjects.get_user(actor_id)
        if user is None:
            raise PermissionError("identity_unknown")
        if user.status is not UserStatus.ACTIVE:
            raise PermissionError("identity_disabled")
        memberships = [
            item
            for item in await self._subjects.active_memberships(actor_id)
            if item.status is MembershipStatus.ACTIVE
        ]
        if not memberships:
            raise PermissionError("identity_membership_missing")
        if len(memberships) != 1:
            raise PermissionError("identity_membership_ambiguous")
        organization_id = memberships[0].organization_id
        organization = await self._subjects.get_organization(organization_id)
        if organization is None or organization.status is not OrganizationStatus.ACTIVE:
            raise PermissionError("identity_organization_inactive")
        assignments = await self._subjects.active_roles(actor_id, organization_id)
        return ActorContext(
            actor_id=actor_id,
            organization_id=organization_id,
            roles=frozenset(
                item.role for item in assignments if item.status is RoleAssignmentStatus.ACTIVE
            ),
        )
