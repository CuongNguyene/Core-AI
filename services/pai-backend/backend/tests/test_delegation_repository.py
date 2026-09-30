from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.authorization.fixtures import ADMIN_ID, ORG_PAI_ID, SME_ID
from app.authorization.repository import InMemoryDelegationRepository
from app.authorization.schemas import DelegationStatus, ScopedDelegation


def draft_delegation() -> ScopedDelegation:
    return ScopedDelegation(
        id=uuid4(),
        user_id=SME_ID,
        permission="competency.verify",
        organization_id=ORG_PAI_ID,
        competency_scope=frozenset({"python"}),
        valid_from=datetime.now(UTC) - timedelta(minutes=1),
        valid_until=datetime.now(UTC) + timedelta(days=1),
        status=DelegationStatus.DRAFT,
        granted_by=ADMIN_ID,
        reason="development fixture",
        version=1,
    )


@pytest.mark.asyncio
async def test_activate_uses_expected_version_and_appends_safe_audit() -> None:
    repository = InMemoryDelegationRepository([draft_delegation()])
    delegation = draft_delegation()
    repository = InMemoryDelegationRepository([delegation])

    activated = await repository.transition(
        delegation.id,
        ADMIN_ID,
        expected_version=1,
        target=DelegationStatus.ACTIVE,
        reason="approved",
    )

    assert activated.status is DelegationStatus.ACTIVE
    assert activated.version == 2
    assert repository.audit_events[-1]["action"] == "DELEGATION_ACTIVATED"
    assert "raw" not in repository.audit_events[-1]


@pytest.mark.asyncio
async def test_stale_or_invalid_transition_does_not_change_delegation() -> None:
    delegation = draft_delegation()
    repository = InMemoryDelegationRepository([delegation])

    with pytest.raises(ValueError, match="version_conflict"):
        await repository.transition(
            delegation.id,
            ADMIN_ID,
            expected_version=2,
            target=DelegationStatus.ACTIVE,
            reason="approved",
        )
    with pytest.raises(ValueError, match="invalid_transition"):
        await repository.transition(
            delegation.id,
            ADMIN_ID,
            expected_version=1,
            target=DelegationStatus.REVOKED,
            reason="bad",
        )
    restored = await repository.get(delegation.id)
    assert restored is not None and restored.status is DelegationStatus.DRAFT


@pytest.mark.asyncio
async def test_credential_issue_delegation_round_trips_without_changing_permission() -> None:
    baseline = draft_delegation()
    delegation = ScopedDelegation(
        id=baseline.id,
        user_id=baseline.user_id,
        permission="credential.issue",
        organization_id=baseline.organization_id,
        competency_scope=baseline.competency_scope,
        valid_from=baseline.valid_from,
        valid_until=baseline.valid_until,
        status=baseline.status,
        granted_by=baseline.granted_by,
        reason=baseline.reason,
        version=baseline.version,
    )
    repository = InMemoryDelegationRepository([delegation])

    stored = await repository.get(delegation.id)

    assert stored is not None
    assert stored.permission == "credential.issue"
