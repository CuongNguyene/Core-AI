from uuid import UUID

import pytest

from app.authorization.fixtures import ADMIN_ID, DISABLED_USER_ID, LEARNER_ID
from app.authorization.repository import InMemorySubjectRepository
from app.authorization.schemas import MembershipStatus, OrganizationMembership, Role
from app.authorization.service import DevelopmentIdentityAdapter


@pytest.mark.asyncio
async def test_adapter_resolves_active_uuid_user_with_one_active_membership() -> None:
    adapter = DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture())

    actor = await adapter.resolve(LEARNER_ID)

    assert actor.actor_id == LEARNER_ID
    assert actor.roles == frozenset({Role.LEARNER})
    assert actor.authentication_method == "development_header"


@pytest.mark.asyncio
async def test_adapter_rejects_unknown_or_disabled_user() -> None:
    adapter = DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture())

    with pytest.raises(PermissionError, match="identity_unknown"):
        await adapter.resolve(UUID("00000000-0000-0000-0000-000000000099"))
    with pytest.raises(PermissionError, match="identity_disabled"):
        await adapter.resolve(DISABLED_USER_ID)


@pytest.mark.asyncio
async def test_adapter_fails_closed_when_active_membership_is_ambiguous() -> None:
    repository = InMemorySubjectRepository.fixture()
    repository.memberships.append(
        OrganizationMembership(
            user_id=ADMIN_ID,
            organization_id=UUID("00000000-0000-0000-0000-000000000010"),
            status=MembershipStatus.ACTIVE,
        )
    )
    adapter = DevelopmentIdentityAdapter(repository)

    with pytest.raises(PermissionError, match="identity_membership_ambiguous"):
        await adapter.resolve(ADMIN_ID)
