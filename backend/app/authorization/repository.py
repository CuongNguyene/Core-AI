from collections.abc import Sequence
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.authorization.models import (
    AuthorizationAuditEventRecord,
    OrganizationMembershipRecord,
    OrganizationRecord,
    ScopedDelegationRecord,
    UserRecord,
    UserRoleAssignmentRecord,
)
from app.authorization.schemas import (
    DelegationStatus,
    Organization,
    OrganizationMembership,
    ScopedDelegation,
    User,
    UserRoleAssignment,
)


class InMemoryDelegationRepository:
    def __init__(self, delegations: list[ScopedDelegation]) -> None:
        self._delegations = {item.id: item for item in delegations}
        self.audit_events: list[dict[str, object]] = []

    async def get(self, delegation_id: UUID) -> ScopedDelegation | None:
        return self._delegations.get(delegation_id)

    async def active_for_user(self, user_id: UUID) -> tuple[ScopedDelegation, ...]:
        return tuple(item for item in self._delegations.values() if item.user_id == user_id)

    async def transition(
        self,
        delegation_id: UUID,
        actor_id: UUID,
        *,
        expected_version: int,
        target: DelegationStatus,
        reason: str,
    ) -> ScopedDelegation:
        current = self._delegations.get(delegation_id)
        if current is None:
            raise KeyError(delegation_id)
        if current.version != expected_version:
            raise ValueError("version_conflict")
        if (current.status, target) not in {
            (DelegationStatus.DRAFT, DelegationStatus.ACTIVE),
            (DelegationStatus.ACTIVE, DelegationStatus.SUSPENDED),
            (DelegationStatus.ACTIVE, DelegationStatus.REVOKED),
            (DelegationStatus.SUSPENDED, DelegationStatus.ACTIVE),
            (DelegationStatus.SUSPENDED, DelegationStatus.REVOKED),
        }:
            raise ValueError("invalid_transition")
        updated = current.model_copy(update={"status": target, "version": current.version + 1})
        self._delegations[delegation_id] = updated
        action = {
            DelegationStatus.ACTIVE: "DELEGATION_ACTIVATED",
            DelegationStatus.SUSPENDED: "DELEGATION_SUSPENDED",
            DelegationStatus.REVOKED: "DELEGATION_REVOKED",
        }[target]
        self.audit_events.append(
            {
                "action": action,
                "actor_id": actor_id,
                "delegation_id": delegation_id,
                "reason_code": "delegation_transition",
            }
        )
        return updated

    async def create(self, delegation: ScopedDelegation) -> ScopedDelegation:
        if delegation.id in self._delegations:
            raise ValueError("delegation_exists")
        self._delegations[delegation.id] = delegation
        return delegation


class SqlAlchemyDelegationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, delegation_id: UUID) -> ScopedDelegation | None:
        async with self._session_factory() as session:
            record = await session.get(ScopedDelegationRecord, delegation_id)
            return _delegation(record) if record else None

    async def active_for_user(self, user_id: UUID) -> tuple[ScopedDelegation, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(ScopedDelegationRecord).where(ScopedDelegationRecord.user_id == user_id)
                )
            ).all()
            return tuple(_delegation(record) for record in records)

    async def create(self, delegation: ScopedDelegation) -> ScopedDelegation:
        async with self._session_factory() as session, session.begin():
            session.add(_delegation_record(delegation))
            session.add(
                AuthorizationAuditEventRecord(
                    id=uuid4(),
                    actor_id=delegation.granted_by,
                    delegation_id=delegation.id,
                    action="DELEGATION_CREATED",
                    audit_metadata={
                        "permission": delegation.permission,
                        "organization_id": str(delegation.organization_id),
                        "version": delegation.version,
                    },
                )
            )
        return delegation

    async def transition(
        self,
        delegation_id: UUID,
        actor_id: UUID,
        *,
        expected_version: int,
        target: DelegationStatus,
        reason: str,
    ) -> ScopedDelegation:
        async with self._session_factory() as session, session.begin():
            record = await session.scalar(
                select(ScopedDelegationRecord)
                .where(ScopedDelegationRecord.id == delegation_id)
                .with_for_update()
            )
            if record is None:
                raise KeyError(delegation_id)
            if record.version != expected_version:
                raise ValueError("version_conflict")
            current = DelegationStatus(record.status)
            if (current, target) not in {
                (DelegationStatus.DRAFT, DelegationStatus.ACTIVE),
                (DelegationStatus.ACTIVE, DelegationStatus.SUSPENDED),
                (DelegationStatus.ACTIVE, DelegationStatus.REVOKED),
                (DelegationStatus.SUSPENDED, DelegationStatus.ACTIVE),
                (DelegationStatus.SUSPENDED, DelegationStatus.REVOKED),
            }:
                raise ValueError("invalid_transition")
            record.status = target.value
            record.version += 1
            action = {
                DelegationStatus.ACTIVE: "DELEGATION_ACTIVATED",
                DelegationStatus.SUSPENDED: "DELEGATION_SUSPENDED",
                DelegationStatus.REVOKED: "DELEGATION_REVOKED",
            }[target]
            session.add(
                AuthorizationAuditEventRecord(
                    id=uuid4(),
                    actor_id=actor_id,
                    delegation_id=delegation_id,
                    action=action,
                    audit_metadata={
                        "previous_status": current.value,
                        "new_status": target.value,
                        "expected_version": expected_version,
                        "reason_code": "delegation_transition",
                    },
                )
            )
            await session.flush()
            return _delegation(record)


