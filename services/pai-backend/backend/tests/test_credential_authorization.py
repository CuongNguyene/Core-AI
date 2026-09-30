from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.authorization.repository import InMemoryDelegationRepository
from app.authorization.schemas import ActorContext, DelegationStatus, Role, ScopedDelegation
from app.credential.policy import CredentialAuthorizationPolicy


@pytest.mark.asyncio
async def test_issue_requires_active_policy_scoped_delegation() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    policy_id = "python-level-3"
    delegation = ScopedDelegation(
        id=uuid4(),
        user_id=actor_id,
        permission="credential.issue",
        organization_id=organization_id,
        competency_scope=frozenset({policy_id}),
        valid_from=datetime.now(UTC) - timedelta(minutes=1),
        valid_until=datetime.now(UTC) + timedelta(days=1),
        status=DelegationStatus.ACTIVE,
        granted_by=uuid4(),
        reason="fixture",
        version=1,
    )
    policy = CredentialAuthorizationPolicy(InMemoryDelegationRepository([delegation]))

    result = await policy.can_issue(
        actor=ActorContext(
            actor_id=actor_id,
            organization_id=organization_id,
            roles=frozenset({Role.SME}),
        ),
        organization_id=organization_id,
        policy_id=policy_id,
        requester_id=uuid4(),
    )

    assert result.allowed is True
    assert result.delegation_id == delegation.id
