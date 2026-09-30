from uuid import uuid4

import pytest

from app.credential.repository import InMemoryCredentialRepository
from app.credential.schemas import (
    CredentialPolicy,
    CredentialPolicyStatus,
    CredentialRequestStatus,
    CredentialType,
    EligibilityDecision,
    EligibilityStatus,
)


def policy() -> CredentialPolicy:
    return CredentialPolicy(
        policy_id="python-level-3",
        version="v1",
        credential_type=CredentialType.COMPETENCY,
        status=CredentialPolicyStatus.ACTIVE,
        organization_id=uuid4(),
        valid_for_days=365,
        allow_duplicate_active=False,
        requires_distinct_approver_and_issuer=True,
    )


@pytest.mark.asyncio
async def test_in_memory_repository_persists_eligible_request_and_rejects_stale_transition() -> (
    None
):
    repository = InMemoryCredentialRepository([policy()])
    item = policy()
    evaluation = EligibilityDecision(
        policy_id=item.policy_id,
        policy_version=item.version,
        subject_id=uuid4(),
        organization_id=item.organization_id,
        status=EligibilityStatus.ELIGIBLE,
        reason_code="eligible",
        evaluator_version="test-v1",
    )
    request = await repository.create_request(
        policy=item,
        subject_id=evaluation.subject_id,
        source_reference_id="record-1",
        evaluation=evaluation,
        requested_by=uuid4(),
        correlation_id=uuid4(),
    )

    assert request.status is CredentialRequestStatus.PENDING_APPROVAL
    with pytest.raises(ValueError, match="version_conflict"):
        await repository.transition_request(
            request.id,
            expected_version=2,
            target=CredentialRequestStatus.APPROVED,
            actor_id=uuid4(),
        )
    stored = await repository.get_request(request.id)
    assert stored is not None and stored.version == 1
