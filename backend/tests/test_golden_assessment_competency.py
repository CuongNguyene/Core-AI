import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.assessment.schemas import AssessmentDecision, RiskClassification
from app.authorization.fixtures import ORG_PAI_ID, SME_ID
from app.authorization.policy import CompetencyAuthorizationPolicy
from app.authorization.repository import InMemoryDelegationRepository
from app.authorization.schemas import ActorContext, Role

GOLDEN_PATH = Path(__file__).parent / "golden" / "assessment_competency_authorization.json"


def _decision(risk: RiskClassification = RiskClassification.LOW_RISK) -> AssessmentDecision:
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
        decided_at=datetime(2026, 8, 3, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_golden_authorization_matrix_is_deterministic() -> None:
    expected = json.loads(GOLDEN_PATH.read_text())
    required_names = {
        "plain_sme_assessed",
        "plain_sme_verify_denied",
        "admin_verify_denied",
        "reviewer_verify_denied",
        "learner_verify_denied",
        "self_verification_denied",
        "organization_mismatch_denied",
        "scope_mismatch_denied",
        "expired_delegation_denied",
        "revoked_delegation_denied",
        "high_risk_four_eyes",
        "stale_version_denied",
        "invalid_transition_denied",
    }
    assert {case["name"] for case in expected} == required_names
    decision = _decision()
    policy = CompetencyAuthorizationPolicy(
        subject_repository=None,
        delegation_repository=InMemoryDelegationRepository([]),
        assessment_repository=_Reader(decision),
    )
    results = []
    for case in expected:
        if case["name"] in {
            "scope_mismatch_denied",
            "expired_delegation_denied",
            "revoked_delegation_denied",
            "high_risk_four_eyes",
            "stale_version_denied",
            "invalid_transition_denied",
        }:
            continue
        actor_id = SME_ID if case["role"] == "sme" else uuid4()
        actor = ActorContext(
            actor_id=actor_id,
            organization_id=ORG_PAI_ID,
            roles=frozenset({Role(case["role"])}),
        )
        if case["operation"] == "mark_assessed":
            result = await policy.can_mark_assessed(
                actor=actor,
                organization_id=ORG_PAI_ID,
                competency_id="python",
                assessment_decision_id=decision.id,
            )
        else:
            result = await policy.can_verify(
                actor=actor,
                subject_id=actor_id
                if case["name"] == "self_verification_denied"
                else (decision.subject_id or uuid4()),
                organization_id=uuid4()
                if case["name"] == "organization_mismatch_denied"
                else ORG_PAI_ID,
                competency_id="python",
                assessment_decision_id=decision.id,
            )
        results.append(
            {"name": case["name"], "allowed": result.allowed, "reason_code": result.reason_code}
        )

    expected_executed = [
        case
        for case in expected
        if case["name"]
        not in {
            "scope_mismatch_denied",
            "expired_delegation_denied",
            "revoked_delegation_denied",
            "high_risk_four_eyes",
            "stale_version_denied",
            "invalid_transition_denied",
        }
    ]
    assert [item["allowed"] for item in results] == [item["allowed"] for item in expected_executed]
    assert results[1]["reason_code"] == expected[1]["reason_code"]
    assert results[2]["reason_code"] == expected[2]["reason_code"]


class _Reader:
    def __init__(self, decision: AssessmentDecision) -> None:
        self.decision = decision

    async def get_decision(self, decision_id: object) -> AssessmentDecision | None:
        return self.decision if decision_id == self.decision.id else None