class SubjectRepository(Protocol):
    async def get_user(self, user_id: UUID) -> User | None: ...

    async def active_memberships(self, user_id: UUID) -> Sequence[OrganizationMembership]: ...

    async def get_organization(self, organization_id: UUID) -> Organization | None: ...

    async def active_roles(
        self, user_id: UUID, organization_id: UUID
    ) -> frozenset[UserRoleAssignment]: ...


class InMemorySubjectRepository:
    def __init__(
        self,
        users: list[User],
        organizations: list[Organization],
        memberships: list[OrganizationMembership],
        role_assignments: list[UserRoleAssignment],
    ) -> None:
        self.users = {user.id: user for user in users}
        self.organizations = {organization.id: organization for organization in organizations}
        self.memberships = memberships
        self.role_assignments = role_assignments

    @classmethod
    def fixture(cls) -> "InMemorySubjectRepository":
        from app.authorization.fixtures import subject_fixture

        return subject_fixture()

    async def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def active_memberships(self, user_id: UUID) -> Sequence[OrganizationMembership]:
        return tuple(membership for membership in self.memberships if membership.user_id == user_id)

    async def get_organization(self, organization_id: UUID) -> Organization | None:
        return self.organizations.get(organization_id)

    async def active_roles(
        self, user_id: UUID, organization_id: UUID
    ) -> frozenset[UserRoleAssignment]:
        return frozenset(
            assignment
            for assignment in self.role_assignments
            if assignment.user_id == user_id and assignment.organization_id == organization_id
        )


class SqlAlchemySubjectRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_user(self, user_id: UUID) -> User | None:
        async with self._session_factory() as session:
            record = await session.get(UserRecord, user_id)
            return _user(record) if record else None

    async def active_memberships(self, user_id: UUID) -> Sequence[OrganizationMembership]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(OrganizationMembershipRecord).where(
                        OrganizationMembershipRecord.user_id == user_id
                    )
                )
            ).all()
            return tuple(_membership(record) for record in records)

    async def get_organization(self, organization_id: UUID) -> Organization | None:
        async with self._session_factory() as session:
            record = await session.get(OrganizationRecord, organization_id)
            return _organization(record) if record else None

    async def active_roles(
        self, user_id: UUID, organization_id: UUID
    ) -> frozenset[UserRoleAssignment]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(UserRoleAssignmentRecord).where(
                        UserRoleAssignmentRecord.user_id == user_id,
                        UserRoleAssignmentRecord.organization_id == organization_id,
                    )
                )
            ).all()
            return frozenset(_role(record) for record in records)


def _user(record: UserRecord) -> User:
    return User.model_validate(record, from_attributes=True)


def _organization(record: OrganizationRecord) -> Organization:
    return Organization.model_validate(record, from_attributes=True)


def _membership(record: OrganizationMembershipRecord) -> OrganizationMembership:
    return OrganizationMembership.model_validate(record, from_attributes=True)


def _role(record: UserRoleAssignmentRecord) -> UserRoleAssignment:
    return UserRoleAssignment.model_validate(record, from_attributes=True)


def _delegation(record: ScopedDelegationRecord) -> ScopedDelegation:
    return ScopedDelegation.model_validate(
        {
            "id": record.id,
            "user_id": record.user_id,
            "permission": record.permission,
            "organization_id": record.organization_id,
            "competency_scope": frozenset(record.competency_scope),
            "valid_from": record.valid_from,
            "valid_until": record.valid_until,
            "status": record.status,
            "granted_by": record.granted_by,
            "reason": record.reason,
            "version": record.version,
        }
    )


def _delegation_record(item: ScopedDelegation) -> ScopedDelegationRecord:
    return ScopedDelegationRecord(
        id=item.id,
        user_id=item.user_id,
        permission=item.permission,
        organization_id=item.organization_id,
        competency_scope=sorted(item.competency_scope),
        valid_from=item.valid_from,
        valid_until=item.valid_until,
        status=item.status.value,
        granted_by=item.granted_by,
        reason=item.reason,
        version=item.version,
    )
