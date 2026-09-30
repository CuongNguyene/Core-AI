from datetime import UTC, datetime
from uuid import UUID

from app.authorization.repository import InMemorySubjectRepository
from app.authorization.schemas import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Role,
    RoleAssignmentStatus,
    User,
    UserRoleAssignment,
    UserStatus,
)

ORG_PAI_ID = UUID("00000000-0000-0000-0000-000000000001")
ADMIN_ID = UUID("00000000-0000-0000-0000-000000000002")
SME_ID = UUID("00000000-0000-0000-0000-000000000003")
REVIEWER_ID = UUID("00000000-0000-0000-0000-000000000004")
LEARNER_ID = UUID("00000000-0000-0000-0000-000000000005")
AUTHORIZED_SME_ID = UUID("00000000-0000-0000-0000-000000000006")
DISABLED_USER_ID = UUID("00000000-0000-0000-0000-000000000007")


def subject_fixture() -> InMemorySubjectRepository:
    created_at = datetime(2026, 8, 3, tzinfo=UTC)
    users = [
        User(
            id=ADMIN_ID,
            display_name="Admin",
            username="admin",
            status=UserStatus.ACTIVE,
            version=1,
            created_at=created_at,
        ),
        User(
            id=SME_ID,
            display_name="SME",
            username="sme",
            status=UserStatus.ACTIVE,
            version=1,
            created_at=created_at,
        ),
        User(
            id=REVIEWER_ID,
            display_name="Reviewer",
            username="reviewer",
            status=UserStatus.ACTIVE,
            version=1,
            created_at=created_at,
        ),
        User(
            id=LEARNER_ID,
            display_name="Learner",
            username="learner",
            status=UserStatus.ACTIVE,
            version=1,
            created_at=created_at,
        ),
        User(
            id=AUTHORIZED_SME_ID,
            display_name="Authorized SME",
            username="authorized-sme",
            status=UserStatus.ACTIVE,
            version=1,
            created_at=created_at,
        ),
        User(
            id=DISABLED_USER_ID,
            display_name="Disabled",
            username="disabled",
            status=UserStatus.DISABLED,
            version=1,
            created_at=created_at,
        ),
    ]
    organization = Organization(
        id=ORG_PAI_ID,
        code="ORG-PAI",
        name="PAI",
        status=OrganizationStatus.ACTIVE,
        version=1,
        created_at=created_at,
    )
    memberships = [
        OrganizationMembership(
            user_id=user.id, organization_id=ORG_PAI_ID, status=MembershipStatus.ACTIVE
        )
        for user in users
    ]
    assignments = [
        UserRoleAssignment(
            user_id=ADMIN_ID,
            organization_id=ORG_PAI_ID,
            role=Role.ADMIN,
            status=RoleAssignmentStatus.ACTIVE,
            granted_by=ADMIN_ID,
        ),
        UserRoleAssignment(
            user_id=SME_ID,
            organization_id=ORG_PAI_ID,
            role=Role.SME,
            status=RoleAssignmentStatus.ACTIVE,
            granted_by=ADMIN_ID,
        ),
        UserRoleAssignment(
            user_id=REVIEWER_ID,
            organization_id=ORG_PAI_ID,
            role=Role.REVIEWER,
            status=RoleAssignmentStatus.ACTIVE,
            granted_by=ADMIN_ID,
        ),
        UserRoleAssignment(
            user_id=LEARNER_ID,
            organization_id=ORG_PAI_ID,
            role=Role.LEARNER,
            status=RoleAssignmentStatus.ACTIVE,
            granted_by=ADMIN_ID,
        ),
        UserRoleAssignment(
            user_id=AUTHORIZED_SME_ID,
            organization_id=ORG_PAI_ID,
            role=Role.SME,
            status=RoleAssignmentStatus.ACTIVE,
            granted_by=ADMIN_ID,
        ),
    ]
    return InMemorySubjectRepository(users, [organization], memberships, assignments)
