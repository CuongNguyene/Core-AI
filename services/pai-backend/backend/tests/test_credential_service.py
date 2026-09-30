from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.authorization.repository import InMemoryDelegationRepository
from app.authorization.schemas import ActorContext, DelegationStatus, Role, ScopedDelegation
from app.credential.evaluators import CredentialEvaluationInput
from app.credential.policy import CredentialAuthorizationPolicy
from app.credential.repository import InMemoryCredentialRepository
from app.credential.schemas import (
    Credential,
    CredentialPolicy,
    CredentialPolicyStatus,
    CredentialStatus,
    CredentialType,
    EligibilityDecision,
    EligibilityStatus,
)
from app.credential.service import CredentialPolicyRegistry, CredentialService


class EligibleEvaluator:
    async def evaluate(self, request: CredentialEvaluationInput) -> EligibilityDecision:
        return EligibilityDecision(
            policy_id=request.policy.policy_id,
            policy_version=request.policy.version,
            subject_id=request.subject_id,
            organization_id=request.organization_id,
            status=EligibilityStatus.ELIGIBLE,
            reason_code="eligible",
            evaluator_version="test-v1",
        )


def setup() -> tuple[CredentialService, ActorContext, ActorContext, CredentialPolicy]:
    organization_id = uuid4()
    learner_id = uuid4()
    approver_id = uuid4()
    policy = CredentialPolicy(
        policy_id="python-level-3",
        version="v1",
        credential_type=CredentialType.COMPETENCY,
        status=CredentialPolicyStatus.ACTIVE,
        organization_id=organization_id,
        valid_for_days=365,
        allow_duplicate_active=False,
        requires_distinct_approver_and_issuer=True,
    )
    delegation = ScopedDelegation(
        id=uuid4(),
        user_id=approver_id,
        permission="credential.approve",
        organization_id=organization_id,
        competency_scope=frozenset({policy.policy_id}),
        valid_from=datetime.now(UTC) - timedelta(minutes=1),
        valid_until=datetime.now(UTC) + timedelta(days=1),
        status=DelegationStatus.ACTIVE,
        granted_by=uuid4(),
        reason="fixture",
        version=1,
    )
    issue_delegation = delegation.model_copy(
        update={"id": uuid4(), "permission": "credential.issue"}
    )
    repository = InMemoryCredentialRepository([policy])
    authorization = CredentialAuthorizationPolicy(
        InMemoryDelegationRepository([delegation, issue_delegation])
    )
    service = CredentialService(
        repository=repository,
        registry=CredentialPolicyRegistry([policy]),
        evaluators={CredentialType.COMPETENCY: EligibleEvaluator()},
        authorization=authorization,
    )
    learner = ActorContext(
        actor_id=learner_id, organization_id=organization_id, roles=frozenset({Role.LEARNER})
    )
    approver = ActorContext(
        actor_id=approver_id, organization_id=organization_id, roles=frozenset({Role.SME})
    )
    return service, learner, approver, policy


@pytest.mark.asyncio
async def test_service_requires_approval_before_issuing_credential() -> None:
    service, learner, approver, policy = setup()
    request = await service.evaluate_and_request(
        actor=learner,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        source_reference_id="competency-record-1",
        correlation_id=uuid4(),
    )

    assert request.status.value == "pending_approval"
    with pytest.raises(ValueError, match="credential_approval_required"):
        await service.issue(actor=learner, request_id=request.id, expected_version=1)

    approved = await service.approve(actor=approver, request_id=request.id, expected_version=1)
    assert approved.status.value == "approved"


@pytest.mark.asyncio
async def test_duplicate_active_credential_does_not_consume_approved_request() -> None:
    service, learner, approver, policy = setup()
    repository = service._repository
    repository.credentials[uuid4()] = Credential(
        id=uuid4(),
        request_id=uuid4(),
        policy_id=policy.policy_id,
        policy_version=policy.version,
        credential_type=policy.credential_type,
        subject_id=learner.actor_id,
        organization_id=policy.organization_id,
        status=CredentialStatus.ISSUED,
        issued_at=datetime.now(UTC),
        valid_until=datetime.now(UTC) + timedelta(days=30),
        issued_by=approver.actor_id,
        version=1,
    )
    request = await service.evaluate_and_request(
        actor=learner,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        source_reference_id="competency-record-1",
        correlation_id=uuid4(),
    )
    await service.approve(actor=approver, request_id=request.id, expected_version=1)

    with pytest.raises(ValueError, match="active_credential_duplicate"):
        await service.issue(actor=approver, request_id=request.id, expected_version=2)

    stored = await service._require_request(request.id)
    assert stored.status.value == "approved"
