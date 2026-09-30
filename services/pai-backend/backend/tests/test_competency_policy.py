from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.assessment.schemas import AssessmentDecision, RiskClassification
from app.authorization.fixtures import AUTHORIZED_SME_ID, ORG_PAI_ID, SME_ID
from app.authorization.policy import CompetencyAuthorizationPolicy
from app.authorization.repository import InMemoryDelegationRepository
from app.authorization.schemas import (
    ActorContext,
    Role,
    ScopedDelegation,
)


class AssessmentReader:
    def __init__(self, decision: AssessmentDecision) -> None:
        self.decision = decision

    async def get_decision(self, decision_id: object) -> AssessmentDecision | None:
        return self.decision if decision_id == self.decision.id else None


def actor(actor_id: object, *roles: Role) -> ActorContext:
    return ActorContext(actor_id=actor_id, organization_id=ORG_PAI_ID, roles=frozenset(roles))


def assessment(risk: RiskClassification = RiskClassification.LOW_RISK) -> AssessmentDecision:
    return AssessmentDecision(
        id=uuid4(),
        submission_id=uuid4(),
        subject_id=uuid4(),
        score_proposal_id=uuid4(),
        review_id=uuid4(),
        assessor_id=SME_ID,
        rubric_version="1.0",
        policy_version="assessment-v1",
        evidence_ids=[uuid4()],
        risk_classification=risk,
        decided_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_plain_sme_can_mark_assessed_but_cannot_verify() -> None:
    decision = assessment()
    policy = CompetencyAuthorizationPolicy(
        subject_repository=None,
        delegation_repository=InMemoryDelegationRepository([]),
        assessment_repository=AssessmentReader(decision),
    )

    assessed = await policy.can_mark_assessed(
        actor=actor(SME_ID, Role.SME),
        organization_id=ORG_PAI_ID,
        competency_id="python",
        assessment_decision_id=decision.id,
    )
    verified = await policy.can_verify(
        actor=actor(SME_ID, Role.SME),
        subject_id=decision.subject_id or uuid4(),
        organization_id=ORG_PAI_ID,
        competency_id="python",
        assessment_decision_id=decision.id,
    )

    assert assessed.allowed is True
    assert verified.allowed is False
    assert verified.reason_code == "verification_delegation_required"


@pytest.mark.asyncio
async def test_delegated_sme_verifies_only_matching_scope_and_window() -> None:
    decision = assessment()
    delegation = ScopedDelegation(
        id=uuid4(),
        user_id=AUTHORIZED_SME_ID,
        permission="competency.verify",
        organization_id=ORG_PAI_ID,
        competency_scope=frozenset({"python"}),
        valid_from=datetime.now(UTC) - timedelta(minutes=1),
        valid_until=datetime.now(UTC) + timedelta(minutes=1),
        status="active",
        granted_by=uuid4(),
        reason="fixture",
        version=1,
    )
    policy = CompetencyAuthorizationPolicy(
        subject_repository=None,
        delegation_repository=InMemoryDelegationRepository([delegation]),
        assessment_repository=AssessmentReader(decision),
    )

    allowed = await policy.can_verify(
        actor=actor(AUTHORIZED_SME_ID, Role.SME),
        subject_id=decision.subject_id or uuid4(),
        organization_id=ORG_PAI_ID,
        competency_id="python",
        assessment_decision_id=decision.id,
    )
    denied = await policy.can_verify(
        actor=actor(AUTHORIZED_SME_ID, Role.SME),
        subject_id=decision.subject_id or uuid4(),
        organization_id=ORG_PAI_ID,
        competency_id="java",
        assessment_decision_id=decision.id,
    )

    assert allowed.allowed is True
    assert allowed.delegation_id == delegation.id
    assert denied.allowed is False
    assert denied.reason_code == "verification_scope_mismatch"


@pytest.mark.asyncio
async def test_high_risk_requires_distinct_assessor_and_verifier() -> None:
    decision = assessment(RiskClassification.HIGH_RISK)
    delegation = ScopedDelegation(
        id=uuid4(),
        user_id=SME_ID,
        permission="competency.verify",
        organization_id=ORG_PAI_ID,
        competency_scope=frozenset({"python"}),
        valid_from=datetime.now(UTC) - timedelta(minutes=1),
        valid_until=datetime.now(UTC) + timedelta(minutes=1),
        status="active",
        granted_by=uuid4(),
        reason="fixture",
        version=1,
    )
    policy = CompetencyAuthorizationPolicy(
        subject_repository=None,
        delegation_repository=InMemoryDelegationRepository([delegation]),
        assessment_repository=AssessmentReader(decision),
    )

    result = await policy.can_verify(
        actor=actor(SME_ID, Role.SME),
        subject_id=decision.subject_id or uuid4(),
        organization_id=ORG_PAI_ID,
        competency_id="python",
        assessment_decision_id=decision.id,
    )

    assert result.allowed is False
    assert result.reason_code == "four_eyes_required"
