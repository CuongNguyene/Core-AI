import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.credential.evaluators import (
    CompletionCredentialEvaluator,
    CredentialEligibilityEvaluator,
    CredentialEvaluationInput,
    LearningAchievementCredentialEvaluator,
)
from app.credential.providers import (
    CompletionAssertion,
    FakeCompletionAssertionProvider,
    FakeLearningOutcomeAssertionProvider,
    LearningOutcomeAssertion,
    UnavailableCompletionAssertionProvider,
    UnavailableLearningOutcomeAssertionProvider,
)
from app.credential.schemas import CredentialPolicy, CredentialPolicyStatus, CredentialType

GOLDEN_PATH = Path(__file__).parent / "golden" / "credential_policy_issuance.json"


def policy(credential_type: CredentialType, organization_id: UUID) -> CredentialPolicy:
    return CredentialPolicy(
        policy_id=f"golden-{credential_type.value}",
        version="v1",
        credential_type=credential_type,
        status=CredentialPolicyStatus.ACTIVE,
        organization_id=organization_id,
        valid_for_days=365,
        allow_duplicate_active=False,
        requires_distinct_approver_and_issuer=False,
    )


@pytest.mark.asyncio
async def test_credential_golden_cases_are_deterministic_and_safe() -> None:
    fixture = json.loads(GOLDEN_PATH.read_text())
    subject_id = uuid4()
    organization_id = uuid4()
    completion_policy = policy(CredentialType.COMPLETION, organization_id)
    achievement_policy = policy(CredentialType.LEARNING_ACHIEVEMENT, organization_id)
    completion_assertion = CompletionAssertion(
        learner_id=subject_id,
        organization_id=organization_id,
        course_id="course-1",
        course_version="v1",
        completed=True,
        source_system="fixture-lms",
        source_record_id="completion-1",
    )
    outcome_assertion = LearningOutcomeAssertion(
        learner_id=subject_id,
        organization_id=organization_id,
        learning_outcome_id="outcome-1",
        course_version="v1",
        assessment_id="assessment-1",
        rubric_version="rubric-v1",
        passed=True,
    )
    evaluators: dict[CredentialType, CredentialEligibilityEvaluator] = {
        CredentialType.COMPLETION: CompletionCredentialEvaluator(
            FakeCompletionAssertionProvider({"completion-approved": completion_assertion})
        ),
        CredentialType.LEARNING_ACHIEVEMENT: LearningAchievementCredentialEvaluator(
            FakeLearningOutcomeAssertionProvider({"outcome-approved": outcome_assertion})
        ),
    }
    policies = {
        CredentialType.COMPLETION: completion_policy,
        CredentialType.LEARNING_ACHIEVEMENT: achievement_policy,
    }

    for case in fixture["cases"]:
        credential_type = CredentialType(case["credential_type"])
        evaluator = evaluators[credential_type]
        if case["expected_status"] == "not_evaluable":
            evaluator = (
                CompletionCredentialEvaluator(UnavailableCompletionAssertionProvider())
                if credential_type is CredentialType.COMPLETION
                else LearningAchievementCredentialEvaluator(
                    UnavailableLearningOutcomeAssertionProvider()
                )
            )
        request = CredentialEvaluationInput(
            policy=policies[credential_type],
            subject_id=subject_id,
            organization_id=organization_id,
            source_reference_id=case["source_reference_id"],
        )
        result = await evaluator.evaluate(request)
        rerun = await evaluator.evaluate(request)
        assert result.model_dump(mode="json") == rerun.model_dump(mode="json")
        assert result.status.value == case["expected_status"]
        assert result.reason_code == case["expected_reason"]
        assert "raw" not in result.model_dump(mode="json")
        assert "prompt" not in result.model_dump(mode="json")
